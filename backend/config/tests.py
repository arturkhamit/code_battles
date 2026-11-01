# ruff: noqa: S101, S105, S106, S603
"""Project-level tests: health/ready probes, production settings, API error handling, admin.

Need real Postgres and Redis, see pytest.ini.
"""

import importlib
import io
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured, ObjectDoesNotExist, PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, connection
from django.http import Http404
from django.test.utils import CaptureQueriesContext
from rest_framework.exceptions import Throttled
from rest_framework.permissions import AllowAny
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from apps.accounts.models import Profile
from apps.battles.models import Battle, Participant
from apps.submissions.models import Submission
from apps.tasks.models import Task
from config.exceptions import ConflictError, ForbiddenError
from config.logging_json import JsonFormatter

BACKEND_DIR = Path(__file__).resolve().parent.parent

PROD_ENV = {
    "DJANGO_SECRET_KEY": "prod-django-secret-key-" + "a" * 40,
    "JWT_SIGNING_KEY": "prod-jwt-signing-key-" + "b" * 40,
    "INTERNAL_API_TOKEN": "prod-internal-api-token-" + "c" * 40,
    "POSTGRES_DB": "db",
    "POSTGRES_USER": "user",
    "POSTGRES_PASSWORD": "pw",
    "POSTGRES_HOST": "localhost",
    "REDIS_URL": "redis://localhost:6379/0",
}
OPTIONAL_ENV = (
    "ALLOWED_HOSTS",
    "CSRF_TRUSTED_ORIGINS",
    "CORS_ALLOWED_ORIGINS",
    "HTTPS",
    "NUM_PROXIES",
    "POSTGRES_PORT",
    "LOG_LEVEL",
)
PAIRS = [
    ("DJANGO_SECRET_KEY", "JWT_SIGNING_KEY"),
    ("DJANGO_SECRET_KEY", "INTERNAL_API_TOKEN"),
    ("JWT_SIGNING_KEY", "INTERNAL_API_TOKEN"),
]


def load_production(monkeypatch, **env):
    """Import config.settings.production afresh under a controlled environment.

    NAME=None removes a variable.
    """
    for name in (*PROD_ENV, *OPTIONAL_ENV):
        monkeypatch.delenv(name, raising=False)
    for name, value in {**PROD_ENV, **env}.items():
        if value is not None:
            monkeypatch.setenv(name, value)
    for module in ("config.settings.base", "config.settings.production"):
        monkeypatch.delitem(sys.modules, module, raising=False)
    return importlib.import_module("config.settings.production")


def run_production(code, drop=(), **env):
    """Run `code` after django.setup() in a fresh interpreter, production settings.

    DB and Redis point at the same services as this test run; `drop` removes variables.
    """
    full_env = {
        "PATH": os.environ["PATH"],
        "PYTHONPATH": str(BACKEND_DIR),
        "DJANGO_SETTINGS_MODULE": "config.settings.production",
        **PROD_ENV,
        **{k: v for k, v in os.environ.items() if k.startswith("POSTGRES_")},
        "REDIS_URL": os.environ["REDIS_URL"],
        **env,
    }
    for name in drop:
        full_env.pop(name)
    return subprocess.run(
        [sys.executable, "-c", "import django; django.setup()\n" + code],
        cwd=BACKEND_DIR,
        env=full_env,
        capture_output=True,
        text=True,
        timeout=120,
    )


# --- logging ----------------------------------------------------------------


def test_json_log_line_has_core_fields_extras_and_traceback():
    logger = logging.getLogger("config.tests.json")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    try:
        try:
            raise ValueError("boom")
        except ValueError:
            logger.error(
                "battle %d failed", 7, exc_info=True, extra={"battle_id": 7, "request": object()}
            )
    finally:
        logger.removeHandler(handler)

    line = json.loads(stream.getvalue())  # exactly one JSON object
    assert line["level"] == "ERROR"
    assert line["logger"] == "config.tests.json"
    assert line["message"] == "battle 7 failed"
    assert line["battle_id"] == 7
    assert "ValueError: boom" in line["exc_info"]
    assert "request" not in line
    assert line["ts"].endswith("+00:00")


# --- health / ready ---------------------------------------------------------


def test_health_is_up_without_any_dependency(client):
    # no django_db mark: touching the database here would fail the test
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_ready_200_when_postgres_and_redis_answer(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"postgres": "ok", "redis": "ok"},
    }


@pytest.mark.django_db
def test_ready_503_when_redis_is_unreachable(client, settings):
    settings.REDIS_URL = "redis://127.0.0.1:1/0"  # nothing listens on port 1
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"
    assert response.json()["checks"] == {"postgres": "ok", "redis": "error"}


@pytest.mark.django_db
def test_ready_503_when_postgres_fails(client, monkeypatch):
    def broken():
        raise RuntimeError("postgres is down")

    monkeypatch.setattr("config.health._check_postgres", broken)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["checks"] == {"postgres": "error", "redis": "ok"}


def test_production_serves_probes_over_http_for_internal_hosts():
    code = """
from django.test import Client
client = Client()
for host in ("localhost", "django", "evil.example"):
    for path in ("/health", "/ready"):
        response = client.get(path, HTTP_HOST=host)
        print(host, path, response.status_code)
"""
    result = run_production(code)
    assert result.returncode == 0, result.stderr
    # JSON log lines share stdout with the prints
    lines = [line for line in result.stdout.splitlines() if not line.startswith("{")]
    # 200 over plain HTTP (no SSL redirect) for the names used inside docker,
    # 400 for a foreign Host header
    assert lines[:4] == [
        "localhost /health 200",
        "localhost /ready 200",
        "django /health 200",
        "django /ready 200",
    ]
    assert lines[4:] == ["evil.example /health 400", "evil.example /ready 400"]


# --- production settings ----------------------------------------------------


def test_production_defaults_with_minimal_env(monkeypatch):
    prod = load_production(monkeypatch)
    assert prod.DEBUG is False
    assert prod.ALLOWED_HOSTS == ["localhost", "127.0.0.1", "django"]
    assert prod.CSRF_TRUSTED_ORIGINS == []
    assert prod.CORS_ALLOWED_ORIGINS == []
    assert prod.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
    assert prod.USE_X_FORWARDED_HOST is True
    assert prod.SECURE_SSL_REDIRECT is False
    assert prod.SESSION_COOKIE_SECURE is False
    assert prod.CSRF_COOKIE_SECURE is False
    assert prod.SECURE_HSTS_SECONDS == 0
    assert prod.DATABASES["default"]["PORT"] == "5432"


def test_production_lists_come_from_env(monkeypatch):
    prod = load_production(
        monkeypatch,
        ALLOWED_HOSTS="codebattles.online, 203.0.113.10",
        CSRF_TRUSTED_ORIGINS="https://codebattles.online",
        CORS_ALLOWED_ORIGINS="https://codebattles.online",
    )
    assert prod.ALLOWED_HOSTS == [
        "codebattles.online",
        "203.0.113.10",
        "localhost",
        "127.0.0.1",
        "django",
    ]
    assert prod.CSRF_TRUSTED_ORIGINS == ["https://codebattles.online"]
    assert prod.CORS_ALLOWED_ORIGINS == ["https://codebattles.online"]


def test_production_https_flag_turns_on_secure_cookies_and_hsts(monkeypatch):
    prod = load_production(monkeypatch, HTTPS="1")
    assert prod.SESSION_COOKIE_SECURE is True
    assert prod.CSRF_COOKIE_SECURE is True
    assert prod.SECURE_HSTS_SECONDS == 3600


def test_production_rejects_unknown_https_value(monkeypatch):
    with pytest.raises(ImproperlyConfigured, match="HTTPS must be 0 or 1"):
        load_production(monkeypatch, HTTPS="true")


@pytest.mark.parametrize("name", PROD_ENV)
def test_production_fails_without_required_variable(monkeypatch, name):
    with pytest.raises(ImproperlyConfigured, match=name):
        load_production(monkeypatch, **{name: None})


def test_production_error_lists_every_missing_variable(monkeypatch):
    with pytest.raises(ImproperlyConfigured) as excinfo:
        load_production(monkeypatch, JWT_SIGNING_KEY=None, INTERNAL_API_TOKEN="  ")
    assert "JWT_SIGNING_KEY, INTERNAL_API_TOKEN" in str(excinfo.value)


@pytest.mark.parametrize(("first", "second"), PAIRS)
def test_production_refuses_equal_secrets(monkeypatch, first, second):
    with pytest.raises(
        ImproperlyConfigured, match=f"{first} and {second} must be different"
    ):
        load_production(monkeypatch, **{second: PROD_ENV[first]})


@pytest.mark.parametrize("name", ["DJANGO_SECRET_KEY", "JWT_SIGNING_KEY", "INTERNAL_API_TOKEN"])
@pytest.mark.parametrize("weak", ["x" * 31, "change-me-" + "x" * 40])
def test_production_refuses_weak_secrets(monkeypatch, name, weak):
    with pytest.raises(ImproperlyConfigured, match=f"{name} is too weak"):
        load_production(monkeypatch, **{name: weak})


def test_django_refuses_to_start_in_production_without_a_secret():
    result = run_production("", drop=("JWT_SIGNING_KEY",))
    assert result.returncode != 0
    assert (
        "ImproperlyConfigured: Missing required environment variables: "
        "JWT_SIGNING_KEY" in result.stderr
    )


def test_check_deploy_is_clean_with_https():
    result = run_production(
        "from django.core.management import call_command\n"
        "call_command('check', deploy=True, fail_level='WARNING')",
        HTTPS="1",
    )
    assert result.returncode == 0, result.stderr


def test_check_deploy_without_https_only_complains_about_https():
    result = run_production(
        "from django.core.management import call_command\n"
        "call_command('check', deploy=True, fail_level='WARNING')",
        HTTPS="0",
    )
    assert result.returncode != 0
    for check_id in ("security.W004", "security.W012", "security.W016"):
        assert check_id in result.stderr
    assert result.stderr.count("security.W") == 3


# --- NUM_PROXIES (client IP for the throttles) --------------------------------


@pytest.mark.parametrize(("value", "expected"), [(None, 0), ("", 0), ("0", 0), ("2", 2)])
def test_production_num_proxies_defaults_to_zero_and_comes_from_env(
    monkeypatch, value, expected
):
    prod = load_production(monkeypatch, NUM_PROXIES=value)
    assert prod.REST_FRAMEWORK["NUM_PROXIES"] == expected  # None would trust any X-Forwarded-For


@pytest.mark.parametrize("value", ["-1", "two", "1.5", "²"])
def test_production_rejects_a_num_proxies_that_is_not_a_non_negative_integer(
    monkeypatch, value
):
    with pytest.raises(ImproperlyConfigured, match="NUM_PROXIES"):
        load_production(monkeypatch, NUM_PROXIES=value)


# --- API error handling -----------------------------------------------------


def run_view_raising(exc):
    """Call a DRF view that raises `exc`, the way a real request would, and render the answer."""

    class Boom(APIView):
        permission_classes = (AllowAny,)

        def get(self, request):
            raise exc

    response = Boom.as_view()(APIRequestFactory().get("/"))
    response.render()
    return response


@pytest.mark.parametrize(
    ("exc", "status", "body"),
    [
        (DjangoValidationError("Battle is full"), 400, {"errors": ["Battle is full"]}),
        (
            DjangoValidationError({"duration": ["Invalid duration"]}),
            400,
            {"duration": ["Invalid duration"]},
        ),
        (ObjectDoesNotExist("x"), 404, {"detail": "Not found."}),
        (Task.DoesNotExist(), 404, {"detail": "Not found."}),
        (Http404("No such battle"), 404, {"detail": "No such battle"}),
        (IntegrityError("duplicate key value\nDETAIL: Key (email)=(a@b.co)"), 409, {"detail": "Conflict."}),
        (ConflictError(), 409, {"detail": "Conflict."}),
        (ConflictError("Battle is full"), 409, {"detail": "Battle is full"}),
        (ForbiddenError(), 403, {"detail": "You do not have permission to perform this action."}),
        (ForbiddenError("Only the creator"), 403, {"detail": "Only the creator"}),
        (PermissionDenied(), 403, {"detail": "You do not have permission to perform this action."}),
        (RuntimeError("secret internal detail"), 500, {"error": "internal_error"}),
        (KeyError("task"), 500, {"error": "internal_error"}),
    ],
)
def test_api_errors_are_json_even_with_debug_on(settings, exc, status, body):
    settings.DEBUG = True  # without the handler DRF re-raises and Django prints an HTML page
    response = run_view_raising(exc)
    assert response.status_code == status
    assert response["Content-Type"].startswith("application/json")
    assert json.loads(response.content) == body


def test_unhandled_exception_is_logged_with_its_traceback(caplog):
    with caplog.at_level(logging.ERROR, logger="config.exceptions"):
        run_view_raising(RuntimeError("secret internal detail"))

    (record,) = [r for r in caplog.records if r.name == "config.exceptions"]
    assert record.getMessage() == "Unhandled exception in Boom"
    assert record.exc_info[0] is RuntimeError


def test_integrity_error_is_logged_without_the_offending_values(caplog):
    with caplog.at_level(logging.WARNING, logger="config.exceptions"):
        run_view_raising(IntegrityError('duplicate key\nDETAIL: Key (email)=(a@b.co) exists'))

    (record,) = [r for r in caplog.records if r.name == "config.exceptions"]
    assert "a@b.co" not in record.getMessage()


def test_throttled_keeps_its_retry_after_header():
    response = run_view_raising(Throttled(wait=42))
    assert response.status_code == 429
    assert response["Retry-After"] == "42"
    assert response["Content-Type"].startswith("application/json")


# --- admin ------------------------------------------------------------------


@pytest.fixture
def sample_rows(user):
    task = Task.objects.create(
        id=7,
        name="Pentagonal numbers",
        description="d",
        cf_rating=800,
        private_tests={"input": ["secret-input"], "output": ["secret-output"]},
    )
    battle = Battle.objects.create(
        creator=user, task=task.id, type="1v1", duration=15, max_participants=2, invite_code="abc123"
    )
    return {  # by admin path
        "tasks/task": task,
        "battles/battle": battle,
        "battles/participant": Participant.objects.create(battle=battle, user=user),
        "accounts/profile": Profile.objects.create(user=user),
        "submissions/submission": Submission.objects.create(
            battle=battle, user=user, code="print(1)", status="success"
        ),
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("model", "query", "visible"),
    [
        ("tasks/task", {}, b"Pentagonal numbers"),
        ("tasks/task", {"q": "Pentagonal"}, b"Pentagonal numbers"),
        ("tasks/task", {"difficulty__isnull": "True"}, b"Pentagonal numbers"),
        ("battles/battle", {"q": "abc123"}, b"abc123"),
        ("battles/battle", {"status__exact": "pending", "type__exact": "1v1"}, b"pending"),
        ("battles/participant", {"q": "player_one"}, b"waiting"),
        ("battles/participant", {"status__exact": "waiting", "role__exact": "player"}, b"waiting"),
        ("accounts/profile", {"q": "player.one@example.com"}, b"1000"),
        ("submissions/submission", {"q": "player_one", "status__exact": "success"}, b"success"),
    ],
)
def test_admin_changelists_list_search_and_filter(admin_client, sample_rows, model, query, visible):
    response = admin_client.get(f"/admin/{model}/", query)
    assert response.status_code == 200
    assert visible in response.content


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model",
    ["tasks/task", "battles/battle", "battles/participant", "accounts/profile", "submissions/submission"],
)
def test_admin_change_pages_open(admin_client, sample_rows, model):
    pk = sample_rows[model].pk
    assert admin_client.get(f"/admin/{model}/{pk}/change/").status_code == 200


@pytest.mark.django_db
def test_admin_never_loads_or_shows_the_task_tests(admin_client, sample_rows):
    with CaptureQueriesContext(connection) as queries:
        listing = admin_client.get("/admin/tasks/task/")
        form = admin_client.get("/admin/tasks/task/7/change/")

    task_selects = [q["sql"] for q in queries if 'FROM "tasks_task"' in q["sql"]]
    assert task_selects
    # the JSON test columns; the small public_tests_count column is fine
    heavy = ('"public_tests"', '"private_tests"', '"generated_tests"')
    assert not any(col in sql for sql in task_selects for col in heavy)
    assert b"secret-input" not in listing.content + form.content
    assert b"private_tests" not in form.content


@pytest.mark.django_db
def test_saving_a_task_in_the_admin_keeps_its_tests(admin_client, sample_rows):
    response = admin_client.post(
        "/admin/tasks/task/7/change/",
        {
            "name": "Renamed",
            "description": "d",
            "difficulty": "7",
            "source": "2",
            "cf_index": "A",
            "cf_rating": "800",
            "cf_tags": "[]",
            "time_limit": "null",
            "input_file": "",
            "output_file": "",
        },
    )
    assert response.status_code == 302, response.content[:2000]
    task = Task.objects.get(id=7)
    assert task.name == "Renamed"
    assert task.private_tests == {"input": ["secret-input"], "output": ["secret-output"]}
