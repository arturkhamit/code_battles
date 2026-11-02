from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.db.models import Case, Func, IntegerField, Q, Value, When
from django.db.models.fields.json import KeyTextTransform, KeyTransform
from django.db.models.functions import Cast, Coalesce


def empty_tests():
    return {"input": [], "output": []}


# code_contests `source` enum -> (slug for URLs, label for people)
SOURCES = {
    0: ("unknown", "Unknown"),
    1: ("codechef", "CodeChef"),
    2: ("codeforces", "Codeforces"),
    3: ("hackerearth", "HackerEarth"),
    4: ("codejam", "Code Jam"),
    5: ("atcoder", "AtCoder"),
    6: ("aizu", "Aizu"),
}
SOURCE_BY_SLUG = {slug: number for number, (slug, _) in SOURCES.items()}
DIFFICULTY_LABELS = ("easy", "medium", "hard", "unknown")

# easy / medium / hard / unknown: by Codeforces rating, else by the `difficulty` enum
# (0 UNKNOWN, 1 EASY, 2 MEDIUM, 3 HARD, 4 HARDER, 5 HARDEST, 6 EXTERNAL, 7 A ... 32 Z).
# The dataset uses 0 for "no rating".
DIFFICULTY_LABEL_SQL = Case(
    When(cf_rating__gt=1900, then=Value("hard")),
    When(cf_rating__gt=1200, then=Value("medium")),
    When(cf_rating__gt=0, then=Value("easy")),
    When(difficulty__in=(1, 7, 8), then=Value("easy")),  # EASY, A, B
    When(difficulty__in=(2, 9, 10), then=Value("medium")),  # MEDIUM, C, D
    When(Q(difficulty__range=(3, 5)) | Q(difficulty__gte=11), then=Value("hard")),
    default=Value("unknown"),
)


class Task(models.Model):
    """A code_contests problem.

    `id` is the 1-based line number of the problem in backend/tests/tests.json (set by
    `manage.py import_tasks`). Battle.task keeps that number as a plain integer, no foreign key.
    `solutions` / `incorrect_solutions` of the dataset are not stored.
    """

    name = models.CharField(max_length=255)
    description = models.TextField()

    # code_contests enums; see DIFFICULTY_LABEL_SQL and SOURCES
    difficulty = models.IntegerField(null=True, blank=True)
    source = models.IntegerField(null=True, blank=True)

    cf_index = models.CharField(max_length=16, blank=True)
    cf_points = models.FloatField(null=True, blank=True)
    cf_rating = models.IntegerField(null=True, blank=True)  # 0 or NULL: no rating
    cf_tags = models.JSONField(default=list, blank=True)
    is_description_translated = models.BooleanField(default=False)

    time_limit = models.JSONField(null=True, blank=True)  # {"seconds": 1, "nanos": 0} or NULL
    memory_limit_bytes = models.BigIntegerField(null=True, blank=True)  # 0 or NULL: no limit
    input_file = models.CharField(max_length=255, blank=True)
    output_file = models.CharField(max_length=255, blank=True)

    # {"input": [...], "output": [...]}; megabytes for some tasks, so never load them for lists
    public_tests = models.JSONField(default=empty_tests, blank=True)
    private_tests = models.JSONField(default=empty_tests, blank=True)
    generated_tests = models.JSONField(default=empty_tests, blank=True)

    # Stored columns Postgres computes from the ones above, so the catalog filters and sorts in
    # SQL; every write path (import_tasks, admin, create) keeps them right by construction.
    difficulty_label = models.GeneratedField(
        expression=DIFFICULTY_LABEL_SQL,
        output_field=models.CharField(max_length=8),
        db_persist=True,
    )
    time_limit_ms = models.GeneratedField(
        expression=Cast(KeyTextTransform("seconds", "time_limit"), models.BigIntegerField()) * 1000
        + Coalesce(Cast(KeyTextTransform("nanos", "time_limit"), models.BigIntegerField()), 0)
        / 1_000_000,
        output_field=models.BigIntegerField(),
        db_persist=True,
    )
    public_tests_count = models.GeneratedField(
        expression=Coalesce(
            Func(
                KeyTransform("input", "public_tests"),
                function="jsonb_array_length",
                output_field=IntegerField(),
            ),
            0,
        ),
        output_field=IntegerField(),
        db_persist=True,
    )

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["difficulty_label"], name="task_difficulty_label_idx"),
            models.Index(fields=["cf_rating"], name="task_cf_rating_idx"),
            models.Index(fields=["source"], name="task_source_idx"),
            models.Index(fields=["name"], name="task_name_idx"),
            models.Index(fields=["time_limit_ms"], name="task_time_limit_ms_idx"),
            models.Index(fields=["memory_limit_bytes"], name="task_memory_idx"),
            models.Index(fields=["public_tests_count"], name="task_public_tests_count_idx"),
            GinIndex(fields=["cf_tags"], name="task_cf_tags_gin"),  # cf_tags @> [...]
        ]

    def __str__(self):
        return f"{self.pk}: {self.name}"

    @property
    def source_slug(self) -> str:
        return SOURCES.get(self.source or 0, SOURCES[0])[0]

    @property
    def source_label(self) -> str:
        return SOURCES.get(self.source or 0, SOURCES[0])[1]
