"""
Sliding-window rate limiting, plus real-client-IP detection.

By default the counts live in this process, so with N workers or instances the effective limit is up to N
times higher. Set REDIS_URL to share them: every instance then counts into the same windows. If Redis is
unreachable the limiter falls back to the in-process counts rather than failing requests (or letting
everything through), and tries Redis again shortly after.
"""
import logging
import threading
import time
import uuid
from collections import deque

from fastapi import HTTPException, Request

from app.config import settings

log = logging.getLogger("hotcrowd.ratelimit")


def client_ip(request: Request) -> str:
    """The caller's address, trusting X-Forwarded-For only for the configured number of proxies.

    Each proxy appends the address it saw, so with N trusted proxies the real client is the Nth entry from
    the right. Anything a client prepends to the header sits further left and is ignored.
    """
    peer = request.client.host if request.client else "unknown"
    hops = settings.trusted_proxy_count
    if hops <= 0:
        return peer
    forwarded = [part.strip() for part in request.headers.get("x-forwarded-for", "").split(",") if part.strip()]
    if len(forwarded) >= hops:
        return forwarded[-hops]
    return peer


class RateLimiter:
    def __init__(self, max_keys: int = 20_000):
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._max_keys = max_keys

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

    def _prune(self, key: str, window: float, now: float) -> deque[float]:
        events = self._events.setdefault(key, deque())
        while events and events[0] <= now - window:
            events.popleft()
        return events

    def _evict(self, window: float, now: float) -> None:
        # Called under the lock when the table is full: drop expired keys, then the oldest ones.
        for key in [k for k, ev in self._events.items() if not ev or ev[-1] <= now - window]:
            del self._events[key]
        if len(self._events) > self._max_keys:
            oldest = sorted(self._events, key=lambda k: self._events[k][-1])
            for key in oldest[: len(self._events) - self._max_keys + self._max_keys // 10]:
                del self._events[key]

    def allow(self, key: str, limit: int, window: float) -> bool:
        """Record an attempt; False when this key already used up `limit` attempts in `window` seconds."""
        now = time.monotonic()
        with self._lock:
            if len(self._events) >= self._max_keys:
                self._evict(window, now)
            events = self._prune(key, window, now)
            if len(events) >= limit:
                return False
            events.append(now)
            return True

    def blocked(self, key: str, limit: int, window: float) -> bool:
        """Is this key at its limit? Does not record anything."""
        now = time.monotonic()
        with self._lock:
            events = self._events.get(key)
            if not events:
                return False
            return len(self._prune(key, window, now)) >= limit

    def record(self, key: str, window: float) -> None:
        now = time.monotonic()
        with self._lock:
            if len(self._events) >= self._max_keys:
                self._evict(window, now)
            self._prune(key, window, now).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)


_PRUNE = """
local t = redis.call('TIME')
local now = t[1] * 1000 + math.floor(t[2] / 1000)
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, now - tonumber(ARGV[1]) * 1000)
"""
_ALLOW = _PRUNE + """
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[2]) then return 0 end
redis.call('ZADD', KEYS[1], now, ARGV[3])
redis.call('PEXPIRE', KEYS[1], tonumber(ARGV[1]) * 1000)
return 1
"""
_BLOCKED = _PRUNE + """
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[2]) then return 1 end
return 0
"""
_RECORD = _PRUNE + """
redis.call('ZADD', KEYS[1], now, ARGV[3])
redis.call('PEXPIRE', KEYS[1], tonumber(ARGV[1]) * 1000)
return 1
"""


class RedisRateLimiter:
    """The same interface as RateLimiter, with the windows kept in Redis (sorted sets, one Lua call each)."""

    PREFIX = "hc:rl:"
    RETRY_AFTER = 10.0  # seconds to leave a failing Redis alone before trying it again

    def __init__(self, url: str, fallback: RateLimiter | None = None):
        import redis

        self._client = redis.Redis.from_url(url, socket_timeout=0.25, socket_connect_timeout=0.25)
        self._allow = self._client.register_script(_ALLOW)
        self._blocked = self._client.register_script(_BLOCKED)
        self._record = self._client.register_script(_RECORD)
        self._fallback = fallback or RateLimiter()
        self._down_until = 0.0

    def _call(self, shared, local):
        if time.monotonic() < self._down_until:
            return local()
        try:
            result = shared()
        except Exception as exc:  # noqa: BLE001 - any Redis problem means "use the local counts for now"
            self._down_until = time.monotonic() + self.RETRY_AFTER
            log.warning("Rate-limit store unavailable (%s); using in-process counts", exc.__class__.__name__)
            return local()
        return result

    def allow(self, key: str, limit: int, window: float) -> bool:
        return bool(
            self._call(
                lambda: self._allow(keys=[self.PREFIX + key], args=[window, limit, uuid.uuid4().hex]),
                lambda: self._fallback.allow(key, limit, window),
            )
        )

    def blocked(self, key: str, limit: int, window: float) -> bool:
        return bool(
            self._call(
                lambda: self._blocked(keys=[self.PREFIX + key], args=[window, limit]),
                lambda: self._fallback.blocked(key, limit, window),
            )
        )

    def record(self, key: str, window: float) -> None:
        self._call(
            lambda: self._record(keys=[self.PREFIX + key], args=[window, 0, uuid.uuid4().hex]),
            lambda: self._fallback.record(key, window),
        )

    def reset(self, key: str) -> None:
        self._fallback.reset(key)
        self._call(lambda: self._client.delete(self.PREFIX + key), lambda: None)

    def clear(self) -> None:
        """Forget everything (tests)."""
        self._fallback.clear()
        try:
            keys = list(self._client.scan_iter(match=self.PREFIX + "*", count=500))
            if keys:
                self._client.delete(*keys)
        except Exception:  # noqa: BLE001
            pass


def build_limiter() -> RateLimiter | RedisRateLimiter:
    if settings.redis_url:
        return RedisRateLimiter(settings.redis_url)
    return RateLimiter()


limiter = build_limiter()


def enforce(request: Request, action: str, limit: int, window: float, *, key: str | None = None) -> None:
    """Raise 429 once the caller (by IP, or by an explicit key) exceeds `limit` requests per `window`."""
    bucket = f"{action}:{key if key is not None else client_ip(request)}"
    if not limiter.allow(bucket, limit, window):
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Please wait a moment and try again.",
            headers={"Retry-After": str(int(window))},
        )
