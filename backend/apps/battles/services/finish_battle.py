import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.battles.models import Battle, Participant
from apps.battles.services.common import lock_battle
from config.exceptions import ConflictError

logger = logging.getLogger(__name__)


def finish_battle(*, battle_id, winner_id) -> Battle:
    """winner_id=None is a draw. Participants stay: they are the history of the battle.

    FastAPI retries a lost answer, so a repeat with the same result is a no-op and a repeat
    with another one is a conflict.
    """
    with transaction.atomic():
        battle = lock_battle(battle_id)

        if battle.status == Battle.Status.FINISHED:
            if battle.winner_id != winner_id:
                raise ConflictError("Battle is already finished with another result.")
            logger.info("Battle %d already finished with this result, skipping", battle.pk)
            return battle

        if winner_id is not None and not battle.participants.filter(
            user_id=winner_id, role=Participant.Role.PLAYER
        ).exists():
            raise ValidationError(
                {"winner_id": f"User {winner_id} is not a player of this battle."}
            )

        battle.winner_id = winner_id
        battle.status = Battle.Status.FINISHED
        battle.end_time = timezone.now()
        battle.save(update_fields=["winner", "status", "end_time"])
        battle.participants.update(status=Participant.Status.FINISHED)

    logger.info("Battle %d finished. Winner: %s", battle.pk, winner_id)
    return battle
