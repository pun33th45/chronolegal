import json
import time
from typing import Any

import redis.asyncio as aioredis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from loguru import logger

from app.core.config import settings

_redis_client: aioredis.Redis | None = None

# In-process fallback store, used only when Redis itself is unreachable (e.g.
# this dev/demo environment, which has no Redis service running at all). Without
# this, every cache.get()/set() silently no-ops on the connection error, so
# even an exact repeat question re-runs the full query-rewrite + embedding
# round trip every time. This never replaces Redis when Redis is actually
# reachable — it only kicks in on the same exception path that already logs
# "Cache get/set error" today, and it's a plain dict (not shared across
# processes/workers), which is fine for this single-process deployment.
_local_cache: dict[str, tuple[Any, float | None]] = {}


def _local_get(key: str) -> Any | None:
    entry = _local_cache.get(key)
    if entry is None:
        return None
    value, expires_at = entry
    if expires_at is not None and time.monotonic() > expires_at:
        del _local_cache[key]
        return None
    return value


def _local_set(key: str, value: Any, ttl: int | None) -> None:
    expires_at = time.monotonic() + ttl if ttl else None
    _local_cache[key] = (value, expires_at)


# Circuit breaker. Without it, every cache call re-attempts the connection
# when Redis is unreachable (e.g. this deployment, which runs no Redis): on
# Windows each failed attempt spends ~2.7s in DNS resolution before falling
# back, and a single research question makes several cache calls. After one
# connection failure Redis is skipped for _REDIS_RETRY_SECONDS and the
# in-process fallback is used directly; then one attempt is made again.
_REDIS_RETRY_SECONDS = 300.0
_redis_down_until = 0.0
_CONNECTION_ERRORS = (RedisConnectionError, RedisTimeoutError, OSError)


def _redis_available() -> bool:
    return time.monotonic() >= _redis_down_until


def _note_failure(exc: Exception) -> None:
    global _redis_down_until
    if isinstance(exc, _CONNECTION_ERRORS):
        if _redis_available():
            logger.warning(
                f"Redis unreachable ({exc}); using the in-process cache for "
                f"{int(_REDIS_RETRY_SECONDS)}s before retrying"
            )
        _redis_down_until = time.monotonic() + _REDIS_RETRY_SECONDS


async def get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None


class CacheService:
    def __init__(self, prefix: str = "chronolegal") -> None:
        self.prefix = prefix
        self.default_ttl = settings.CACHE_TTL_SECONDS

    def _key(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Any | None:
        full_key = self._key(key)
        if not _redis_available():
            return _local_get(full_key)
        client = await get_redis()
        try:
            value = await client.get(full_key)
            return json.loads(value) if value else None
        except Exception as e:
            _note_failure(e)
            logger.debug(f"Cache get error for key={key}: {e} (using in-process fallback)")
            return _local_get(full_key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        full_key = self._key(key)
        if not _redis_available():
            _local_set(full_key, value, ttl or self.default_ttl)
            return False
        client = await get_redis()
        try:
            serialized = json.dumps(value, default=str)
            await client.setex(full_key, ttl or self.default_ttl, serialized)
            return True
        except Exception as e:
            _note_failure(e)
            logger.debug(f"Cache set error for key={key}: {e} (using in-process fallback)")
            _local_set(full_key, value, ttl or self.default_ttl)
            return False

    async def delete(self, key: str) -> bool:
        _local_cache.pop(self._key(key), None)
        if not _redis_available():
            return True
        client = await get_redis()
        try:
            await client.delete(self._key(key))
            return True
        except Exception as e:
            _note_failure(e)
            logger.debug(f"Cache delete error for key={key}: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """`pattern` supports a single trailing `*` wildcard (e.g.
        "rag:*") — enough for every current caller, which just needs to
        invalidate a whole cache namespace (e.g. all cached RAG answers
        after a judgment is deleted, so a repeated exact question can't
        surface a stale pre-deletion answer for a case that no longer
        exists)."""
        prefix = self._key(pattern.rstrip("*"))
        matched = [k for k in _local_cache if k.startswith(prefix)]
        for k in matched:
            del _local_cache[k]
        if not _redis_available():
            return len(matched)
        client = await get_redis()
        try:
            keys = await client.keys(self._key(pattern))
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception as e:
            _note_failure(e)
            logger.debug(f"Cache delete_pattern error: {e} (using in-process fallback)")
            return len(matched)

    async def exists(self, key: str) -> bool:
        full_key = self._key(key)
        if not _redis_available():
            return _local_get(full_key) is not None
        client = await get_redis()
        try:
            return bool(await client.exists(full_key))
        except Exception as e:
            _note_failure(e)
            return _local_get(full_key) is not None

    async def exists_strict(self, key: str) -> bool:
        """Like exists(), but propagates Redis errors instead of failing
        open. Use only for security-critical checks (e.g. token
        revocation) where an unreachable cache must not be silently
        treated as "not found"."""
        if not _redis_available():
            # Still fails closed, just without another connection timeout.
            raise RedisConnectionError("Redis unavailable (circuit open)")
        client = await get_redis()
        try:
            return bool(await client.exists(self._key(key)))
        except Exception as e:
            _note_failure(e)
            raise

    async def increment(self, key: str, ttl: int | None = None) -> int:
        client = await get_redis()
        pipe = client.pipeline()
        full_key = self._key(key)
        pipe.incr(full_key)
        if ttl:
            pipe.expire(full_key, ttl)
        results = await pipe.execute()
        return results[0]


cache = CacheService()
