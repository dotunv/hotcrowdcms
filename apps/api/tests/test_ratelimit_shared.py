"""The Redis-backed limiter behaves like the in-process one, is shared between instances, and degrades safely."""
import os
import time
import uuid

import pytest

from app.ratelimit import RateLimiter, RedisRateLimiter

REDIS_URL = os.environ.get("TEST_REDIS_URL", "")
needs_redis = pytest.mark.skipif(not REDIS_URL, reason="set TEST_REDIS_URL to run against a real Redis")


def _key() -> str:
    return f"t-{uuid.uuid4().hex}"


@pytest.fixture(params=["memory", pytest.param("redis", marks=needs_redis)])
def limiter(request):
    if request.param == "memory":
        return RateLimiter()
    instance = RedisRateLimiter(REDIS_URL)
    instance.clear()
    return instance


def test_allows_up_to_the_limit_then_blocks(limiter):
    key = _key()
    assert [limiter.allow(key, 3, 60) for _ in range(5)] == [True, True, True, False, False]


def test_keys_are_independent(limiter):
    a, b = _key(), _key()
    for _ in range(3):
        limiter.allow(a, 3, 60)
    assert limiter.allow(a, 3, 60) is False
    assert limiter.allow(b, 3, 60) is True


def test_window_slides(limiter):
    key = _key()
    assert limiter.allow(key, 1, 1) is True
    assert limiter.allow(key, 1, 1) is False
    time.sleep(1.2)
    assert limiter.allow(key, 1, 1) is True


def test_blocked_does_not_count_and_record_does(limiter):
    key = _key()
    for _ in range(5):
        assert limiter.blocked(key, 2, 60) is False
    limiter.record(key, 60)
    limiter.record(key, 60)
    assert limiter.blocked(key, 2, 60) is True


def test_reset_clears_one_key(limiter):
    key = _key()
    limiter.record(key, 60)
    limiter.record(key, 60)
    limiter.reset(key)
    assert limiter.blocked(key, 2, 60) is False


@needs_redis
def test_two_instances_share_the_same_counts():
    first, second = RedisRateLimiter(REDIS_URL), RedisRateLimiter(REDIS_URL)
    key = _key()
    assert first.allow(key, 2, 60) is True
    assert second.allow(key, 2, 60) is True
    assert first.allow(key, 2, 60) is False
    assert second.allow(key, 2, 60) is False


@needs_redis
def test_keys_expire_in_redis_so_it_does_not_fill_up():
    limiter = RedisRateLimiter(REDIS_URL)
    key = _key()
    limiter.allow(key, 5, 60)
    assert 0 < limiter._client.pttl(RedisRateLimiter.PREFIX + key) <= 60_000


def test_unreachable_redis_falls_back_to_local_counts_and_keeps_limiting():
    limiter = RedisRateLimiter("redis://127.0.0.1:1/0")  # nothing listens here
    key = _key()
    assert [limiter.allow(key, 2, 60) for _ in range(3)] == [True, True, False]
    assert limiter.blocked(key, 2, 60) is True


def test_a_failing_redis_is_not_retried_on_every_call(monkeypatch):
    limiter = RedisRateLimiter("redis://127.0.0.1:1/0")
    limiter.allow(_key(), 5, 60)
    calls = []
    monkeypatch.setattr(limiter, "_allow", lambda **kw: calls.append(kw))
    limiter.allow(_key(), 5, 60)
    assert calls == []  # inside the back-off window: straight to the local counts
