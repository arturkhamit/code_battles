import json
import logging

from infrastructure.redis.client import redis_client

logger = logging.getLogger(__name__)


def _channel(battle_id: int) -> str:
    return f"battle:{battle_id}:events"


def publish_event(battle_id: int, event: dict):
    channel = _channel(battle_id)
    redis_client.publish(channel, json.dumps(event))
    logger.debug("Published event to %s: %s", channel, event.get("event"))


def notify_battle_created(battle_id: int, creator_id: int, invite_code: int):
    publish_event(
        battle_id,
        {
            "event": "battle_created",
            "data": {
                "battle_id": battle_id,
                "creator_id": creator_id,
                "invite_code": invite_code,
            },
        },
    )


def notify_battle_joined(
    battle_id: int,
    task_id: int,
    max_participants: int,
    participant_id: int,
    participants: list,
):
    publish_event(
        battle_id,
        {
            "event": "lobby_update",
            "data": {
                "participants_count": len(participants),
                "task_id": task_id,
            },
        },
    )


def notify_battle_leaved(battle_id: int, user_id: int, participants: list):
    publish_event(
        battle_id,
        {
            "event": "lobby_update",
            "data": {
                "participants_count": len(participants),
            },
        },
    )


def notify_battle_started(battle_id: int, invite_code: int):
    publish_event(
        battle_id,
        {
            "event": "battle_started_notification",
            "data": {"battle_id": battle_id, "invite_code": invite_code},
        },
    )


def notify_battle_finished(battle_id: int, winner_id: int):
    publish_event(
        battle_id,
        {
            "event": "battle_finished_notification",
            "data": {"battle_id": battle_id, "winner_id": winner_id},
        },
    )