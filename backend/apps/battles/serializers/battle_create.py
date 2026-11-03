from rest_framework import serializers

from apps.battles.models.battle import Battle
from apps.battles.services.create_battle import (
    DUEL_PARTICIPANTS,
    MAX_DURATION,
    MAX_GROUP_PARTICIPANTS,
    MIN_DURATION,
    MIN_GROUP_PARTICIPANTS,
    create_battle,
)
from apps.tasks.models import Task


class BattleCreateSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(choices=Battle.Type.choices)
    task = serializers.IntegerField(min_value=1)
    duration = serializers.IntegerField(min_value=MIN_DURATION, max_value=MAX_DURATION)
    # optional: 1v1 is always 2, a group defaults to the maximum
    max_participants = serializers.IntegerField(required=False)
    ranked = serializers.BooleanField(default=False)
    is_private = serializers.BooleanField(default=False)

    class Meta:
        model = Battle
        fields = (
            "id",
            "status",
            "ranked",
            "type",
            "task",
            "creator",
            "duration",
            "max_participants",
            "is_private",
            "invite_code",
            "created_at",
        )
        read_only_fields = ("id", "status", "creator", "invite_code", "created_at")

    def validate_task(self, value):
        if not Task.objects.filter(pk=value).exists():
            raise serializers.ValidationError(f"Task {value} does not exist.")
        return value

    def validate(self, attrs):
        if attrs["type"] == Battle.Type.DUEL:
            attrs["max_participants"] = DUEL_PARTICIPANTS  # whatever the client sent
        else:
            attrs.setdefault("max_participants", MAX_GROUP_PARTICIPANTS)
            if not MIN_GROUP_PARTICIPANTS <= attrs["max_participants"] <= MAX_GROUP_PARTICIPANTS:
                raise serializers.ValidationError(
                    {
                        "max_participants": "A group battle takes "
                        f"{MIN_GROUP_PARTICIPANTS} to {MAX_GROUP_PARTICIPANTS} participants."
                    }
                )
        return attrs

    def create(self, validated_data):  # validated_data includes creator from save(creator=...)
        return create_battle(**validated_data)
