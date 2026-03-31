from infrastructure.messaging.battle_events import notify_battle_leaved
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.battles.permissions import IsInternalService
from apps.battles.serializers.battle_leave import BattleLeaveSerializer


class BattleLeaveView(APIView):
    authentication_classes = []
    permission_classes = [IsInternalService]

    def patch(self, request, battle_id):
        data = request.data.copy()
        data["battle_id"] = battle_id

        serializer = BattleLeaveSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        participant = serializer.save()
        battle = participant.battle

        user_id = serializer.validated_data.get("user_id")

        notify_battle_leaved(
            battle_id=battle_id,
            user_id=user_id,
            participants=list(
                battle.participants.all().values_list("user_id", flat=True)
            ),
        )

        return Response(serializer.data, status=status.HTTP_200_OK)
