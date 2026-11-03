import hmac
import logging
from typing import NamedTuple

from django.contrib.auth import get_user_model
from django.db import transaction
from infrastructure.messaging.battle_events import notify_battle_joined
from rest_framework.exceptions import NotFound

from apps.battles.models import Battle, Participant
from apps.battles.services.common import lock_battle, players_count
from config.exceptions import ConflictError, ForbiddenError

logger = logging.getLogger(__name__)

User = get_user_model()


class JoinResult(NamedTuple):
    participant: Participant
    battle: Battle
    players_count: int


def join_battle(*, battle_id, user_id, role=None, invite_code=None) -> JoinResult:
    """Let a user into a battle. Idempotent: a participant gets his current role back, so a
    reconnect or a second tab neither adds a row nor turns a player into a spectator.

    role=None: a player while the battle is pending and has room, otherwise a spectator.
    The battle row stays locked until commit, so the last free place goes to exactly one caller.
    """
    with transaction.atomic():
        battle = lock_battle(battle_id)
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            raise NotFound("User not found")
        if battle.status == Battle.Status.FINISHED:
            raise ConflictError("Battle is finished.")

        participant = Participant.objects.filter(battle=battle, user=user).first()
        if participant is None:
            participant = _admit(battle, user, role, invite_code)
        elif participant.status == Participant.Status.DISCONNECTED:
            participant.status = Participant.Status.PLAYING  # back into the running battle
            participant.save(update_fields=["status"])

        count = players_count(battle)
        notify_battle_joined(battle_id=battle.pk, task_id=battle.task, players_count=count)

    logger.info(
        "User %d joined battle %d as %s", user.pk, battle.pk, participant.role
    )
    return JoinResult(participant, battle, count)


def _admit(battle, user, role, invite_code) -> Participant:
    # the creator needs no code, and members never get here (a known participant is returned as is)
    if (
        battle.is_private
        and user.pk != battle.creator_id
        and not (invite_code and hmac.compare_digest(invite_code.encode(), battle.invite_code.encode()))
    ):
        raise ForbiddenError("This battle is private: a valid invite code is required.")

    pending = battle.status == Battle.Status.PENDING
    has_room = pending and players_count(battle) < battle.max_participants
    if role == Participant.Role.PLAYER and not has_room:
        raise ConflictError("Battle is full." if pending else "Battle has already started.")
    if role is None:
        role = Participant.Role.PLAYER if has_room else Participant.Role.SPECTATOR

    return Participant.objects.create(
        battle=battle,
        user=user,
        role=role,
        status=Participant.Status.WAITING if pending else Participant.Status.PLAYING,
    )
