from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate(self, attrs):
        refresh_token = attrs["refresh"]

        try:
            refresh = RefreshToken(refresh_token)
        except TokenError:
            raise serializers.ValidationError(
                {"refresh": "Invalid or expired refresh token"}
            )

        return {"access": str(refresh.access_token)}
