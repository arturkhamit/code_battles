import asyncio
import json
import logging

from fastapi import WebSocket

from infrastructure.redis.client import redis_client

logger = logging.getLogger(__name__)

IDLE_TTL_SECONDS = 300


def _channel(battle_id: int) -> str:
    return f"battle:{battle_id}:events"


def _idle_key(battle_id: int) -> str:
    return f"battle:{battle_id}:idle_ttl"


class BattleConnectionManager:
    def __init__(self):
        self.local_sockets: dict[int, dict[int, WebSocket]] = {}
        self._subscriptions: dict[int, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket, battle_id: int, user_id: int):
        await websocket.accept()

        is_first = battle_id not in self.local_sockets
        if is_first:
            self.local_sockets[battle_id] = {}

        self.local_sockets[battle_id][user_id] = websocket

        if is_first:
            self._subscriptions[battle_id] = asyncio.create_task(
                self._subscribe(battle_id)
            )

        await redis_client.delete(_idle_key(battle_id))

    def disconnect(self, battle_id: int, user_id: int):
        sockets = self.local_sockets.get(battle_id)
        if not sockets:
            return

        sockets.pop(user_id, None)

        if not sockets:
            del self.local_sockets[battle_id]
            task = self._subscriptions.pop(battle_id, None)
            if task:
                task.cancel()

    async def set_idle_timer(self, battle_id: int):
        await redis_client.set(_idle_key(battle_id), "1", ex=IDLE_TTL_SECONDS)

    def has_local_connections(self, battle_id: int) -> bool:
        return bool(self.local_sockets.get(battle_id))

    def local_count(self, battle_id: int) -> int:
        return len(self.local_sockets.get(battle_id, {}))

    async def publish(self, battle_id: int, event: dict):
        await redis_client.publish(_channel(battle_id), json.dumps(event))

    async def publish_personal(self, battle_id: int, user_id: int, event: dict):
        tagged = {**event, "_target_user_id": user_id}
        await redis_client.publish(_channel(battle_id), json.dumps(tagged))

    async def _subscribe(self, battle_id: int):
        pubsub = redis_client.pubsub()
        channel = _channel(battle_id)
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                event = json.loads(message["data"])
                target = event.pop("_target_user_id", None)
                sockets = self.local_sockets.get(battle_id, {})

                if target is not None:
                    ws = sockets.get(target)
                    if ws:
                        try:
                            await ws.send_json(event)
                        except RuntimeError:
                            pass
                else:
                    for ws in list(sockets.values()):
                        try:
                            await ws.send_json(event)
                        except RuntimeError:
                            pass
        except asyncio.CancelledError:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
        except Exception as exc:
            logger.error(f"Subscription error for battle {battle_id}: {exc}")


manager = BattleConnectionManager()
