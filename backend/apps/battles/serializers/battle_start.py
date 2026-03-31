from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.battles.models.battle import Battle
from apps.battles.services.start_battle import start_battle

User = get_user_model()


class BattleStartSerializer(serializers.ModelSerializer):
    battle_id = serializers.IntegerField()
    user_id = serializers.IntegerField()

    class Meta:
        model = Battle
        fields = (
            "battle_id",
            "user_id",
        )

    def validate(self, attrs):
        try:
            user = User.objects.get(id=attrs["user_id"])
            battle = Battle.objects.get(id=attrs["battle_id"])
        except User.DoesNotExist:
            raise serializers.ValidationError(
                f"User {attrs['user_id']} does not exist."
            )
        except Battle.DoesNotExist:
            raise serializers.ValidationError(
                f"Battle {attrs['battle_id']} does not exist."
            )

        attrs["battle_instance"] = battle
        attrs["user_instance"] = user

        return attrs

    def create(self, validated_data):
        battle_instance = validated_data.pop("battle_instance")
        user_instance = validated_data.pop("user_instance")

        battle = start_battle(user=user_instance, battle=battle_instance)
        return battle
