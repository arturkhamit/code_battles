from django.contrib import admin

from apps.accounts.models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user_id", "rating", "preferred_language")
    list_filter = ("preferred_language",)
    search_fields = ("user__username", "user__email")
    raw_id_fields = ("user",)
