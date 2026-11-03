import re
from datetime import timedelta

from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.generics import ListAPIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.battles.models import Battle
from apps.battles.serializers.battle_lobby import (
    TASK_BRIEF_FIELDS,
    BattleInviteSerializer,
    OpenBattleSerializer,
)
from apps.battles.services.common import with_players_count
from apps.battles.throttles import InviteLookupThrottle
from apps.tasks.models import Task

INVITE_CODE_RE = re.compile(r"[A-Za-z0-9_-]{1,6}")  # what generate_invite_code makes
# A lobby nobody ever opened over WS gets no idle timer; hide it, expire_pending_battles deletes it.
OPEN_LOBBY_MAX_AGE = timedelta(minutes=30)


class OpenBattlesPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 50


class OpenBattlesView(ListAPIView):
    """GET /api/battles/open/?limit=&offset=

    Public lobbies that can still be joined as a player: pending, not private, not full,
    younger than OPEN_LOBBY_MAX_AGE. Newest first. Answer: {count, next, previous, results}.
    """

    pagination_class = OpenBattlesPagination
    serializer_class = OpenBattleSerializer

    def get_queryset(self):
        return (
            with_players_count(
                Battle.objects.filter(
                    status=Battle.Status.PENDING,
                    is_private=False,
                    created_at__gte=timezone.now() - OPEN_LOBBY_MAX_AGE,
                )
            )
            .filter(players_count__lt=F("max_participants"))
            .select_related("creator")
            .order_by("-created_at", "-id")
        )

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        tasks = Task.objects.only(*TASK_BRIEF_FIELDS).in_bulk({b.task for b in page})
        data = OpenBattleSerializer(page, many=True, context={"tasks": tasks}).data
        return self.get_paginated_response(data)


class BattleInviteView(APIView):
    """GET /api/battles/invite/<code>/ -> summary of the battle that has this code.

    Private battles answer too: knowing the code is the key. The lookup is throttled
    so that codes cannot be guessed.
    """

    throttle_classes = [InviteLookupThrottle]

    def get(self, request, code):
        battle = None
        if INVITE_CODE_RE.fullmatch(code):  # anything else cannot be a code (and may not be a valid query value)
            battle = with_players_count(Battle.objects.filter(invite_code=code)).first()
        if battle is None:
            raise NotFound("No battle has this invite code.")

        tasks = Task.objects.only(*TASK_BRIEF_FIELDS).in_bulk([battle.task])
        return Response(BattleInviteSerializer(battle, context={"tasks": tasks}).data)
