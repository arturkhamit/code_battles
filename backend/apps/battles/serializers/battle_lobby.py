"""Output of the public lobby endpoints (battles/open/, battles/invite/<code>/).

The task of a battle is a plain number, so the view loads the tasks of the page in one query
(TASK_BRIEF_FIELDS: never the megabytes of tests) and passes them as context["tasks"].
"""

from rest_framework import serializers

from apps.battles.models import Battle

TASK_BRIEF_FIELDS = ("id", "name", "difficulty_label")


def task_brief(task_id, tasks):
    task = tasks.get(task_id)  # None only if the task row was deleted
    return {
        "id": task_id,
        "name": task.name if task else None,
        "difficulty_label": task.difficulty_label if task else "unknown",
    }


class OpenBattleSerializer(serializers.ModelSerializer):
    task = serializers.SerializerMethodField()
    duration = serializers.IntegerField(read_only=True)  # minutes; the column is a float
    players_count = serializers.IntegerField(read_only=True)  # annotated by the view
    creator_username = serializers.CharField(source="creator.username", read_only=True)

    class Meta:
        model = Battle
        fields = (
            "id",
            "type",
            "task",
            "duration",
            "max_participants",
            "players_count",
            "creator_username",
            "created_at",
            "invite_code",  # only public battles are listed, so it is never a secret here
        )

    def get_task(self, battle):
        return task_brief(battle.task, self.context["tasks"])


class BattleInviteSerializer(serializers.ModelSerializer):
    task = serializers.SerializerMethodField()
    players_count = serializers.IntegerField(read_only=True)  # annotated by the view

    class Meta:
        model = Battle
        fields = (
            "id",
            "type",
            "status",
            "task",
            "players_count",
            "max_participants",
            "is_private",
        )

    def get_task(self, battle):
        return task_brief(battle.task, self.context["tasks"])
