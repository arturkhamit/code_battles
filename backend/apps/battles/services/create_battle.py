from django.core.exceptions import ValidationError
from django.db import transaction

from apps.battles.models import Battle

ALLOWED_TYPES = {Battle.Type.DUEL}


def create_battle(creator, *, ranked, type, duration, task):

    if type not in ALLOWED_TYPES:
        raise ValidationError("Unsupported battle type")

    if duration <= 0 or duration > 60 * 60:
        raise ValidationError("Invalid duration")

    if not task:
        raise ValidationError("Task is required")

    if not creator:
        raise ValidationError("User not found")
    invite_code = _generate_invite_code()

    with transaction.atomic():
        battle = Battle.objects.create(
            creator=creator,
            type=type,
            duration=duration,
            task=task,
            status=Battle.Status.PENDING,
            invite_code=invite_code,
            ranked=ranked,
            # is_private=is_private,
        )

    return battle


def _generate_invite_code():
    import secrets

    return secrets.token_urlsafe(4)  # length == 6
