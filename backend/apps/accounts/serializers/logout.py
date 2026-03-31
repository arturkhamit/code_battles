from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class LogoutSerializer(serializers.Serializer):
    username = serializers.CharField()

    def validate(self, attrs):
        user = User.objects.get(username=attrs["username"])

        if not user:
            raise serializers.ValidationError("Could not find user with this username")

        refresh_token = RefreshToken.for_user(user)
        refresh_token.blacklist()

        with transaction.atomic():
            user.is_active = False
            user.save()

        return {"message": "User logged out successfully"}
