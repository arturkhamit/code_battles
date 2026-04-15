from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.battles.models import Battle
from apps.battles.permissions import IsInternalService
from apps.battles.services.delete_battle import delete_battle


class BattleDeleteView(APIView):
    authentication_classes = []
    permission_classes = [IsInternalService]

    def delete(self, request, battle_id):
        try:
            battle = Battle.objects.get(pk=battle_id)
        except Battle.DoesNotExist:
            return Response(
                {"detail": "Battle not found"}, status=status.HTTP_404_NOT_FOUND
            )

        deleted = delete_battle(battle)

        if not deleted:
            return Response(
                {"detail": "Battle is not pending and cannot be deleted"},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)
