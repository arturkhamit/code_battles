import logging

from django.db import transaction
from django.utils import timezone

from apps.battles.models import Battle, Participant
from apps.battles.services.common import lock_battle, players_count
from config.exceptions import ConflictError, ForbiddenError

logger = logging.getLogger(__name__)

MIN_PLAYERS = 2  # 1v1 takes exactly two (its capacity), a group at least two


def start_battle(*, battle_id, user_id) -> Battle:
    with transaction.atomic():
        battle = lock_battle(battle_id)

        if battle.creator_id != user_id:
            raise ForbiddenError("Only the battle creator can start the battle.")
        if battle.status != Battle.Status.PENDING:
            raise ConflictError("Battle is not pending, it cannot be started.")
        count = players_count(battle)
        if count < MIN_PLAYERS:
            raise ConflictError(
                f"At least {MIN_PLAYERS} players are needed to start, there are {count}."
            )

        battle.status = Battle.Status.ACTIVE
        battle.start_time = timezone.now()
        battle.save(update_fields=["status", "start_time"])
        battle.participants.update(status=Participant.Status.PLAYING)

    logger.info("Battle %d started by user %d", battle.pk, user_id)
    return battle
