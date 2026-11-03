from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.battles.permissions import IsInternalService
from apps.battles.serializers.battle_finish import BattleFinishSerializer
from apps.battles.services.finish_battle import finish_battle


class BattleFinishView(APIView):
    """PATCH /internal/battles/finish/<id>/  {"winner_id": int | null}  (null: a draw)

    200 {status: "success"}, also for a repeat with the same winner. 400 winner is not a
    player of the battle, or the key is missing; 404 unknown battle;
    409 already finished with another result.
    """

    authentication_classes = []
    permission_classes = [IsInternalService]

    def patch(self, request, battle_id):
        serializer = BattleFinishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        finish_battle(battle_id=battle_id, **serializer.validated_data)

        return Response({"status": "success"}, status=status.HTTP_200_OK)
