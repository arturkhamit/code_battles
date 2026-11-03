from rest_framework import serializers


class BattleFinishSerializer(serializers.Serializer):
    # the key is required: null is a draw, a missing key is a client bug, not a result
    winner_id = serializers.IntegerField(allow_null=True)
