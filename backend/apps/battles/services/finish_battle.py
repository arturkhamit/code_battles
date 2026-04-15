import logging

from django.db import transaction
from django.utils import timezone

from apps.battles.models import Battle

logger = logging.getLogger(__name__)


def finish_battle(battle, winner_id):

    if battle.status == "finished":
        logger.warning("Battle %d already finished, skipping", battle.pk)
        return battle

    with transaction.atomic():
        battle.winner_id = winner_id
        battle.status = Battle.Status.FINISHED
        battle.end_time = timezone.now()
        battle.save()

        battle.participants.filter().delete()

    logger.info("Battle %d finished. Winner: %s", battle.pk, winner_id)
    return battle