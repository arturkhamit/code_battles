import asyncio
import json
import logging

from api.internal import callbacks
from api.routers import tasks, websockets
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from infrastructure.redis.client import redis_client
from services.battle_engine import manager

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


async def redis_listener():
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("battle_events")

    async for message in pubsub.listen():
        if message["type"] == "message":
            try:
                payload = json.loads(message["data"])

                if payload.get("type") == "battle_joined":
                    event_data = payload.get("data", {})

                    battle_id = event_data.get("battle_id")
                    task_id = event_data.get("task_id")
                    participants = event_data.get("participants", [])
                    participants_count = len(participants)

                    if battle_id:
                        await manager.broadcast(
                            battle_id,
                            {
                                "event": "lobby_update",
                                "data": {
                                    "participants_count": participants_count,
                                    "task_id": task_id,
                                },
                            },
                        )

            except json.JSONDecodeError:
                logging.error("Error while patsing JSON from Redis")
            except Exception as e:
                logging.error(f"Error while broadcasting: {e}")


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(redis_listener())


@app.on_event("shutdown")
async def shutdown_event():
    await redis_client.close()
