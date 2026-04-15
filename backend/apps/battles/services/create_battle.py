import logging
import secrets

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.battles.models import Battle

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {Battle.Type.DUEL, Battle.Type.GROUP}


def create_battle(creator, *, ranked, type, duration, task, max_participants):

    if type not in ALLOWED_TYPES:
        raise ValidationError("Unsupported battle type")

    if duration <= 0 or duration > 60 * 60:
        raise ValidationError("Invalid duration")

    if not task:
        raise ValidationError("Task is required")

    if not creator:
        raise ValidationError("User not found")

    if type == Battle.Type.GROUP and max_participants <= 2:
        raise ValidationError("Group battles require at least 2 participants")
    invite_code = secrets.token_urlsafe(4)

    with transaction.atomic():
        battle = Battle.objects.create(
            creator=creator,
            type=type,
            duration=duration,
            task=task,
            status=Battle.Status.PENDING,
            invite_code=invite_code,
            ranked=ranked,
            max_participants=max_participants,
        )

    logger.info(
        "Battle %d created by user %d (type=%s, duration=%s, task=%s)",
        battle.pk, creator.pk, type, duration, task,
    )
    return battle