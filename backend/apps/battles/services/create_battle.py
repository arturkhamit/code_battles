import logging

from django.db import IntegrityError, transaction

from apps.battles.models import Battle
from config.exceptions import ConflictError

logger = logging.getLogger(__name__)

# Game rules, enforced by BattleCreateSerializer. Duration is in minutes everywhere.
MIN_DURATION = 5
MAX_DURATION = 120
DUEL_PARTICIPANTS = 2
MIN_GROUP_PARTICIPANTS = 2
MAX_GROUP_PARTICIPANTS = 10

INVITE_CODE_ATTEMPTS = 5


def create_battle(
    creator, *, ranked, type, duration, task, max_participants, is_private
):
    for _ in range(INVITE_CODE_ATTEMPTS):
        battle = Battle(  # invite_code comes from the model default
            creator=creator,
            type=type,
            duration=duration,
            task=task,
            status=Battle.Status.PENDING,
            ranked=ranked,
            max_participants=max_participants,
            is_private=is_private,
        )
        try:
            with transaction.atomic():  # savepoint: a collision keeps an outer transaction usable
                battle.save()
        except IntegrityError:
            if Battle.objects.filter(invite_code=battle.invite_code).exists():
                continue  # the code is taken: roll another one
            raise

        logger.info(
            "Battle %d created by user %d (type=%s, duration=%s, task=%s, private=%s)",
            battle.pk, creator.pk, type, duration, task, is_private,
        )
        return battle

    raise ConflictError("Could not generate a unique invite code, try again.")
