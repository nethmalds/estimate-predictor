"""Async Redis client singleton.

Usage:
    from infrastructure.cache.redis_client import get_redis, init_redis, close_redis

    # In server startup:
    await init_redis()

    # In server shutdown:
    await close_redis()

    # In request handlers:
    r = get_redis()
    if r:
        await r.set("key", "value", ex=3600)
"""
import logging

import redis.asyncio as aioredis

from core.config.settings import settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis | None:
    """Return the active Redis client, or None if Redis is not configured."""
    return _redis


async def init_redis() -> None:
    """Connect to Redis. No-op (with warning) if REDIS_URL is not set."""
    global _redis
    if not settings.redis_url:
        logger.warning(
            "REDIS_URL not set — session store will use in-process memory. "
            "Sessions will be lost on restart and won't share across workers."
        )
        return
    try:
        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        _redis = client
        logger.info("Redis connected: %s", settings.redis_url.split("@")[-1])
    except Exception as exc:
        logger.error("Redis connection failed (%s) — falling back to in-process store", exc)
        _redis = None


async def close_redis() -> None:
    """Close the Redis connection gracefully."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
