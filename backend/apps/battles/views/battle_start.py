from datetime import timedelta

from infrastructure.messaging.battle_events import notify_battle_started
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.battles.permissions import IsInternalService
from apps.battles.serializers.battle_start import BattleStartSerializer


class BattleStartView(APIView):
    authentication_classes = []
    permission_classes = [IsInternalService]

    def patch(self, request, battle_id):
        data = request.data.copy()
        data["battle_id"] = battle_id

        serializer = BattleStartSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        battle = serializer.save()

        notify_battle_started(battle_id=battle_id, invite_code=battle.invite_code)

        deadline = None
        if battle.start_time and battle.duration:
            end_time = battle.start_time + timedelta(minutes=battle.duration)
            deadline = end_time.timestamp()

        return Response(
            {"status": "success", "deadline": deadline}, status=status.HTTP_200_OK
        )
