import asyncio
import json
import logging
from contextlib import contextmanager, suppress
from dataclasses import dataclass

from fastapi import WebSocket

from core.tasks import supervise
from infrastructure.redis.client import get_redis

logger = logging.getLogger(__name__)

IDLE_TTL_SECONDS = 300
SUBSCRIBE_TIMEOUT = 5.0
SEND_TIMEOUT = 10.0  # one stuck client must not hold up the others

WS_REPLACED = 4001


def _channel(battle_id: int) -> str:
    return f"battle:{battle_id}:events"


def _idle_key(battle_id: int) -> str:
    return f"battle:{battle_id}:idle_ttl"


@dataclass(eq=False)
class Conn:
    """One accepted socket of a confirmed participant."""

    ws: WebSocket
    battle_id: int
    user_id: int
    username: str
    role: str  # player | spectator, as confirmed by Django
    task_id: int | None
    replaced: bool = False  # closed by a newer socket of the same user: no leave, no user_left


class BattleConnectionManager:
    # shortcut: sockets and subscriptions live in this process, so the replace rule
    # (one socket per battle+user) holds per process; the deployment runs one worker (DK-3).
    def __init__(self):
        self.local_sockets: dict[int, dict[int, Conn]] = {}
        self._subscriptions: dict[int, asyncio.Task] = {}
        self._ready: dict[int, asyncio.Event] = {}
        self._joining: dict[tuple[int, int], int] = {}

    @contextmanager
    def joining(self, battle_id: int, user_id: int):
        """Marks a join in flight: a socket of the same user closing right now must not send
        Django a leave that would remove the participant this join has just (re)confirmed."""
        key = (battle_id, user_id)
        self._joining[key] = self._joining.get(key, 0) + 1
        try:
            yield
        finally:
            self._joining[key] -= 1
            if not self._joining[key]:
                del self._joining[key]

    def user_present(self, battle_id: int, user_id: int) -> bool:
        return user_id in self.local_sockets.get(battle_id, {}) or (battle_id, user_id) in self._joining

    async def register(self, conn: Conn) -> None:
        """Make `conn` the socket of its (battle, user), then wait until the battle channel is
        subscribed, so nothing published after this call is missed."""
        sockets = self.local_sockets.setdefault(conn.battle_id, {})
        old = sockets.get(conn.user_id)
        sockets[conn.user_id] = conn
        if old is not None:
            old.replaced = True
            with suppress(Exception):  # the old socket may already be closed
                await old.ws.close(code=WS_REPLACED, reason="replaced")
        try:
            await self._ensure_subscription(conn.battle_id)
            await get_redis().delete(_idle_key(conn.battle_id))
        except BaseException:
            self.unregister(conn)
            raise

    def unregister(self, conn: Conn) -> None:
        sockets = self.local_sockets.get(conn.battle_id)
        # a replaced socket must not remove the one that replaced it
        if not sockets or sockets.get(conn.user_id) is not conn:
            return
        del sockets[conn.user_id]
        if not sockets:
            del self.local_sockets[conn.battle_id]
            self._ready.pop(conn.battle_id, None)
            task = self._subscriptions.pop(conn.battle_id, None)
            if task:
                task.cancel()

    async def set_idle_timer(self, battle_id: int):
        await get_redis().set(_idle_key(battle_id), "1", ex=IDLE_TTL_SECONDS)

    def has_local_connections(self, battle_id: int) -> bool:
        return bool(self.local_sockets.get(battle_id))

    async def publish(self, battle_id: int, event: dict):
        await get_redis().publish(_channel(battle_id), json.dumps(event))

    async def publish_personal(self, battle_id: int, user_id: int, event: dict):
        tagged = {**event, "_target_user_id": user_id}
        await get_redis().publish(_channel(battle_id), json.dumps(tagged))

    async def shutdown(self) -> None:
        tasks = list(self._subscriptions.values())
        self._subscriptions.clear()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _ensure_subscription(self, battle_id: int) -> None:
        task = self._subscriptions.get(battle_id)
        if task is None or task.done():
            ready = self._ready[battle_id] = asyncio.Event()
            self._subscriptions[battle_id] = asyncio.create_task(
                supervise(
                    f"subscription of battle {battle_id}",
                    lambda: self._listen(battle_id, ready),
                ),
                name=f"battle-{battle_id}-subscription",
            )
        await asyncio.wait_for(self._ready[battle_id].wait(), SUBSCRIBE_TIMEOUT)

    async def _listen(self, battle_id: int, ready: asyncio.Event) -> None:
        """One Redis connection's worth of listening; supervise() restarts it after a failure,
        so a Redis restart costs a re-subscribe with backoff, not the battle."""
        pubsub = get_redis().pubsub()
        try:
            await pubsub.subscribe(_channel(battle_id))
            ready.set()
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await self._dispatch(battle_id, message["data"])
        finally:
            with suppress(Exception):
                await pubsub.aclose()

    async def _dispatch(self, battle_id: int, raw: str) -> None:
        try:
            event = json.loads(raw)
            target = event.pop("_target_user_id", None)
        except (ValueError, AttributeError):
            logger.warning("Dropped a malformed event", extra={"battle_id": battle_id})
            return

        sockets = self.local_sockets.get(battle_id, {})
        if target is None:
            conns = list(sockets.values())
        else:
            conns = [sockets[target]] if target in sockets else []
        await asyncio.gather(*(self._send(c, event) for c in conns))

    async def _send(self, conn: Conn, event: dict) -> None:
        try:
            await asyncio.wait_for(conn.ws.send_json(event), SEND_TIMEOUT)
        except Exception as exc:  # a dead or stuck socket must not break the fan-out
            logger.warning(
                "Send to user failed: %s", type(exc).__name__,
                extra={"battle_id": conn.battle_id, "user_id": conn.user_id},
            )


manager = BattleConnectionManager()
