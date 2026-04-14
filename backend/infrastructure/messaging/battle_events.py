import json

from infrastructure.redis.client import redis_client

BATTLE_CHANNEL = "battle_events"


def publish_event(event_type: str, payload: dict):
    message = {"type": event_type, "data": payload}
    redis_client.publish(BATTLE_CHANNEL, json.dumps(message))


def notify_battle_created(battle_id: int, creator_id: int, invite_code: int):
    publish_event(
        "battle_created",
        {
            "battle_id": battle_id,
            "creator_id": creator_id,
            "invite_code": invite_code,
        },
    )


def notify_battle_joined(
    battle_id: int, task_id: int, max_members: int, participant_id: int, participants: list
):
    publish_event(
        "battle_joined",
        {
            "battle_id": battle_id,
            "task_id": task_id,
            "max_members": max_members,
            "participant": participant_id,
            "participants": participants,
        },
    )


def notify_battle_leaved(battle_id: int, user_id: int, participants: list):
    publish_event(
        "battle_leaved",
        {"battle_id": battle_id, "user_id": user_id, "participants": participants},
    )


def notify_battle_started(battle_id: int, invite_code: int):
    publish_event(
        "battle_started", {"battle_id": battle_id, "invitation_code": invite_code}
    )


def notify_battle_finished(battle_id: int, winner_id: int):
    publish_event("battle_finished", {"battle_id": battle_id, "winner_id": winner_id})
