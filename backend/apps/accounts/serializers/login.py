from django.contrib.auth import authenticate
from django.contrib.auth.models import update_last_login
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(username=attrs["username"], password=attrs["password"])

        if not user:
            raise AuthenticationFailed("Invalid credentials")  # 401, not 400

        update_last_login(None, user)

        refresh = RefreshToken.for_user(user)

        # TEMPORAIRLY:
        refresh["username"] = user.username
        refresh["email"] = user.email

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }
