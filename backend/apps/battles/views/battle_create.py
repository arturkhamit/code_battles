from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.battles.serializers.battle_create import BattleCreateSerializer
from apps.battles.throttles import BattleCreateThrottle


class BattleCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [BattleCreateThrottle]

    def post(self, request):
        serializer = BattleCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(creator=request.user)

        return Response(serializer.data, status=status.HTTP_201_CREATED)
