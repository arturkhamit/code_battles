"""Django -> WebSocket clients through Redis pub/sub (`battle:{id}:events`).

Only events the frontend knows (frontend/src/types/ws.ts) are sent from here. FastAPI sends the
others itself: battle_started, battle_finished (with winner_username, a draw has null), ...

Events are best-effort and leave after the transaction commits: a rolled back change is never
announced, and a Redis outage cannot fail (or half-undo) a request that already changed the DB.
"""

import json
import logging
from functools import partial

from django.db import transaction
from infrastructure.redis.client import redis_client

logger = logging.getLogger(__name__)


def _channel(battle_id: int) -> str:
    return f"battle:{battle_id}:events"


def publish_event(battle_id: int, event: dict):
    channel = _channel(battle_id)
    try:
        redis_client.publish(channel, json.dumps(event))
    except Exception as exc:
        logger.warning("Could not publish %s to %s: %s", event.get("event"), channel, exc)
        return
    logger.debug("Published event to %s: %s", channel, event.get("event"))


def _publish_on_commit(battle_id: int, event: dict):
    # outside a transaction on_commit runs the callback at once
    transaction.on_commit(partial(publish_event, battle_id, event))


def notify_battle_joined(battle_id: int, task_id: int, players_count: int):
    """Also sent when a known participant reconnects: a new socket learns the task from it."""
    _publish_on_commit(
        battle_id,
        {
            "event": "lobby_update",
            "data": {"participants_count": players_count, "task_id": task_id},
        },
    )


def notify_battle_leaved(battle_id: int, players_count: int):
    _publish_on_commit(
        battle_id,
        {"event": "lobby_update", "data": {"participants_count": players_count}},
    )
