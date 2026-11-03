from rest_framework import serializers


class BattleStartSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
