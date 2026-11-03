from rest_framework import serializers

from apps.battles.models.participant import Participant


class BattleJoinSerializer(serializers.Serializer):
    """Body of the internal join. FastAPI may send null for what the client did not give."""

    user_id = serializers.IntegerField()
    role = serializers.ChoiceField(
        choices=Participant.Role.choices, required=False, allow_null=True
    )
    invite_code = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
