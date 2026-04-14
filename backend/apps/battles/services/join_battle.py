from django.core.exceptions import ValidationError
from django.db import transaction

from apps.battles.models import Battle, Participant


def join_battle(user, *, battle):
    role = Participant.Role.PLAYER
    try:
        if battle.type == "1v1" and battle.participants.count() >= battle.max_participants:
            raise ValidationError("Battle is full")
        if battle.status == "active":
            role = Participant.Role.SPECTATOR
        
        with transaction.atomic():
            participant = Participant.objects.create(
                battle=battle,
                user=user,
                role=role,
            )

        return participant

    except Battle.DoesNotExist:
        raise ValidationError("Battle not found")
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f"Unknown error: {e}") from e
