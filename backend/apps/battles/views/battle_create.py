from infrastructure.messaging.battle_events import notify_battle_created
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.battles.permissions import IsInternalService
from apps.battles.serializers.battle_create import BattleCreateSerializer


class BattleCreateView(APIView):
    authentication_classes = []
    permission_classes = [IsInternalService]

    def post(self, request):

        serializer = BattleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        battle = serializer.save()

        notify_battle_created(
            battle_id=battle.id,
            creator_id=battle.creator.id,
            invite_code=battle.invite_code,
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)
