import asyncio

from api.internal import callbacks
from api.routers import tasks, websockets
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from infrastructure.redis.client import redis_client

app = FastAPI(title="Battle Engine FastAPI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # change in future
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
            print(f"New event from Django: {message['data']}")


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(redis_listener())


@app.on_event("shutdown")
async def shutdown_event():
    await redis_client.close()
