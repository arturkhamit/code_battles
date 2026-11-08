import redis.asyncio as redis
from core.config import settings

# Created in the app lifespan (init_redis), on the loop that serves requests: a client made at
# import time would be tied to whatever loop first touches it.
_client: redis.Redis | None = None


def init_redis() -> redis.Redis:
    global _client
    _client = redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_keepalive=True,
        health_check_interval=30,  # pub/sub listeners notice a silently dead connection
    )
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


def get_redis() -> redis.Redis:
    if _client is None:
        raise RuntimeError("Redis client is not initialised (app lifespan has not started)")
    return _client


def redis_db() -> int:
    return get_redis().connection_pool.connection_kwargs.get("db", 0)
