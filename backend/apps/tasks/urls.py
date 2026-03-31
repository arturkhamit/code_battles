from django.urls import path

from apps.tasks.views import TaskView

urlpatterns = [
    path("<int:task_id>/", TaskView.as_view(), name="tasks"),
]
