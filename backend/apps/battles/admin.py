from django.contrib import admin

from apps.battles.models import Battle, Participant


@admin.register(Battle)
class BattleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "type",
        "status",
        "ranked",
        "creator_id",
        "task",
        "max_participants",
        "created_at",
    )
    list_filter = ("status", "type", "ranked")
    search_fields = ("invite_code", "creator__username")
    raw_id_fields = ("creator", "winner")
    ordering = ("-id",)


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ("id", "battle_id", "user_id", "role", "status", "score")
    list_filter = ("status", "role")
    search_fields = ("user__username",)
    raw_id_fields = ("battle", "user")
    ordering = ("-id",)
