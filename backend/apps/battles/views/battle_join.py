from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.battles.permissions import IsInternalService
from apps.battles.serializers.battle_join import BattleJoinSerializer
from apps.battles.services.join_battle import join_battle


class BattleJoinView(APIView):
    """PATCH /internal/battles/join/<id>/  {"user_id", "role"?: "player"|"spectator", "invite_code"?}

    200 {id, role, status, battle_status, type, max_participants, players_count, task_id,
         creator_id, creator_username, duration (minutes)};
    a user who is already in the battle gets 200 with the role he has.
    403 private battle without the right invite_code; 404 unknown battle or user;
    409 battle finished, or role=player on a full / started battle; 400 bad body.
    """

    authentication_classes = []
    permission_classes = [IsInternalService]

    def patch(self, request, battle_id):
        serializer = BattleJoinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        participant, battle, players = join_battle(
            battle_id=battle_id, **serializer.validated_data
        )

        return Response(
            {
                "id": participant.pk,
                "role": participant.role,
                "status": participant.status,
                "battle_status": battle.status,
                "type": battle.type,
                "max_participants": battle.max_participants,
                "players_count": players,
                "task_id": battle.task,
                "creator_id": battle.creator_id,
                "creator_username": battle.creator.username,
                "duration": battle.duration,
            },
            status=status.HTTP_200_OK,
        )
