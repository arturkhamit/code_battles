import asyncio
import logging
from contextlib import asynccontextmanager

from core.logging_config import setup_logging

setup_logging()

from api.routers import tasks, websockets  # noqa: E402
from core.config import settings  # noqa: E402
from core.tasks import supervise  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from infrastructure.redis.client import close_redis, get_redis, init_redis  # noqa: E402
from redis.exceptions import RedisError  # noqa: E402
from services import battle_flow, limits, runner_client  # noqa: E402
from services import django_callbacks as django  # noqa: E402
from services.battle_engine import manager  # noqa: E402

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_redis()
    await django.start()
    await runner_client.start()
    background = [
        asyncio.create_task(supervise("idle listener", battle_flow.idle_listener), name="idle-listener"),
        asyncio.create_task(supervise("finish outbox", django.outbox_worker), name="finish-outbox"),
    ]
    try:
        # a restart in the middle of a battle must not lose its time-up
        await battle_flow.rearm_timers()
    except Exception:
        logger.exception("Could not re-arm battle timers (Redis unavailable?)")

    yield

    for task in background:
        task.cancel()
    await asyncio.gather(*background, return_exceptions=True)
    battle_flow.cancel_timers()
    await manager.shutdown()
    await runner_client.close()
    await django.close()
    await close_redis()


# Interactive docs and the schema are for local work only
_no_docs = {"docs_url": None, "redoc_url": None, "openapi_url": None}
app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
    **(_no_docs if settings.is_production else {}),
)

if settings.CORS_ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.include_router(tasks.router, prefix="/api")
app.include_router(websockets.router)


@app.get("/health", include_in_schema=False)
async def health():
    """Liveness: 200 while the process answers; touches no dependency."""
    return {"status": "ok"}


@app.get("/ready", include_in_schema=False)
async def ready():
    """Readiness: Redis PING and Django /ready (so Postgres too), 503 naming what is down."""
    checks = {}

    async def check(name, probe):
        try:
            await asyncio.wait_for(probe(), 2.5)
            checks[name] = "ok"
        except Exception as exc:
            logger.warning("Readiness check failed: %s: %s", name, type(exc).__name__)
            checks[name] = "error"

    await asyncio.gather(
        check("redis", lambda: get_redis().ping()), check("django", django.check_ready)
    )
    ok = all(state == "ok" for state in checks.values())
    return JSONResponse(
        {"status": "ok" if ok else "unavailable", "checks": checks},
        status_code=200 if ok else 503,
    )


@app.exception_handler(django.DjangoError)
async def django_error_handler(request: Request, exc: django.DjangoError):
    if exc.status == 404:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    if exc.status is None:
        return JSONResponse({"detail": "Task service is unavailable"}, status_code=503)
    return JSONResponse({"detail": "Task service error"}, status_code=502)


@app.exception_handler(limits.RateLimited)
async def rate_limited_handler(request: Request, exc: limits.RateLimited):
    return JSONResponse(
        {
            "detail": exc.message,
            "code": "rate_limited",
            "scope": exc.scope,
            "retry_after": exc.retry_after,
        },
        status_code=429,
        headers={"Retry-After": str(exc.retry_after)},
    )


@app.exception_handler(RedisError)
async def redis_error_handler(request: Request, exc: RedisError):
    logger.error("Redis error: %s", type(exc).__name__)
    return JSONResponse({"detail": "Service temporarily unavailable"}, status_code=503)
