from django.contrib import admin

from apps.tasks.models import Task

TEST_FIELDS = ("public_tests", "private_tests", "generated_tests")


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "difficulty_label", "cf_rating", "source")
    list_filter = ("difficulty_label", "source", "difficulty")
    search_fields = ("name",)
    # the tests are up to megabytes of JSON per task: neither load them nor render them
    exclude = TEST_FIELDS

    def get_queryset(self, request):
        return super().get_queryset(request).defer(*TEST_FIELDS)
