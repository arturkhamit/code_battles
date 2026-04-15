from fastapi import APIRouter, Depends, HTTPException

from core.auth import get_current_user
from schemas.submission import CodeSubmission
from services.code_executor import execute_and_test_code
from services.django_callbacks import fetch_task_from_django

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("/{task_id}/info")
async def get_task_info(task_id: int, _user: dict = Depends(get_current_user)):
    task_data = await fetch_task_from_django(task_id)

    if not task_data:
        raise HTTPException(status_code=404, detail="Couldnt find the task")

    return {
        "id": task_id,
        "name": task_data.get("name"),
        "description": task_data.get("description"),
        "time_limit": task_data.get("time_limit"),
        "memory_limit_bytes": task_data.get("memory_limit_bytes"),
        "public_tests": task_data.get("public_tests", {"input": [], "output": []}),
    }


@router.post("/{task_id}/submit")
async def submit_code(
    task_id: int,
    submission: CodeSubmission,
    _user: dict = Depends(get_current_user),
):
    task_data = await fetch_task_from_django(task_id)

    if not task_data:
        raise HTTPException(status_code=404, detail="Couldnt find the task")

    result = await execute_and_test_code(
        task_data=task_data, language=submission.language, user_code=submission.code
    )

    return result