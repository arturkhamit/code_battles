from rest_framework import serializers


class BattleLeaveSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
