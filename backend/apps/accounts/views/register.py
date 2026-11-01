from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.serializers.register import RegisterSerializer
from apps.accounts.throttles import RegisterThrottle


class RegisterView(APIView):
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (RegisterThrottle,)

    def post(self, request, *args, **kwargs):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()  # save the new user to the database
        return Response(serializer.data, status=status.HTTP_201_CREATED)
