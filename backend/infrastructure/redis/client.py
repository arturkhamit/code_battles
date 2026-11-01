import redis
from django.conf import settings


def get_redis_client(**kwargs) -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, **kwargs)


# publishes are best-effort and happen inside requests: an unreachable Redis must not hang them
redis_client = get_redis_client(socket_connect_timeout=2, socket_timeout=2)
