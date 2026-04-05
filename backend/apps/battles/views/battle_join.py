from infrastructure.messaging.battle_events import notify_battle_joined
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.battles.permissions import IsInternalService
from apps.battles.serializers.battle_join import BattleJoinSerializer


class BattleJoinView(APIView):
    authentication_classes = []
    permission_classes = [IsInternalService]

    def patch(self, request, battle_id):
        data = request.data.copy()
        data["battle_id"] = battle_id

        serializer = BattleJoinSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        participant = serializer.save()
        battle = participant.battle

        notify_battle_joined(
            battle_id=battle_id,
            task_id=battle.task,
            participant_id=participant.user.id,
            participants=list(
                battle.participants.all().values_list("user_id", flat=True)
            ),
        )

        return Response(serializer.data, status=status.HTTP_200_OK)
