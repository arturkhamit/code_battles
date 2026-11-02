# ruff: noqa: S101, S603
import io
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.tasks.management.commands import import_tasks
from apps.tasks.models import Task

BACKEND_DIR = Path(__file__).resolve().parents[2]

# the keys a dataset row has (and the old detail endpoint returned), plus id
DETAIL_KEYS = {
    "id", "name", "description", "public_tests", "private_tests", "generated_tests",
    "source", "difficulty", "cf_index", "cf_points", "cf_rating", "cf_tags",
    "is_description_translated", "time_limit", "memory_limit_bytes", "input_file",
    "output_file",
}  # fmt: skip
LIST_KEYS = {
    "id", "name", "difficulty_label", "cf_rating", "cf_tags", "source_label", "source_slug",
    "time_limit_ms", "memory_limit_mb", "public_tests_count", "excerpt",
}  # fmt: skip


def internal(settings):
    return {"HTTP_AUTHORIZATION": f"Bearer {settings.INTERNAL_API_TOKEN}"}


def row(**overrides):
    """One line of tests.json as a dict."""
    return {
        "name": "Pentagonal numbers",
        "description": "Find the n-th pentagonal number.\n",
        "public_tests": {"input": ["1\n"], "output": ["1\n"]},
        "private_tests": {"input": ["2\n"], "output": ["5\n"]},
        "generated_tests": {"input": ["3\n", "4\n"], "output": ["12\n", "22\n"]},
        "source": 2,
        "difficulty": 7,
        "cf_index": "A",
        "cf_points": 500.0,
        "cf_rating": 800,
        "cf_tags": ["math"],
        "is_description_translated": False,
        "time_limit": {"seconds": 3, "nanos": 0},
        "memory_limit_bytes": 268435456,
        "input_file": "",
        "output_file": "",
        **overrides,
    }


@pytest.fixture
def many_tasks(db):
    Task.objects.bulk_create(
        Task(id=i, name=f"task {i}", description="d", cf_rating=800) for i in range(1, 131)
    )


# --- difficulty label -------------------------------------------------------


@pytest.mark.parametrize(
    ("cf_rating", "difficulty", "label"),
    [
        # a rating wins over the enum
        (800, 3, "easy"),
        (1200, None, "easy"),
        (1201, None, "medium"),
        (1900, 1, "medium"),
        (1901, 7, "hard"),
        (3500, None, "hard"),
        # no rating (0 or NULL): the code_contests enum decides
        (0, 1, "easy"),  # EASY
        (None, 2, "medium"),  # MEDIUM
        (0, 3, "hard"),  # HARD
        (0, 4, "hard"),  # HARDER
        (0, 5, "hard"),  # HARDEST
        (0, 7, "easy"),  # A
        (0, 8, "easy"),  # B
        (0, 9, "medium"),  # C
        (0, 10, "medium"),  # D
        (0, 11, "hard"),  # E
        (0, 14, "hard"),  # H
        (0, 32, "hard"),  # Z
        (0, 0, "unknown"),  # UNKNOWN_DIFFICULTY
        (0, 6, "unknown"),  # EXTERNAL
        (0, None, "unknown"),
        (None, None, "unknown"),
    ],
)
@pytest.mark.django_db
def test_difficulty_label(cf_rating, difficulty, label):
    # a stored column Postgres computes: create() reads it back
    task = Task.objects.create(name="t", description="d", cf_rating=cf_rating, difficulty=difficulty)
    assert task.difficulty_label == label


# --- GET /internal/tasks/<id>/ ----------------------------------------------


@pytest.mark.django_db
def test_task_detail_has_the_dataset_keys_plus_id(api, settings):
    Task.objects.create(id=761, **{k: v for k, v in row().items() if k != "name"}, name="162_A")

    response = api.get("/internal/tasks/761/", **internal(settings))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == DETAIL_KEYS  # in particular: no solutions, no incorrect_solutions
    assert body["id"] == 761
    assert body["name"] == "162_A"
    # what FastAPI /info and the judge read
    assert body["time_limit"] == {"seconds": 3, "nanos": 0}
    assert body["memory_limit_bytes"] == 268435456
    assert body["public_tests"] == {"input": ["1\n"], "output": ["1\n"]}
    assert body["private_tests"] == {"input": ["2\n"], "output": ["5\n"]}
    assert body["generated_tests"]["output"] == ["12\n", "22\n"]


@pytest.mark.django_db
def test_task_detail_of_an_unknown_id_is_a_json_404(api, settings):
    response = api.get("/internal/tasks/999999/", **internal(settings))
    assert response.status_code == 404
    assert response["Content-Type"].startswith("application/json")
    assert "detail" in response.json()


# --- GET /internal/tasks/?limit=&offset= ------------------------------------


@pytest.mark.django_db
def test_task_list_defaults_to_20_items_without_description_or_tests(
    api, settings, many_tasks
):
    response = api.get("/internal/tasks/", **internal(settings))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"count", "next", "previous", "results"}
    assert body["count"] == 130
    assert body["previous"] is None
    assert body["next"].endswith("/internal/tasks/?limit=20&offset=20")
    assert [t["id"] for t in body["results"]] == list(range(1, 21))
    assert set(body["results"][0]) == LIST_KEYS
    assert body["results"][0]["difficulty_label"] == "easy"


@pytest.mark.django_db
def test_task_list_limit_and_offset(api, settings, many_tasks):
    response = api.get("/internal/tasks/?limit=5&offset=10", **internal(settings))

    body = response.json()
    assert [t["id"] for t in body["results"]] == [11, 12, 13, 14, 15]
    assert "offset=15" in body["next"]
    assert "offset=5" in body["previous"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("query", "size"),
    [("limit=1000", 100), ("limit=100", 100), ("limit=0", 20), ("limit=-3", 20), ("limit=x", 20)],
)
def test_task_list_limit_is_capped_at_100_and_bad_values_use_the_default(
    api, settings, many_tasks, query, size
):
    response = api.get(f"/internal/tasks/?{query}", **internal(settings))
    assert response.status_code == 200
    assert len(response.json()["results"]) == size


@pytest.mark.django_db
def test_task_list_never_loads_the_heavy_columns(
    api, settings, many_tasks, django_assert_num_queries
):
    # COUNT + one SELECT: no per-item query for deferred description/tests/label
    with django_assert_num_queries(2):
        assert api.get("/internal/tasks/?limit=100", **internal(settings)).status_code == 200


# --- manage.py import_tasks -------------------------------------------------


@pytest.mark.django_db
def test_import_tasks_numbers_by_line_skips_bad_rows_and_is_idempotent(tmp_path, caplog):
    path = tmp_path / "tests.json"
    unequal = row(name="unequal", public_tests={"input": ["1"], "output": []})
    path.write_text(
        "\n".join(
            [
                json.dumps(row(name="first")),
                "",  # blank lines are not rows (the old loader skipped them too)
                "{not json",
                json.dumps(unequal),
                json.dumps(row(name="last", solutions={"language": [1], "solution": ["x"]})),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    def run():
        out = io.StringIO()
        call_command("import_tasks", str(path), stdout=out)
        return out.getvalue()

    with caplog.at_level(logging.WARNING, logger=import_tasks.logger.name):
        first_run = run()
    assert first_run.startswith("Imported 2 tasks, skipped 2, in ")
    # skipped rows still use up their number: "last" is row 4, as the old index lookup had it
    assert list(Task.objects.values_list("id", "name")) == [(1, "first"), (4, "last")]
    skipped = [r.getMessage() for r in caplog.records if r.name == import_tasks.logger.name]
    assert len(skipped) == 2
    assert skipped[0].startswith("import_tasks: row 2 skipped: not JSON")
    assert skipped[1].startswith("import_tasks: row 3 skipped:")

    second_run = run()
    assert second_run.startswith("Imported 2 tasks, skipped 2, in ")
    assert Task.objects.count() == 2  # no duplicates

    path.write_text(json.dumps(row(name="renamed", cf_rating=2000)) + "\n", encoding="utf-8")
    run()
    assert Task.objects.get(id=1).name == "renamed"  # a re-run updates in place
    assert Task.objects.get(id=1).cf_rating == 2000
    assert Task.objects.get(id=4).name == "last"  # and leaves other rows alone


@pytest.mark.django_db
def test_import_tasks_leaves_the_id_sequence_after_the_imported_rows(tmp_path):
    path = tmp_path / "tests.json"
    path.write_text(json.dumps(row()) + "\n" + json.dumps(row()) + "\n", encoding="utf-8")
    call_command("import_tasks", str(path), stdout=io.StringIO())

    created = Task.objects.create(name="by hand", description="d")  # no id: uses the sequence

    assert created.id == 3


@pytest.mark.django_db
def test_import_tasks_stores_the_validated_values(tmp_path):
    path = tmp_path / "tests.json"
    lines = [
        row(name="no tests", public_tests=None, private_tests=None, generated_tests=None),
        row(name="no limits", time_limit=None, memory_limit_bytes=0, cf_rating=0),
    ]
    path.write_text("".join(json.dumps(r) + "\n" for r in lines), encoding="utf-8")
    call_command("import_tasks", str(path), stdout=io.StringIO())

    no_tests, no_limits = Task.objects.order_by("id")
    assert no_tests.public_tests == no_tests.private_tests == {"input": [], "output": []}
    assert no_tests.generated_tests == {"input": [], "output": []}
    assert (no_limits.time_limit, no_limits.memory_limit_bytes) == (None, 0)
    assert no_limits.difficulty_label == "easy"  # difficulty 7 = A, there is no rating
    assert (no_limits.time_limit_ms, no_tests.public_tests_count) == (None, 0)
    assert (no_tests.time_limit_ms, no_limits.public_tests_count) == (3000, 1)
    assert no_limits.description == "Find the n-th pentagonal number."  # trimmed like before


@pytest.mark.django_db
def test_import_tasks_writes_in_batches(tmp_path, monkeypatch):
    monkeypatch.setattr(import_tasks, "BATCH_ROWS", 2)
    path = tmp_path / "tests.json"
    path.write_text("".join(json.dumps(row(name=f"t{i}")) + "\n" for i in range(5)), encoding="utf-8")

    out = io.StringIO()
    call_command("import_tasks", str(path), stdout=out)

    assert out.getvalue().startswith("Imported 5 tasks, skipped 0")
    assert Task.objects.count() == 5


@pytest.mark.django_db
def test_import_tasks_never_puts_a_huge_task_into_a_multi_row_batch(tmp_path, monkeypatch):
    # Django writes several rows through UNNEST, which needs ~30x the JSON size in memory
    monkeypatch.setattr(import_tasks, "BATCH_CHARS", 1500)
    saved = []
    original_save = import_tasks.Command._save

    def spy(batch):
        saved.append([task.id for task in batch])
        return original_save(batch)

    monkeypatch.setattr(import_tasks.Command, "_save", staticmethod(spy))
    small, huge = row(), row(description="x" * 5000)
    path = tmp_path / "tests.json"
    path.write_text("".join(json.dumps(r) + "\n" for r in (small, small, huge, small, small)), encoding="utf-8")

    call_command("import_tasks", str(path), stdout=io.StringIO())

    assert [batch for batch in saved if batch] == [[1, 2], [3], [4, 5]]
    assert Task.objects.count() == 5


def test_import_tasks_reports_a_missing_file(tmp_path):
    with pytest.raises(CommandError, match="File not found"):
        call_command("import_tasks", str(tmp_path / "nope.json"))


def test_import_tasks_default_path_is_backend_tests_tests_json():
    assert import_tasks.DEFAULT_PATH == BACKEND_DIR / "tests" / "tests.json"


# --- catalog: filters, ordering, item fields, facets ------------------------


@pytest.fixture
def catalog(db):
    def make(id, name, rating, tags, source, seconds, mem_mb, tests, difficulty=None):
        Task.objects.create(
            id=id, name=name, description=f"Problem description.\nLegend of {name}.\n\nInput\n\nn",
            cf_rating=rating, cf_tags=tags, source=source, difficulty=difficulty,
            time_limit={"seconds": seconds, "nanos": 500_000_000} if seconds else None,
            memory_limit_bytes=mem_mb * 2**20,
            public_tests={"input": ["1"] * tests, "output": ["1"] * tests},
        )  # fmt: skip

    make(1, "Watermelon", 800, ["math", "brute force"], 2, 1, 64, 1)
    make(2, "Graph walk", 1500, ["graphs", "dfs and similar"], 2, 2, 256, 3)
    make(3, "Hard graphs", 2400, ["graphs", "math"], 2, 4, 512, 2)
    make(4, "Chef and brackets", 0, [], 1, None, 0, 0, difficulty=0)  # unknown, no limits
    make(5, "Aizu square", None, [], 6, 1, 128, 4, difficulty=2)  # medium by the enum


def ids(api, settings, query):
    response = api.get(f"/internal/tasks/?{query}", **internal(settings))
    assert response.status_code == 200, response.content
    return [t["id"] for t in response.json()["results"]]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("search=graph", [2, 3]),
        ("search=GRAPH", [2, 3]),
        ("search=4", [4]),  # a number also matches the id
        ("search=%234", [4]),  # "#4"
        ("difficulty=medium", [2, 5]),
        ("difficulty=easy,hard", [1, 3]),
        ("difficulty=unknown", [4]),
        ("rating_min=1000", [2, 3]),
        ("rating_max=1500", [1, 2]),  # unrated tasks never match a range
        ("rating_min=1000&rating_max=2000", [2]),
        ("tags=graphs", [2, 3]),
        ("tags=graphs,math", [3]),  # all of the tags
        ("source=codeforces", [1, 2, 3]),
        ("source=codechef,aizu", [4, 5]),
        ("search=graph&difficulty=hard&tags=math", [3]),
        ("search=nothing-like-it", []),
    ],
)
def test_task_list_filters(api, settings, catalog, query, expected):
    assert ids(api, settings, query) == expected


@pytest.mark.parametrize(
    ("ordering", "expected"),
    [
        ("id", [1, 2, 3, 4, 5]),
        ("-id", [5, 4, 3, 2, 1]),
        ("name", [5, 4, 2, 3, 1]),
        ("cf_rating", [1, 2, 3, 4, 5]),  # no rating last, by id
        ("-cf_rating", [3, 2, 1, 4, 5]),
        ("difficulty", [1, 2, 5, 3, 4]),  # easy, medium (rated first), hard, unknown last
        ("-difficulty", [3, 2, 5, 1, 4]),
        ("time_limit", [1, 5, 2, 3, 4]),
        ("-memory_limit", [3, 2, 5, 1, 4]),  # 0 = no limit: last
        ("-tests", [5, 2, 3, 1, 4]),
    ],
)
def test_task_list_ordering(api, settings, catalog, ordering, expected):
    assert ids(api, settings, f"ordering={ordering}") == expected


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query",
    ["ordering=description", "ordering=--id", "difficulty=trivial", "source=leetcode", "rating_min=x"],
)
def test_task_list_rejects_unknown_filter_values(api, settings, query):
    response = api.get(f"/internal/tasks/?{query}", **internal(settings))
    assert response.status_code == 400
    assert response["Content-Type"].startswith("application/json")


def test_task_list_item_is_readable_without_the_full_task(api, settings, catalog):
    response = api.get("/internal/tasks/?search=Graph%20walk", **internal(settings))
    (item,) = response.json()["results"]
    assert set(item) == LIST_KEYS
    assert item == {
        "id": 2, "name": "Graph walk", "difficulty_label": "medium", "cf_rating": 1500,
        "cf_tags": ["graphs", "dfs and similar"], "source_label": "Codeforces",
        "source_slug": "codeforces", "time_limit_ms": 2500, "memory_limit_mb": 256,
        "public_tests_count": 3, "excerpt": "Legend of Graph walk.",
    }  # fmt: skip
    no_limits = api.get("/internal/tasks/?search=4", **internal(settings)).json()["results"][0]
    assert (no_limits["cf_rating"], no_limits["memory_limit_mb"], no_limits["time_limit_ms"]) == (
        None, None, None,
    )  # fmt: skip
    assert no_limits["source_label"] == "CodeChef"


@pytest.mark.parametrize(
    ("text", "excerpt"),
    [
        ("Problem description.\nShort.\n\nInput\n\nT lines", "Short."),
        ("Given $1 \\le n \\le 10^5$ and <image> a_i.", "Given 1 ≤ n ≤ 10^5 and a_i."),
        ("**Bold** `code` # title", "Bold code title"),
        ("word " * 60, ("word " * 31).strip() + "…"),
    ],
)
def test_make_excerpt(text, excerpt):
    from apps.tasks.serializers import EXCERPT_CHARS, make_excerpt

    result = make_excerpt(text)
    assert result == excerpt
    assert len(result) <= EXCERPT_CHARS


def test_task_facets(api, settings, catalog):
    response = api.get("/internal/tasks/facets/", **internal(settings))
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert body["difficulties"] == [
        {"value": "easy", "count": 1}, {"value": "medium", "count": 2},
        {"value": "hard", "count": 1}, {"value": "unknown", "count": 1},
    ]  # fmt: skip
    assert body["sources"][0] == {"value": "codeforces", "label": "Codeforces", "count": 3}
    assert {s["value"] for s in body["sources"]} == {"codeforces", "codechef", "aizu"}
    assert body["tags"][:2] == [{"value": "graphs", "count": 2}, {"value": "math", "count": 2}]
    assert len(body["tags"]) == 4
    assert body["rating"] == {"min": 800, "max": 2400}
    assert "cf_rating" in body["orderings"]


@pytest.mark.django_db
def test_task_facets_need_the_internal_token(api):
    assert api.get("/internal/tasks/facets/").status_code in (401, 403)


def test_system_checks_pass():
    """pytest skips Django's checks; `migrate` does not (a GinIndex without contrib.postgres)."""
    from django.core.management import call_command

    call_command("check", fail_level="ERROR")


# --- start-up does not need the dataset -------------------------------------


def test_django_and_urls_start_without_tests_json_and_stay_small():
    code = """
import sys

def refuse(event, args):
    if event == "open" and "tests.json" in str(args[0]):
        raise RuntimeError(f"opened {args[0]}")

sys.addaudithook(refuse)
import django
django.setup()
import config.urls
import resource
print(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)  # KiB on Linux
print("tests.parse_json" in sys.modules)
"""
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings.test"}
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    rss_kib, parse_json_loaded = result.stdout.split()[-2:]
    assert parse_json_loaded == "False"
    assert int(rss_kib) < 150 * 1024  # it was 165 MiB while the 93 MB file was loaded
