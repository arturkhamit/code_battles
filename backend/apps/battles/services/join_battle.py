from django.core.exceptions import ValidationError
from django.db import transaction

from apps.battles.models import Battle, Participant


def join_battle(user, *, battle):
    try:
        if battle.type == "1v1" and battle.participants.count() >= 2:
            raise ValidationError("Battle is full")

        with transaction.atomic():
            participant = Participant.objects.create(
                battle=battle,
                user=user,
                role=Participant.Role.PLAYER,
            )

        return participant

    except Battle.DoesNotExist:
        raise ValidationError("Battle not found")
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f"Unknown error: {e}") from e
