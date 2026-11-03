from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.battles.permissions import IsInternalService
from apps.battles.services.delete_battle import delete_battle


class BattleDeleteView(APIView):
    authentication_classes = []
    permission_classes = [IsInternalService]

    def delete(self, request, battle_id):
        delete_battle(battle_id)  # 404 if unknown, 409 if not pending

        return Response(status=status.HTTP_204_NO_CONTENT)
