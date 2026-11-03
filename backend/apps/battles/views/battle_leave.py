from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.battles.permissions import IsInternalService
from apps.battles.serializers.battle_leave import BattleLeaveSerializer
from apps.battles.services.common import players_count
from apps.battles.services.leave_battle import leave_battle


class BattleLeaveView(APIView):
    """PATCH /internal/battles/leave/<id>/  {"user_id"}

    200 {battle_status, players_count}: pending deletes the participant, active marks him
    `disconnected`, finished changes nothing. 400 not a participant; 404 unknown battle.
    """

    authentication_classes = []
    permission_classes = [IsInternalService]

    def patch(self, request, battle_id):
        serializer = BattleLeaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        battle = leave_battle(battle_id=battle_id, **serializer.validated_data)

        return Response(
            {"battle_status": battle.status, "players_count": players_count(battle)},
            status=status.HTTP_200_OK,
        )
