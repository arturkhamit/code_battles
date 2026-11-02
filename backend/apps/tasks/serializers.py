import re

from rest_framework import serializers

from apps.tasks.models import Task


class TestCasesSerializer(serializers.Serializer):
    input = serializers.ListField(
        child=serializers.CharField(allow_blank=True), allow_empty=True
    )
    output = serializers.ListField(
        child=serializers.CharField(allow_blank=True), allow_empty=True
    )


class SolutionsSerializer(serializers.Serializer):
    language = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True,
    )
    solution = serializers.ListField(
        child=serializers.CharField(allow_blank=True),
        allow_empty=True,
    )


class TaskImportSerializer(serializers.Serializer):
    """Validates one line of tests.json for `manage.py import_tasks`.

    The max_length values mirror the Task columns so that a bad line is skipped
    instead of failing a whole bulk insert.
    """

    name = serializers.CharField(max_length=255)
    description = serializers.CharField()

    public_tests = TestCasesSerializer(required=False, allow_null=True)
    private_tests = TestCasesSerializer(required=False, allow_null=True)
    generated_tests = TestCasesSerializer(required=False, allow_null=True)

    source = serializers.IntegerField(required=False, allow_null=True)
    difficulty = serializers.IntegerField(required=False, allow_null=True)

    solutions = SolutionsSerializer(required=False, allow_null=True)
    incorrect_solutions = SolutionsSerializer(required=False, allow_null=True)

    cf_contest_id = serializers.IntegerField(required=False, allow_null=True)
    cf_index = serializers.CharField(required=False, allow_blank=True, max_length=16)
    cf_points = serializers.FloatField(required=False, allow_null=True)
    cf_rating = serializers.IntegerField(required=False, allow_null=True)
    cf_tags = serializers.ListField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        allow_empty=True,
    )

    is_description_translated = serializers.BooleanField(default=False)
    untranslated_description = serializers.CharField(required=False, allow_blank=True)

    time_limit = serializers.JSONField(required=False, allow_null=True)
    memory_limit_bytes = serializers.IntegerField(
        required=False, allow_null=True, min_value=0
    )
    input_file = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )
    output_file = serializers.CharField(
        required=False, allow_blank=True, max_length=255
    )

    def validate(self, attrs):
        for test_type in ["public_tests", "private_tests", "generated_tests"]:
            tests = attrs.get(test_type)
            if tests and len(tests["input"]) != len(tests["output"]):
                raise serializers.ValidationError(
                    f"In {test_type} size of input ({len(tests['input'])}) "
                    f"is not same as output ({len(tests['output'])})."
                )
        return attrs


EXCERPT_CHARS = 160
_BEFORE_INPUT = re.compile(r"\n\s*Input\s*\n")  # the legend ends where the Input section starts
_LEADING = re.compile(r"^\s*Problem (description|statement)\.?\s*", re.IGNORECASE)
_LATEX = {
    "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "ne": "≠", "neq": "≠",
    "cdot": "·", "times": "×", "dots": "…", "ldots": "…", "cdots": "…",
}  # fmt: skip
_LATEX_CMD = re.compile(r"\\([a-zA-Z]+)")
_TAGS = re.compile(r"<[^>]*>")  # <image>, <b>, ...
_JUNK = re.compile(r"[$`*#~{}\\]+")
_SPACES = re.compile(r"\s+")


def make_excerpt(text: str, limit: int = EXCERPT_CHARS) -> str:
    """The start of the legend as one plain line: no markup, LaTeX or section headings."""
    text = _LEADING.sub("", _BEFORE_INPUT.split(text, maxsplit=1)[0])
    text = _LATEX_CMD.sub(lambda m: _LATEX.get(m.group(1), " "), text)
    text = _SPACES.sub(" ", _JUNK.sub("", _TAGS.sub(" ", text))).strip()
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0] or text[: limit - 1]
    return cut.rstrip(" ,.;:") + "…"


class TaskListSerializer(serializers.ModelSerializer):
    """Catalog item: no tests (megabytes) and only a short excerpt of the description.

    The view annotates `description_head` (the first characters, cut in SQL).
    """

    cf_rating = serializers.SerializerMethodField()
    source_label = serializers.CharField(read_only=True)
    source_slug = serializers.CharField(read_only=True)
    memory_limit_mb = serializers.SerializerMethodField()
    excerpt = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = (
            "id",
            "name",
            "difficulty_label",
            "cf_rating",
            "cf_tags",
            "source_label",
            "source_slug",
            "time_limit_ms",
            "memory_limit_mb",
            "public_tests_count",
            "excerpt",
        )

    def get_cf_rating(self, task) -> int | None:
        return task.cf_rating or None  # 0 means "no rating"

    def get_memory_limit_mb(self, task) -> int | None:
        return task.memory_limit_bytes // 2**20 if task.memory_limit_bytes else None

    def get_excerpt(self, task) -> str:
        return make_excerpt(getattr(task, "description_head", ""))


class TaskDetailSerializer(serializers.ModelSerializer):
    """Everything FastAPI (/info) and the judge read: the keys the dataset rows have, plus id."""

    class Meta:
        model = Task
        fields = (
            "id",
            "name",
            "description",
            "public_tests",
            "private_tests",
            "generated_tests",
            "source",
            "difficulty",
            "cf_index",
            "cf_points",
            "cf_rating",
            "cf_tags",
            "is_description_translated",
            "time_limit",
            "memory_limit_bytes",
            "input_file",
            "output_file",
        )
