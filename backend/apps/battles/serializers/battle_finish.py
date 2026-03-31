from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.battles.models.battle import Battle
from apps.battles.services.finish_battle import finish_battle

User = get_user_model()


class BattleFinishSerializer(serializers.ModelSerializer):
    battle_id = serializers.IntegerField()
    winner_id = serializers.IntegerField(allow_null=True, required=False)

    class Meta:
        model = Battle
        fields = (
            "battle_id",
            "winner_id",
        )

    def validate(self, attrs):
        battle_id = attrs.pop("battle_id")
        winner_id = attrs.pop("winner_id", None)

        try:
            battle = Battle.objects.get(id=battle_id)
        except Battle.DoesNotExist:
            raise serializers.ValidationError(f"Battle {battle_id} does not exist.")

        if winner_id is not None:
            try:
                User.objects.get(id=winner_id)
            except User.DoesNotExist:
                raise serializers.ValidationError(f"User {winner_id} does not exist.")

        attrs["battle_instance"] = battle
        attrs["winner_id"] = winner_id

        return attrs

    def create(self, validated_data):
        battle_instance = validated_data.pop("battle_instance")

        battle = finish_battle(battle=battle_instance, **validated_data)
        return battle
