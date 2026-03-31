from infrastructure.messaging.battle_events import notify_battle_finished
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.battles.permissions import IsInternalService
from apps.battles.serializers.battle_finish import BattleFinishSerializer


class BattleFinishView(APIView):
    authentication_classes = []
    permission_classes = [IsInternalService]

    def patch(self, request, battle_id):
        data = request.data.copy()
        data["battle_id"] = battle_id

        serializer = BattleFinishSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        battle = serializer.save()

        notify_battle_finished(battle_id=battle_id, winner_id=battle.winner_id)

        return Response({"status": "success"}, status=status.HTTP_200_OK)
