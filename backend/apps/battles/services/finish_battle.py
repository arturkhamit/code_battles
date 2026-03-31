from django.db import transaction
from django.utils import timezone

from apps.battles.models import Battle


def finish_battle(battle, winner_id):

    if battle.status == "finished":
        return battle

    with transaction.atomic():
        battle.winner_id = winner_id
        battle.status = Battle.Status.FINISHED
        battle.end_time = timezone.now()
        battle.save()

        battle.participants.filter().delete()

    return battle
