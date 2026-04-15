import asyncio
import logging
import re

from core.logging_config import setup_logging

setup_logging()

from api.internal import callbacks
from api.routers import tasks, websockets
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from infrastructure.redis.client import redis_client
from services.django_callbacks import notify_django_delete_battle

logger = logging.getLogger(__name__)

IDLE_KEY_PATTERN = re.compile(r"^battle:(\d+):idle_ttl$")

app = FastAPI(title="Battle Engine FastAPI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["localhost", "127.0.0.1"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(callbacks.router)
app.include_router(tasks.router, prefix="/api")
app.include_router(websockets.router)


async def idle_battle_listener():
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("__keyevent@0__:expired")

    async for message in pubsub.listen():
        if message["type"] != "message":
            continue

        expired_key = message["data"]
        if not isinstance(expired_key, str):
            expired_key = expired_key.decode()

        match = IDLE_KEY_PATTERN.match(expired_key)
        if not match:
            continue

        battle_id = int(match.group(1))
        logger.info(f"Battle {battle_id} idle timer expired, requesting deletion")

        try:
            await notify_django_delete_battle(battle_id)
        except Exception as exc:
            logger.error(f"Failed to delete idle battle {battle_id}: {exc}")

        for suffix in ("deadline", "finished"):
            await redis_client.delete(f"battle:{battle_id}:{suffix}")


@app.on_event("startup")
async def startup_event():
    try:
        await redis_client.config_set("notify-keyspace-events", "Ex")
    except Exception as exc:
        logger.warning(
            f"Could not enable keyspace notifications: {exc}. "
            "Make sure Redis is configured with notify-keyspace-events=Ex"
        )
    asyncio.create_task(idle_battle_listener())


@app.on_event("shutdown")
async def shutdown_event():
    await redis_client.close()