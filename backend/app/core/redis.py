import json
from typing import Any

import redis.asyncio as aioredis
from loguru import logger

from app.core.config import settings

_redis_client: aioredis.Redis | None = None


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
        client = await get_redis()
        try:
            value = await client.get(self._key(key))
            return json.loads(value) if value else None
        except Exception as e:
            logger.warning(f"Cache get error for key={key}: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        client = await get_redis()
        try:
            serialized = json.dumps(value, default=str)
            await client.setex(self._key(key), ttl or self.default_ttl, serialized)
            return True
        except Exception as e:
            logger.warning(f"Cache set error for key={key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        client = await get_redis()
        try:
            await client.delete(self._key(key))
            return True
        except Exception as e:
            logger.warning(f"Cache delete error for key={key}: {e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        client = await get_redis()
        try:
            keys = await client.keys(self._key(pattern))
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Cache delete_pattern error: {e}")
            return 0

    async def exists(self, key: str) -> bool:
        client = await get_redis()
        try:
            return bool(await client.exists(self._key(key)))
        except Exception:
            return False

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
