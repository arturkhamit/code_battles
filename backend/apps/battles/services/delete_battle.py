import logging

from django.db import transaction

from apps.battles.models import Battle
from apps.battles.services.common import lock_battle
from config.exceptions import ConflictError

logger = logging.getLogger(__name__)


def delete_battle(battle_id):
    """Only an idle pending battle can go; the ORM cascades to participants and submissions."""
    with transaction.atomic():
        battle = lock_battle(battle_id)
        if battle.status != Battle.Status.PENDING:
            logger.warning(
                "Cannot delete battle %d: status is %s (expected pending)",
                battle.pk, battle.status,
            )
            raise ConflictError("Battle is not pending and cannot be deleted")
        battle.delete()

    logger.info("Idle battle %d deleted", battle_id)
