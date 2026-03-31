from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from tests.parse_json import get_json_tasks

from apps.battles.permissions import IsInternalService
from apps.tasks.serializers import TaskImportSerializer

TASKS_STORAGE: list = get_json_tasks()


class TaskView(APIView):
    authentication_classes = []
    permission_classes = [IsInternalService]

    def get(self, request, task_id):
        index = task_id - 1

        if index < 0 or index >= len(TASKS_STORAGE):
            return Response(
                {"error": f"Task {task_id} not found in storage"},
                status=status.HTTP_404_NOT_FOUND,
            )

        task_data = TASKS_STORAGE[index]

        serializer = TaskImportSerializer(data=task_data)

        if not serializer.is_valid():
            return Response(
                {
                    "error": "Кривой формат JSON в этой задаче!",
                    "details": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(serializer.validated_data, status=status.HTTP_200_OK)
