"""
In-process sliding-window rate limiting with bounded memory, plus real-client-IP detection.

State lives in this process: with N workers the effective limit is up to N times higher. That is still
enough to stop online password guessing and code scanning; a shared store (Redis) is the next step if
you scale out.
"""
import threading
import time
from collections import deque

from fastapi import HTTPException, Request

from app.config import settings


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


limiter = RateLimiter()


def enforce(request: Request, action: str, limit: int, window: float, *, key: str | None = None) -> None:
    """Raise 429 once the caller (by IP, or by an explicit key) exceeds `limit` requests per `window`."""
    bucket = f"{action}:{key if key is not None else client_ip(request)}"
    if not limiter.allow(bucket, limit, window):
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Please wait a moment and try again.",
            headers={"Retry-After": str(int(window))},
        )
