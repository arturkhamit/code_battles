from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate(self, attrs):
        try:
            token = RefreshToken(attrs["refresh"])
            token.blacklist()
        except TokenError:
            raise serializers.ValidationError(
                {"refresh": "Token is invalid or already blacklisted"}
            )

        return {"message": "User logged out successfully"}
