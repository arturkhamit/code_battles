import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth import get_current_user
from schemas.submission import CodeSubmission
from services import django_callbacks as django
from services import limits
from services.code_executor import execute_and_test_code

# Django errors are turned into 404 / 502 / 503 and RateLimited into 429 by the handlers in main.py.
router = APIRouter(prefix="/tasks", tags=["Tasks"])

API_PREFIX = "/api"  # this router is mounted under it

# what a catalog item carries (Django's TaskListSerializer); anything else is dropped
ITEM_KEYS = (
    "id", "name", "difficulty_label", "cf_rating", "cf_tags", "source_label", "source_slug",
    "time_limit_ms", "memory_limit_mb", "public_tests_count", "excerpt",
)  # fmt: skip
_LABEL = "(easy|medium|hard|unknown)"
_SLUG = "[a-z]{1,20}"


def task_filters(
    search: str | None = Query(None, max_length=100),
    difficulty: str | None = Query(None, pattern=f"^{_LABEL}(,{_LABEL})*$"),
    rating_min: int | None = Query(None, ge=0, le=5000),
    rating_max: int | None = Query(None, ge=0, le=5000),
    tags: str | None = Query(None, max_length=500),
    source: str | None = Query(None, pattern=f"^{_SLUG}(,{_SLUG})*$"),
    ordering: str | None = Query(
        None, pattern="^-?(id|name|cf_rating|difficulty|time_limit|memory_limit|tests)$"
    ),
) -> dict:
    """The catalog filters Django understands (whitelist); empty ones are left out."""
    values = {
        "search": search, "difficulty": difficulty, "rating_min": rating_min,
        "rating_max": rating_max, "tags": tags, "source": source, "ordering": ordering,
    }  # fmt: skip
    return {k: v for k, v in values.items() if v not in (None, "")}


def catalog_item(item: dict) -> dict:
    return {k: item.get(k) for k in ITEM_KEYS}


@router.get("/facets/")
async def get_task_facets(_user: dict = Depends(get_current_user)):
    """Tags, sources, rating range and difficulty counts for the catalog filters."""
    return await django.fetch_task_facets()


@router.get("/random")
async def get_random_task(
    filters: dict = Depends(task_filters), _user: dict = Depends(get_current_user)
):
    """One random catalog item among those the filters match; 404 if none does."""
    filters.pop("ordering", None)
    count = (await django.fetch_tasks(limit=1, offset=0, filters=filters)).get("count") or 0
    if count <= 0:
        raise HTTPException(404, "No task matches the filters")
    page = await django.fetch_tasks(limit=1, offset=secrets.randbelow(count), filters=filters)
    if not page.get("results"):  # the catalog shrank in between
        raise HTTPException(404, "No task matches the filters")
    return catalog_item(page["results"][0])


@router.get("/")
async def get_tasks(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    filters: dict = Depends(task_filters),
    _user: dict = Depends(get_current_user),
):
    data = await django.fetch_tasks(limit=limit, offset=offset, filters=filters)

    results = [catalog_item(item) for item in data.get("results", [])]
    count = data.get("count")

    def page(new_offset: int) -> str:
        return f"{API_PREFIX}/tasks/?{urlencode({**filters, 'limit': limit, 'offset': new_offset})}"

    has_next = offset + limit < count if count is not None else len(results) == limit
    return {
        "count": count,
        "next": page(offset + limit) if has_next else None,
        "previous": page(max(0, offset - limit)) if offset > 0 else None,
        "results": results,
    }


@router.get("/{task_id}/info")
async def get_task_info(task_id: int, _user: dict = Depends(get_current_user)):
    task_data = await django.fetch_task(task_id)

    return {
        "id": task_id,
        "name": task_data.get("name"),
        "description": task_data.get("description"),
        "time_limit": task_data.get("time_limit"),
        "memory_limit_bytes": task_data.get("memory_limit_bytes"),
        # public tests only: private and generated ones never leave the server
        "public_tests": task_data.get("public_tests", {"input": [], "output": []}),
    }


@router.post("/{task_id}/submit")
async def submit_code(
    task_id: int,
    submission: CodeSubmission,
    user: dict = Depends(get_current_user),
):
    async with limits.run_slot(user["user_id"]):
        task_data = await django.fetch_task(task_id)
        return await execute_and_test_code(
            task_data=task_data, language=submission.language, user_code=submission.code
        )
