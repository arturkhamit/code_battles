from django.db.models import Count, Q
from rest_framework.exceptions import NotFound

from apps.battles.models import Battle, Participant


def lock_battle(battle_id: int) -> Battle:
    """SELECT ... FOR UPDATE of the battle row. Call inside transaction.atomic().

    Every change of a battle or its participants takes this lock first, so the capacity
    check, start and finish of one battle never interleave.
    """
    try:
        return Battle.objects.select_for_update().get(pk=battle_id)
    except Battle.DoesNotExist:
        raise NotFound("Battle not found") from None


def players_count(battle: Battle) -> int:
    """Spectators neither fill a battle nor count towards starting it."""
    return battle.participants.filter(role=Participant.Role.PLAYER).count()


def with_players_count(queryset):
    return queryset.annotate(
        players_count=Count(
            "participants", filter=Q(participants__role=Participant.Role.PLAYER)
        )
    )
