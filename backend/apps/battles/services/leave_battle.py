import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from infrastructure.messaging.battle_events import notify_battle_leaved

from apps.battles.models import Battle, Participant
from apps.battles.services.common import lock_battle, players_count

logger = logging.getLogger(__name__)


def leave_battle(*, battle_id, user_id) -> Battle:
    """pending: the row goes, the place is free again.
    active: the row stays as `disconnected`, a rejoin gets the same role back.
    finished: nothing to do.
    """
    with transaction.atomic():
        battle = lock_battle(battle_id)
        if battle.status == Battle.Status.FINISHED:
            return battle

        participant = Participant.objects.filter(battle=battle, user_id=user_id).first()
        if participant is None:
            raise ValidationError(
                {"user_id": f"User {user_id} is not a participant of this battle."}
            )

        if battle.status == Battle.Status.PENDING:
            participant.delete()
        else:
            participant.status = Participant.Status.DISCONNECTED
            participant.save(update_fields=["status"])

        notify_battle_leaved(battle_id=battle.pk, players_count=players_count(battle))

    logger.info("User %d left battle %d (%s)", user_id, battle.pk, battle.status)
    return battle
