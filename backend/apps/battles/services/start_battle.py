import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.battles.models import Battle, Participant

logger = logging.getLogger(__name__)


def start_battle(user, *, battle):

    if user.id != battle.creator_id:
        raise ValidationError("Only the battle creator can start the battle")
    if battle.type == "1v1" and battle.participants.count() > 2:
        raise ValidationError("Too many participants to start the 1v1 battle")

    with transaction.atomic():
        battle.status = Battle.Status.ACTIVE
        battle.start_time = timezone.now()
        battle.save()

        participants = battle.participants.filter()
        for participant in participants:
            participant.status = Participant.Status.PLAYING
            participant.save()

    logger.info("Battle %d started by user %d", battle.pk, user.pk)
    return battle
