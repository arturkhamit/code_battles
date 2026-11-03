from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.battles.models import Battle
from apps.battles.permissions import IsInternalService
from apps.battles.serializers.battle_list import BattleListSerializer


class BattlesView(APIView):
    """GET /internal/battles/?status=pending|active|finished"""

    authentication_classes = []
    permission_classes = [IsInternalService]

    def get(self, request, *args, **kwargs):
        battles = Battle.objects.all()
        wanted = request.query_params.get("status")
        if wanted is not None:
            if wanted not in Battle.Status.values:
                raise serializers.ValidationError(
                    {"status": f"Unknown status, expected one of: {', '.join(Battle.Status.values)}."}
                )
            battles = battles.filter(status=wanted)
        serializer = BattleListSerializer(battles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
