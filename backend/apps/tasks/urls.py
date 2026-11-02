from django.urls import path

from apps.tasks.views import TaskDetailView, TaskFacetsView, TaskListView

urlpatterns = [
    path("facets/", TaskFacetsView.as_view(), name="task-facets"),
    path("<int:task_id>/", TaskDetailView.as_view(), name="task-detail"),
    path("", TaskListView.as_view(), name="task-list"),
]
