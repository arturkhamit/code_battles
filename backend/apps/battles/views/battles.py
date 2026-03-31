from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.battles.models import Battle
from apps.battles.permissions import IsInternalService
from apps.battles.serializers.battle_list import BattleListSerializer


class BattlesView(APIView):
    authentication_classes = []
    permission_classes = [IsInternalService]

    def get(self, request, *args, **kwargs):
        battles = Battle.objects.all()
        serializer = BattleListSerializer(battles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
