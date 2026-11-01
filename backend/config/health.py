import logging

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_safe
from infrastructure.redis.client import get_redis_client

logger = logging.getLogger(__name__)


@require_safe
def health(request):
    """Liveness: 200 while the process serves requests; touches no dependency."""
    return JsonResponse({"status": "ok"})


def _check_postgres():
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")


def _check_redis():
    client = get_redis_client(socket_connect_timeout=2, socket_timeout=2)
    try:
        client.ping()
    finally:
        client.close()


@require_safe
def ready(request):
    """Readiness: 200 only if Postgres and Redis answer, else 503 naming the failed one."""
    checks = {}
    for name, check in (("postgres", _check_postgres), ("redis", _check_redis)):
        try:
            check()
            checks[name] = "ok"
        except Exception as exc:
            logger.warning("Readiness check failed: %s: %s", name, exc)
            checks[name] = "error"
    ok = all(state == "ok" for state in checks.values())
    return JsonResponse(
        {"status": "ok" if ok else "unavailable", "checks": checks},
        status=200 if ok else 503,
    )
