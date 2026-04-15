import logging

from django.db import connection, transaction

from apps.battles.models import Battle

logger = logging.getLogger(__name__)


def delete_battle(battle):
    if battle.status != Battle.Status.PENDING:
        logger.warning(
            "Cannot delete battle %d: status is %s (expected pending)",
            battle.pk, battle.status,
        )
        return False

    with transaction.atomic():
        battle.participants.all().delete()
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM battles_battle WHERE id = %s", [battle.pk]
            )

    logger.info("Idle battle %d deleted", battle.pk)
    return True
