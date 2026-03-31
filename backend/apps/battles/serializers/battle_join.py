from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.battles.models.battle import Battle
from apps.battles.services.join_battle import join_battle

User = get_user_model()


class BattleJoinSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(write_only=True)
    battle_id = serializers.IntegerField(write_only=True)  # Добавлено поле

    class Meta:
        model = Battle
        fields = (
            "id",
            "user_id",
            "battle_id",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        try:
            user = User.objects.get(id=attrs.pop("user_id"))
            battle = Battle.objects.get(id=attrs.pop("battle_id"))
        except User.DoesNotExist:
            raise serializers.ValidationError(
                f"User {attrs.get('user_id')} does not exist."
            )
        except Battle.DoesNotExist:
            raise serializers.ValidationError(
                f"Battle {attrs.get('battle_id')} does not exist."
            )

        attrs["battle_instance"] = battle
        attrs["user_instance"] = user

        return attrs

    def create(self, validated_data):
        battle_instance = validated_data.pop("battle_instance")
        user_instance = validated_data.pop("user_instance")

        battle = join_battle(
            battle=battle_instance, user=user_instance, **validated_data
        )
        return battle
