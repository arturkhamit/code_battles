import re

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from apps.battles.models.battle import Battle
from apps.battles.services.create_battle import create_battle

User = get_user_model()


class BattleCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Battle
        fields = ("id", "ranked", "type", "task", "creator", "duration")
        read_only_fields = ("id",)

    def validate(self, attrs):
        if attrs.get("ranked") not in [True, False]:
            raise serializers.ValidationError(
                {"ranked": "Ranked must be a boolean value."}
            )

        if attrs.get("type") not in Battle.Type.values:
            raise serializers.ValidationError({"type": "Invalid battle type."})

        try:
            task = str(attrs.get("task", ""))
            url_regex = re.compile(r"^https?://\S+$", re.IGNORECASE)

            if not bool(url_regex.match(task)):
                raise serializers.ValidationError("Task must be a valid URL.")
        except Exception:
            attrs["task"] = "Temp task"

        return attrs

    def create(self, validated_data):
        creator_instance = validated_data.pop("creator")

        with transaction.atomic():
            battle = create_battle(creator=creator_instance, **validated_data)

            battle.save()

        return battle
