# ruff: noqa: S101
import json

import pytest
from pydantic import ValidationError

from core.config import Settings
from services.battle_engine import BattleConnectionManager, Conn

REQUIRED = {
    "JWT_SIGNING_KEY": "jwt-key-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "INTERNAL_API_TOKEN": "internal-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "RUNNER_TOKEN": "runner-cccccccccccccccccccccccccccccccc",
}


def settings(monkeypatch, **env):
    for key in (*REQUIRED, "CORS_ALLOWED_ORIGINS", "ENVIRONMENT", "RUNNER_URL"):
        monkeypatch.delenv(key, raising=False)
    for key, value in {**REQUIRED, **env}.items():
        if value is not None:
            monkeypatch.setenv(key, value)
    return Settings(_env_file=None)


def test_missing_secrets_fail_fast_naming_the_variable(monkeypatch):
    with pytest.raises(ValidationError) as err:
        settings(monkeypatch, JWT_SIGNING_KEY=None, INTERNAL_API_TOKEN=None, RUNNER_TOKEN=None)
    assert all(name in str(err.value) for name in REQUIRED)


def test_secrets_must_differ(monkeypatch):
    with pytest.raises(ValidationError):
        settings(monkeypatch, INTERNAL_API_TOKEN=REQUIRED["JWT_SIGNING_KEY"])
    with pytest.raises(ValidationError):
        settings(monkeypatch, RUNNER_TOKEN=REQUIRED["INTERNAL_API_TOKEN"])


@pytest.mark.parametrize("name", list(REQUIRED))
@pytest.mark.parametrize("weak", ["short", "change-me-" + "x" * 40])
def test_weak_secrets_rejected_in_production_only(monkeypatch, name, weak):
    with pytest.raises(ValidationError) as err:
        settings(monkeypatch, **{name: weak})
    assert name in str(err.value)
    assert settings(monkeypatch, ENVIRONMENT="local", **{name: weak})


def test_environment_defaults_to_production_and_rejects_unknown(monkeypatch):
    assert settings(monkeypatch).is_production
    assert not settings(monkeypatch, ENVIRONMENT="local").is_production
    with pytest.raises(ValidationError):
        settings(monkeypatch, ENVIRONMENT="staging")


def test_cors_origins_are_parsed_and_must_have_a_scheme(monkeypatch):
    assert settings(monkeypatch).CORS_ALLOWED_ORIGINS == []
    parsed = settings(monkeypatch, CORS_ALLOWED_ORIGINS="http://localhost:3000, https://codebattles.online/")
    assert parsed.CORS_ALLOWED_ORIGINS == ["http://localhost:3000", "https://codebattles.online"]
    for bad in ("localhost", "127.0.0.1:3000", "*", "http://a.example/path"):
        with pytest.raises(ValidationError):
            settings(monkeypatch, CORS_ALLOWED_ORIGINS=bad)


def test_django_ready_url_sits_next_to_internal(monkeypatch):
    s = settings(monkeypatch, DJANGO_INTERNAL_URL="http://django:8000/internal/")
    assert s.DJANGO_READY_URL == "http://django:8000/ready"


def test_uvicorn_logs_redact_token_in_query():
    import logging

    from core.logging_config import RedactTokenFilter, setup_logging

    setup_logging()
    for name in ("uvicorn.error", "uvicorn.access"):
        assert any(isinstance(f, RedactTokenFilter) for f in logging.getLogger(name).filters)

    # uvicorn.error: '%s - "WebSocket %s" [accepted]'; uvicorn.access: '%s - "%s %s HTTP/%s" %d'
    ws = logging.LogRecord("uvicorn.error", logging.INFO, "", 0, '%s - "WebSocket %s" [accepted]',
                           ("1.2.3.4:5", "/ws/battle/2?token=eyJhbGciOi.eyJzdWIi.sig"), None)
    http = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                             ("1.2.3.4:5", "GET", "/x?a=1&token=eyJ.x.y&b=2", "1.1", 200), None)
    plain = logging.LogRecord("uvicorn.error", logging.INFO, "", 0, "Started %s", ("ok",), None)
    for record in (ws, http, plain):
        assert RedactTokenFilter().filter(record)
    assert ws.getMessage() == '1.2.3.4:5 - "WebSocket /ws/battle/2?token=***" [accepted]'
    assert http.getMessage() == '1.2.3.4:5 - "GET /x?a=1&token=***&b=2 HTTP/1.1" 200'
    assert plain.getMessage() == "Started ok" and plain.args == ("ok",)


class _Socket:
    def __init__(self, fail=False):
        self.fail, self.sent = fail, []

    async def send_json(self, event):
        if self.fail:
            raise RuntimeError("socket is gone")
        self.sent.append(event)


async def test_a_dead_socket_does_not_stop_the_fan_out():
    manager = BattleConnectionManager()
    dead, alive = _Socket(fail=True), _Socket()
    manager.local_sockets[1] = {
        1: Conn(dead, 1, 1, "a", "player", 1),
        2: Conn(alive, 1, 2, "b", "player", 1),
    }
    await manager._dispatch(1, json.dumps({"event": "chat_message", "data": {}}))
    assert alive.sent == [{"event": "chat_message", "data": {}}]

    await manager._dispatch(1, json.dumps({"event": "execution_result", "data": {}, "_target_user_id": 2}))
    assert alive.sent[-1]["event"] == "execution_result" and "_target_user_id" not in alive.sent[-1]
    assert dead.sent == []
    await manager._dispatch(1, "not json")  # dropped, no exception
