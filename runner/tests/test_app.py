"""The HTTP layer of the runner with a fake sandbox behind it (no Docker)."""

import asyncio
import threading
import time

import httpx
import pytest

from app.config import Settings
from app.executor import SandboxError
from app.main import create_app

TOKEN = "test-runner-token-0123456789abcdef0123456"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
BODY = {
    "language": "python", "code": "print(1)",
    "tests": {"public": [{"input": "1", "output": "1"}], "hidden": [{"input": "SECRET-IN", "output": "SECRET-OUT"}]},
}


class FakeSandbox:
    def __init__(self):
        self.calls = []
        self.answer = {"verdict": "OK", "passed": 2, "time_ms": 5, "memory_kb": 0}
        self.delay = 0.0
        self.error = None
        self.running = 0
        self.peak = 0
        self.lock = threading.Lock()
        self.checks = {"docker": "ok", "image_python": "ok", "image_cpp": "ok"}

    def judge(self, req):
        with self.lock:
            self.running += 1
            self.peak = max(self.peak, self.running)
        try:
            self.calls.append(req)
            time.sleep(self.delay)
            if self.error:
                raise self.error
            return self.answer
        finally:
            with self.lock:
                self.running -= 1

    def check(self):
        return self.checks


def make(sandbox, **overrides):
    settings = Settings(RUNNER_TOKEN=TOKEN, ENVIRONMENT="production", _env_file=None, **overrides)
    return create_app(settings, sandbox=sandbox)


def client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://runner")


@pytest.fixture
def sandbox():
    return FakeSandbox()


async def test_health_needs_no_token_and_no_docker(sandbox):
    async with client(make(sandbox)) as c:
        assert (await c.get("/health")).json() == {"status": "ok"}


async def test_ready_is_200_when_docker_and_images_are_there_else_503(sandbox):
    async with client(make(sandbox)) as c:
        assert (await c.get("/ready")).status_code == 200
        sandbox.checks = {"docker": "ok", "image_python": "ok", "image_cpp": "error"}
        response = await c.get("/ready")
        assert response.status_code == 503 and response.json()["checks"]["image_cpp"] == "error"


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer nope"}, {"Authorization": TOKEN}, {"Authorization": "Basic " + TOKEN}])
async def test_run_without_the_right_token_is_401_and_runs_nothing(sandbox, headers):
    async with client(make(sandbox)) as c:
        response = await c.post("/run", json=BODY, headers=headers)
    assert response.status_code == 401 and sandbox.calls == []


async def test_run_returns_the_verdict(sandbox):
    async with client(make(sandbox)) as c:
        response = await c.post("/run", json=BODY, headers=AUTH)
    assert response.status_code == 200
    assert response.json() == {"verdict": "OK", "passed": 2, "total": 2, "failed_test": None,
                               "time_ms": 5, "memory_mb": None}


async def test_a_hidden_failure_leaves_the_runner_as_a_number_and_a_verdict(sandbox):
    sandbox.answer = {"verdict": "WA", "passed": 1, "failed_index": 1, "time_ms": 5, "memory_kb": 0,
                      "detail": {"actual": "SECRET-ACTUAL", "stderr": "SECRET-ERR", "reason": "SECRET-WHY"}}
    async with client(make(sandbox)) as c:
        response = await c.post("/run", json=BODY, headers=AUTH)
    assert response.json()["failed_test"] == {"number": 2, "hidden": True}
    assert "SECRET" not in response.text


async def test_the_request_cannot_carry_container_options(sandbox):
    body = {**BODY, "privileged": True, "binds": ["/:/host"], "network_mode": "host", "image": "evil"}
    async with client(make(sandbox)) as c:
        response = await c.post("/run", json=body, headers=AUTH)
    assert response.status_code == 200
    assert not hasattr(sandbox.calls[0], "privileged") and not hasattr(sandbox.calls[0], "image")


async def test_bad_requests_are_422_without_echoing_the_input(sandbox):
    async with client(make(sandbox)) as c:
        for body in ({**BODY, "language": "java"}, {**BODY, "tests": {}}, {"language": "python"}):
            response = await c.post("/run", json=body, headers=AUTH)
            assert response.status_code == 422 and "SECRET" not in response.text
            assert response.json()["error"] == "invalid_request"


async def test_a_huge_body_is_refused_before_it_is_read(sandbox):
    async with client(make(sandbox)) as c:
        response = await c.post("/run", content=b"{}", headers={**AUTH, "Content-Length": str(500 << 20)})
    assert response.status_code == 413


async def test_a_sandbox_failure_is_a_503_with_no_details(sandbox):
    sandbox.error = SandboxError("docker: ConnectionError: tcp://docker-proxy:2375 refused")
    async with client(make(sandbox)) as c:
        response = await c.post("/run", json=BODY, headers=AUTH)
    assert response.status_code == 503 and response.json() == {"error": "sandbox_unavailable"}
    assert "docker-proxy" not in response.text


async def test_never_more_runs_at_once_than_the_limit_and_the_rest_wait(sandbox):
    sandbox.delay = 0.15
    app = make(sandbox, RUNNER_MAX_CONCURRENCY=3, RUNNER_QUEUE_TIMEOUT_SECONDS=10)
    async with client(app) as c:
        responses = await asyncio.gather(*[c.post("/run", json=BODY, headers=AUTH) for _ in range(20)])
    assert all(r.status_code == 200 for r in responses)
    assert sandbox.peak == 3 and len(sandbox.calls) == 20


async def test_a_full_runner_answers_busy_after_the_queue_timeout(sandbox):
    sandbox.delay = 0.6
    app = make(sandbox, RUNNER_MAX_CONCURRENCY=1, RUNNER_QUEUE_TIMEOUT_SECONDS=0.1)
    async with client(app) as c:
        first = asyncio.create_task(c.post("/run", json=BODY, headers=AUTH))
        await asyncio.sleep(0.1)
        second = await c.post("/run", json=BODY, headers=AUTH)
        assert second.status_code == 503 and second.json() == {"error": "busy"}
        assert (await first).status_code == 200
        # the slot comes back: the next request is served
        assert (await c.post("/run", json=BODY, headers=AUTH)).status_code == 200


def test_settings_refuse_a_short_or_placeholder_token():
    with pytest.raises(ValueError, match="RUNNER_TOKEN"):
        Settings(RUNNER_TOKEN="short", _env_file=None)
    with pytest.raises(ValueError, match="placeholder"):
        Settings(RUNNER_TOKEN="change-me-" + "x" * 30, _env_file=None)
    assert Settings(RUNNER_TOKEN="change-me-" + "x" * 30, ENVIRONMENT="local", _env_file=None)


class FakeDockerApi:
    """Counts live containers: +1 on create, -1 on remove."""

    def __init__(self):
        self.live, self.peak, self.n = set(), 0, 0
        self.lock = threading.Lock()

    def create_container(self, command, **_):
        with self.lock:
            self.n += 1
            cid = f"c{self.n}-{command[0]}"
            self.live.add(cid)
            self.peak = max(self.peak, len(self.live))
        return {"Id": cid}

    def remove_container(self, cid, **_):
        time.sleep(0.02)  # removal is slow: a slot given back before it would show as a peak
        with self.lock:
            self.live.discard(cid)

    def create_host_config(self, **_):
        return {}

    def attach_socket(self, cid, **_):
        return type("S", (), {"cid": cid, "close": lambda self: None})()

    def start(self, cid):
        time.sleep(0.02)

    def wait(self, cid, **_):
        return {"StatusCode": 0}

    def inspect_container(self, cid):
        return {"State": {}}


@pytest.mark.parametrize("language", ["python", "cpp"])
async def test_live_sandbox_containers_never_exceed_the_limit(monkeypatch, language):
    from types import SimpleNamespace

    from app import executor
    from app.executor import Sandbox

    def fake_read(raw, frames, deadline):
        frames.out += (b'{"ok": true, "size": 0}\n' if raw.cid.endswith("compile")
                       else b'{"verdict": "OK", "passed": 2, "total": 2}\n')
        return True

    monkeypatch.setattr(executor.protocol, "send_all", lambda *a: True)
    monkeypatch.setattr(executor.protocol, "read_until_closed", fake_read)
    api = FakeDockerApi()
    settings = Settings(RUNNER_TOKEN=TOKEN, ENVIRONMENT="production", _env_file=None,
                        RUNNER_MAX_CONCURRENCY=4, RUNNER_QUEUE_TIMEOUT_SECONDS=30)
    app = create_app(settings, sandbox=Sandbox(SimpleNamespace(api=api), settings))
    body = {**BODY, "language": language}
    async with client(app) as c:
        responses = await asyncio.gather(*[c.post("/run", json=body, headers=AUTH) for _ in range(20)])
    assert all(r.status_code == 200 for r in responses), [r.text for r in responses if r.status_code != 200]
    assert 0 < api.peak <= 4 and not api.live
    assert api.n == (40 if language == "cpp" else 20)  # cpp: compile + run, both inside one slot


def test_the_docker_url_and_api_version_come_from_the_settings():
    from app.executor import make_client

    settings = Settings(RUNNER_TOKEN=TOKEN, SANDBOX_DOCKER_URL="tcp://docker-proxy:2375", _env_file=None)
    api = make_client(settings).api
    assert "docker-proxy" in api.base_url and api._version == "1.44"  # fixed: no GET /version
