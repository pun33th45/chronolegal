"""The cache's Redis circuit breaker: one connection failure stops further
Redis attempts (each failed attempt costs seconds) until the retry window
passes, while cache reads/writes keep working in-process."""

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core import redis as redis_module


class _DeadRedis:
    def __init__(self):
        self.calls = 0

    async def _fail(self, *a, **k):
        self.calls += 1
        raise RedisConnectionError("Error 11001 connecting to redis:6379")

    get = setex = exists = delete = keys = _fail


@pytest.fixture
def dead_redis(monkeypatch):
    client = _DeadRedis()

    async def fake_get_redis():
        return client

    monkeypatch.setattr(redis_module, "get_redis", fake_get_redis)
    monkeypatch.setattr(redis_module, "_redis_down_until", 0.0)
    redis_module._local_cache.clear()
    return client


@pytest.mark.asyncio
async def test_one_failure_opens_the_breaker_and_fallback_still_works(dead_redis):
    cache = redis_module.CacheService()
    assert await cache.get("k") is None  # first call hits Redis and fails
    assert dead_redis.calls == 1

    await cache.set("k", {"v": 1}, ttl=60)
    assert await cache.get("k") == {"v": 1}  # served in-process
    assert await cache.exists("k") is True
    assert dead_redis.calls == 1  # no further Redis attempts while open


@pytest.mark.asyncio
async def test_strict_check_still_fails_closed_while_open(dead_redis):
    cache = redis_module.CacheService()
    await cache.get("k")  # opens the breaker
    with pytest.raises(RedisConnectionError):
        await cache.exists_strict("rt_deny:abc")
    assert dead_redis.calls == 1


@pytest.mark.asyncio
async def test_redis_is_retried_after_the_window(dead_redis, monkeypatch):
    cache = redis_module.CacheService()
    await cache.get("k")
    monkeypatch.setattr(redis_module, "_redis_down_until", 0.0)  # window elapsed
    await cache.get("k")
    assert dead_redis.calls == 2
