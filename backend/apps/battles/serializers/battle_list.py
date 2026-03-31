from django.db.models import Q
from rest_framework import serializers

from apps.battles.models import Battle


class BattleListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Battle
        exclude = ("id", "creator", "invite_code")

    def validate(self, attrs):

        if attrs["status"] not in Battle.Status:
            raise serializers.ValidationError(
                {"status": "This status of battle doesn't exist"}
            )

        return attrs

    def create(self, validated_data):
        return Battle.objects.filter(
            Q(status=validated_data["status"])  # | Q(status="finished")
        )
