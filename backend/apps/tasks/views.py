from django.db import connection
from django.db.models import Case, Count, F, IntegerField, Max, Min, Q, Value, When
from django.db.models.functions import NullIf, Substr
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.battles.permissions import IsInternalService
from apps.tasks.models import Task
from apps.tasks.models.task import DIFFICULTY_LABELS, SOURCE_BY_SLUG, SOURCES
from apps.tasks.serializers import TaskDetailSerializer, TaskListSerializer

LIST_FIELDS = (
    "id", "name", "difficulty_label", "cf_rating", "cf_tags", "source", "time_limit_ms",
    "memory_limit_bytes", "public_tests_count",
)  # fmt: skip
DESCRIPTION_HEAD = 1500  # enough of the legend for a 160-char excerpt
SEARCH_MAX = 100

# ?ordering=<key> or -<key>; secondary keys keep the order stable for limit/offset paging.
# Missing values (no rating, unknown difficulty, no limit) go last in both directions.
ORDERINGS = {
    "id": ("id",),
    "name": ("name",),
    "cf_rating": ("rating",),
    "difficulty": ("difficulty_rank", "rating"),
    "time_limit": ("time_limit_ms",),
    "memory_limit": ("memory",),
    "tests": ("public_tests_count",),
}


def _csv(params, name: str) -> list[str]:
    return [v.strip() for v in params.get(name, "").split(",") if v.strip()]


def _int(params, name: str) -> int | None:
    raw = params.get(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        raise ValidationError({name: ["Must be an integer."]}) from None


def filter_tasks(queryset, params):
    """The catalog filters of ?search, difficulty, rating_min/max, tags, source, ordering.

    Bad values are a 400 (the UI only sends what /facets/ offered, so a 400 is a bug to see).
    `tags` is AND: a task must have every chosen tag, like the Codeforces problemset.
    """
    if search := params.get("search", "").strip()[:SEARCH_MAX]:
        match = Q(name__icontains=search)
        if search.lstrip("#").isdigit():
            match |= Q(id=int(search.lstrip("#")))
        queryset = queryset.filter(match)

    if difficulties := _csv(params, "difficulty"):
        if bad := set(difficulties) - set(DIFFICULTY_LABELS):
            raise ValidationError({"difficulty": [f"Unknown: {', '.join(sorted(bad))}."]})
        queryset = queryset.filter(difficulty_label__in=difficulties)

    rating_min, rating_max = _int(params, "rating_min"), _int(params, "rating_max")
    if rating_min is not None or rating_max is not None:
        queryset = queryset.filter(cf_rating__gt=0)  # a range never matches "no rating"
        if rating_min is not None:
            queryset = queryset.filter(cf_rating__gte=rating_min)
        if rating_max is not None:
            queryset = queryset.filter(cf_rating__lte=rating_max)

    if tags := _csv(params, "tags"):
        queryset = queryset.filter(cf_tags__contains=tags)

    if sources := _csv(params, "source"):
        if bad := set(sources) - set(SOURCE_BY_SLUG):
            raise ValidationError({"source": [f"Unknown: {', '.join(sorted(bad))}."]})
        numbers = [SOURCE_BY_SLUG[s] for s in sources]
        match = Q(source__in=numbers)
        if 0 in numbers:
            match |= Q(source__isnull=True)
        queryset = queryset.filter(match)

    ordering = params.get("ordering", "").strip() or "id"
    key = ordering.removeprefix("-")
    if key not in ORDERINGS:
        raise ValidationError({"ordering": [f"One of: {', '.join(ORDERINGS)} (- for descending)."]})
    descending = ordering.startswith("-")
    queryset = queryset.annotate(
        rating=NullIf(F("cf_rating"), Value(0)),
        memory=NullIf(F("memory_limit_bytes"), Value(0)),
        difficulty_rank=Case(
            When(difficulty_label="easy", then=1),
            When(difficulty_label="medium", then=2),
            When(difficulty_label="hard", then=3),
            output_field=IntegerField(),
        ),
    )
    order_by = [
        F(name).desc(nulls_last=True) if descending else F(name).asc(nulls_last=True)
        for name in ORDERINGS[key]
    ]
    return queryset.order_by(*order_by, "id")


class TaskPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 100


class TaskListView(ListAPIView):
    """GET /internal/tasks/?limit&offset&search&difficulty&rating_min&rating_max&tags&source&ordering
    -> {count, next, previous, results}. See filter_tasks."""

    authentication_classes = []
    permission_classes = [IsInternalService]
    pagination_class = TaskPagination
    serializer_class = TaskListSerializer

    def get_queryset(self):
        # tests are megabytes per task and the description is long: only its head is read
        queryset = Task.objects.only(*LIST_FIELDS).annotate(
            description_head=Substr("description", 1, DESCRIPTION_HEAD)
        )
        return filter_tasks(queryset, self.request.query_params)


class TaskFacetsView(APIView):
    """GET /internal/tasks/facets/ -> what the catalog filters can offer, with counts."""

    authentication_classes = []
    permission_classes = [IsInternalService]

    def get(self, request):
        by_label = dict(
            Task.objects.values_list("difficulty_label").annotate(n=Count("id")).order_by()
        )
        by_source = dict(Task.objects.values_list("source").annotate(n=Count("id")).order_by())
        sources = {}
        for number, n in by_source.items():
            slug, label = SOURCES.get(number or 0, SOURCES[0])
            entry = sources.setdefault(slug, {"value": slug, "label": label, "count": 0})
            entry["count"] += n
        rating = Task.objects.filter(cf_rating__gt=0).aggregate(
            min=Min("cf_rating"), max=Max("cf_rating")
        )
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT tag, COUNT(*) FROM {Task._meta.db_table}, "  # noqa: S608 (no user input)
                "jsonb_array_elements_text(cf_tags) AS tag "
                "WHERE jsonb_typeof(cf_tags) = 'array' GROUP BY tag ORDER BY 2 DESC, 1"
            )
            tags = [{"value": tag, "count": n} for tag, n in cursor.fetchall()]
        return Response(
            {
                "total": sum(by_label.values()),
                "difficulties": [
                    {"value": label, "count": by_label.get(label, 0)} for label in DIFFICULTY_LABELS
                ],
                "sources": sorted(sources.values(), key=lambda s: -s["count"]),
                "tags": tags,
                "rating": rating,
                "orderings": list(ORDERINGS),
            }
        )


class TaskDetailView(RetrieveAPIView):
    """GET /internal/tasks/<task_id>/ -> one task with its tests, 404 JSON if missing."""

    authentication_classes = []
    permission_classes = [IsInternalService]
    serializer_class = TaskDetailSerializer
    queryset = Task.objects.all()
    lookup_url_kwarg = "task_id"
