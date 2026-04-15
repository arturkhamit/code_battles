from django.db import transaction
from apps.battles.models import Battle


def delete_battle(battle):
    if battle.status != Battle.Status.PENDING:
        return False

    with transaction.atomic():
        battle.participants.all().delete()
        battle.delete()

    return True
