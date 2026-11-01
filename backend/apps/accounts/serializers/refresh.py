from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer


class RefreshSerializer(TokenRefreshSerializer):
    """simplejwt's refresh with rotation (SIMPLE_JWT): returns a new access AND a new refresh
    token and blacklists the one that was sent. Errors keep this API's 400 field format."""

    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except (TokenError, ObjectDoesNotExist) as exc:  # bad token / user is gone
            raise serializers.ValidationError(
                {"refresh": "Invalid or expired refresh token"}
            ) from exc
