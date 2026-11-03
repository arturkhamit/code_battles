from django.contrib import admin

from apps.submissions.models import Submission


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "battle_id", "user_id", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("user__username",)
    raw_id_fields = ("battle", "user")
