from infrastructure.messaging.battle_events import notify_battle_created
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.battles.serializers.battle_create import BattleCreateSerializer


class BattleCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data.copy()
        data["creator"] = request.user.id

        serializer = BattleCreateSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        battle = serializer.save()

        notify_battle_created(
            battle_id=battle.id,
            creator_id=battle.creator.id,
            invite_code=battle.invite_code,
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)