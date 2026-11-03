from datetime import timedelta

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.battles.permissions import IsInternalService
from apps.battles.serializers.battle_start import BattleStartSerializer
from apps.battles.services.start_battle import start_battle


class BattleStartView(APIView):
    """PATCH /internal/battles/start/<id>/  {"user_id"}

    200 {status: "success", deadline: epoch seconds}. 403 not the creator; 404 unknown battle;
    409 not pending (a second start keeps start_time) or fewer than 2 players.
    """

    authentication_classes = []
    permission_classes = [IsInternalService]

    def patch(self, request, battle_id):
        serializer = BattleStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        battle = start_battle(battle_id=battle_id, **serializer.validated_data)

        deadline = None
        if battle.start_time and battle.duration:
            end_time = battle.start_time + timedelta(minutes=battle.duration)  # duration: minutes
            deadline = end_time.timestamp()

        return Response(
            {"status": "success", "deadline": deadline}, status=status.HTTP_200_OK
        )
