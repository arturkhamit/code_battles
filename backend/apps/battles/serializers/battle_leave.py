from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.battles.models.battle import Battle
from apps.battles.services.leave_battle import leave_battle

User = get_user_model()


class BattleLeaveSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(write_only=True)
    battle_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = Battle
        fields = (
            "id",
            "battle_id",
            "user_id",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        user_id = attrs.pop("user_id")
        battle_id = attrs.pop("battle_id")

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"user_id": f"User {user_id} does not exist."}
            )

        try:
            battle = Battle.objects.get(id=battle_id)
        except Battle.DoesNotExist:
            raise serializers.ValidationError(
                {"battle_id": f"Battle {battle_id} does not exist."}
            )

        is_participant = battle.participants.filter(user_id=user_id).exists()

        if not is_participant:
            raise serializers.ValidationError(
                {"user_id": "This user is not a participant of this battle."}
            )

        attrs["battle_instance"] = battle
        attrs["user_instance"] = user

        return attrs

    def create(self, validated_data):
        battle_instance = validated_data.pop("battle_instance")
        user_instance = validated_data.pop("user_instance")

        battle = leave_battle(
            user=user_instance, battle=battle_instance, **validated_data
        )
        return battle
