from django.core.exceptions import ValidationError
from django.db import transaction

from apps.battles.models import Battle, Participant


def leave_battle(user, *, battle):
    try:
        with transaction.atomic():
            participant = Participant.objects.filter(user=user, battle=battle).first()
            if participant:
                participant.delete()
            else:
                raise ValidationError("User is not a participant of this battle")

        return participant

    except Battle.DoesNotExist:
        raise ValidationError("Battle not found")
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f"Unknown error: {e}") from e
