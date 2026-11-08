# ruff: noqa: S101, S106
import asyncio
import json
import time

import httpx
import pytest
import redis.asyncio as aioredis

from core.auth import decode_access_token
from core.config import settings
from infrastructure.redis import client as redis_module
from services import django_callbacks

from .conftest import CORRECT, FAIL_HIDDEN, SLOW, next_id, token_for
from .test_ws_battle import _eventually, two_players

pytestmark = pytest.mark.usefixtures("server")


# --- health, ready, docs ----------------------------------------------------------------------


async def test_health_is_always_200(server):
    response = await server.rest("GET", "/health")
    assert response.status_code == 200 and response.json() == {"status": "ok"}


async def test_ready_ok(server):
    response = await server.rest("GET", "/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"redis": "ok", "django": "ok"}}


async def test_ready_503_when_django_is_not_ready(server):
    server.fake.ready_status = 503  # e.g. Django up, Postgres down
    try:
        response = await server.rest("GET", "/ready")
    finally:
        server.fake.ready_status = 200
    assert response.status_code == 503
    assert response.json()["checks"] == {"redis": "ok", "django": "error"}


async def test_ready_503_when_redis_is_down(server, monkeypatch):
    import main

    dead = aioredis.from_url("redis://127.0.0.1:1/0", decode_responses=True)
    monkeypatch.setattr(redis_module, "_client", dead)
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ready")
        health = await client.get("/health")
    await dead.aclose()
    assert response.status_code == 503
    assert response.json()["checks"]["redis"] == "error"
    assert health.status_code == 200  # liveness does not depend on Redis


async def test_ws_without_redis_closes_1011_cleanly(server, monkeypatch):
    dead = aioredis.from_url("redis://127.0.0.1:1/0", decode_responses=True)
    monkeypatch.setattr(redis_module, "_client", dead)  # the server thread reads the same module
    try:
        ws = await server.connect(next_id(), next_id())
        code, _ = await ws.closed()
    finally:
        monkeypatch.undo()
        await dead.aclose()
    assert code == 1011


async def test_docs_are_closed_in_production(server):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert (await server.rest("GET", path)).status_code == 404


# --- tasks API --------------------------------------------------------------------------------


async def test_task_list_passes_difficulty_label_and_api_prefixed_links(server):
    user = next_id()
    response = await server.rest("GET", "/api/tasks/?limit=1&offset=1", user)
    body = response.json()
    assert response.status_code == 200
    assert body["results"][0]["difficulty_label"] == "easy"
    assert body["results"][0]["id"] == 1
    assert body["next"] == "/api/tasks/?limit=1&offset=2"
    assert body["previous"] == "/api/tasks/?limit=1&offset=0"


async def test_task_list_forwards_only_whitelisted_filters_and_keeps_them_in_links(server):
    server.fake.catalog_queries.clear()
    query = "search=graph&difficulty=easy,hard&tags=math&source=codeforces&ordering=-cf_rating"
    response = await server.rest("GET", f"/api/tasks/?limit=1&{query}&evil=1", next_id())
    assert response.status_code == 200
    sent = server.fake.catalog_queries[-1]
    assert sent == {"search": "graph", "difficulty": "easy,hard", "tags": "math",
                    "source": "codeforces", "ordering": "-cf_rating", "limit": "1", "offset": "0"}
    assert "ordering=-cf_rating" in response.json()["next"]
    assert "internal" not in response.json()["results"][0]  # only the catalog item keys


@pytest.mark.parametrize(
    "query", ["ordering=description", "difficulty=trivial", "source=Code%20Forces", "rating_min=-1"]
)
async def test_task_list_rejects_values_outside_the_whitelist(server, query):
    response = await server.rest("GET", f"/api/tasks/?{query}", next_id())
    assert response.status_code == 422


async def test_task_facets_pass_through(server):
    body = (await server.rest("GET", "/api/tasks/facets/", next_id())).json()
    assert body["tags"] == [{"value": "math", "count": 3}]


async def test_random_task_picks_within_the_filtered_count(server):
    server.fake.catalog_queries.clear()
    response = await server.rest("GET", "/api/tasks/random?difficulty=hard&ordering=name", next_id())
    assert response.status_code == 200
    assert response.json()["id"] == 1
    count_query, pick_query = server.fake.catalog_queries[-2:]
    assert 0 <= int(pick_query["offset"]) < 3
    assert count_query["difficulty"] == pick_query["difficulty"] == "hard"
    assert "ordering" not in pick_query


async def test_random_task_is_404_when_nothing_matches(server):
    server.fake.catalog_count = 0
    try:
        response = await server.rest("GET", "/api/tasks/random?search=zzz", next_id())
    finally:
        server.fake.catalog_count = 3
    assert response.status_code == 404


async def test_task_list_requires_a_token(server):
    assert (await server.rest("GET", "/api/tasks/")).status_code in (401, 403)


async def test_django_down_is_503_not_404(server):
    server.fake.down = True
    try:
        listing = await server.rest("GET", "/api/tasks/", next_id())
        info = await server.rest("GET", "/api/tasks/1/info", next_id())
    finally:
        server.fake.down = False
    assert listing.status_code == 503 and info.status_code == 503


async def test_info_has_public_tests_only(server):
    body = (await server.rest("GET", "/api/tasks/1/info", next_id())).json()
    assert body["public_tests"] == {"input": ["1\n"], "output": ["1"]}
    blob = json.dumps(body)
    for secret in ("PRIVATE-IN-555", "HIDDEN-IN-777", "HIDDEN-OUT-888"):
        assert secret not in blob


async def test_rest_submit_hides_the_hidden_test(server):
    response = await server.rest(
        "POST", "/api/tasks/1/submit", next_id(), json={"language": "python", "code": FAIL_HIDDEN}
    )
    result = response.json()
    assert result["hidden"] is True and result["test_number"] == 2
    assert "HIDDEN-IN-777" not in response.text and "HIDDEN-OUT-888" not in response.text

    public = await server.rest(
        "POST", "/api/tasks/1/submit", next_id(), json={"language": "python", "code": "WRONG"}
    )
    assert public.json()["hidden"] is False and "Expected:\n1" in public.json()["details"]


# --- limits -----------------------------------------------------------------------------------


async def test_rest_submit_cooldown_gives_429_with_retry_after(server):
    user = next_id()
    first = await server.rest("POST", "/api/tasks/1/submit", user, json={"language": "python", "code": CORRECT})
    second = await server.rest("POST", "/api/tasks/1/submit", user, json={"language": "python", "code": CORRECT})
    assert first.status_code == 200 and first.json()["is_correct"] is True
    assert second.status_code == 429
    assert int(second.headers["Retry-After"]) >= 1
    assert second.json()["code"] == "rate_limited"
    assert second.json()["retry_after"] == int(second.headers["Retry-After"])
    await asyncio.sleep(1.1)
    third = await server.rest("POST", "/api/tasks/1/submit", user, json={"language": "python", "code": CORRECT})
    assert third.status_code == 200


async def test_ws_submit_cooldown_is_rate_limited(server):
    battle, a, b, ws_a, ws_b = await two_players(server)
    await ws_a.send(action="start_battle_request")
    await ws_a.wait_for("battle_started")
    await ws_a.send(action="submit_code", language="python", code="WRONG")
    await ws_a.wait_for("execution_result")
    await ws_a.send(action="submit_code", language="python", code="WRONG")
    error = await ws_a.wait_for("error")
    assert error["data"]["code"] == "rate_limited" and error["data"]["retry_after"] >= 1


async def test_one_run_per_user_across_rest_and_ws(server, monkeypatch):
    monkeypatch.setattr(settings, "SUBMIT_COOLDOWN_SECONDS", 0)  # isolate the per-user slot
    battle, a, b, ws_a, ws_b = await two_players(server)
    await ws_a.send(action="start_battle_request")
    await ws_a.wait_for("battle_started")
    await ws_b.send(action="submit_code", language="python", code=SLOW)  # runs 1.5 s
    await ws_b.wait_for("opponent_running_code")
    response = await server.rest(
        "POST", "/api/tasks/1/submit", b, json={"language": "python", "code": CORRECT}
    )
    assert response.status_code == 429 and response.json()["scope"] == "user_runs"
    await ws_b.wait_for("battle_finished", timeout=5)  # the slow run still finishes normally


async def test_server_wide_run_semaphore(server):
    # MAX_CONCURRENT_RUNS is 2 in the tests: of three users running at once one is refused
    users = [next_id() for _ in range(3)]

    async def submit(user):
        return (await server.rest(
            "POST", "/api/tasks/1/submit", user, json={"language": "python", "code": SLOW}
        )).status_code

    codes = sorted(await asyncio.gather(*(submit(u) for u in users)))
    assert codes == [200, 200, 429]
    # and the slots are given back
    assert (await submit(next_id())) == 200


async def test_ws_connect_limit_per_minute(server):
    user = next_id()
    for _ in range(20):
        ws = await server.connect(987654322, user)  # unknown battle: closed at once
        assert (await ws.closed())[0] == 4404
    ws = await server.connect(987654322, user)
    code, _ = await ws.closed()
    assert code == 4429
    error = next(m for m in ws.seen if m["event"] == "error")
    assert error["data"]["code"] == "rate_limited"
    assert 1 <= error["data"]["retry_after"] <= 60


# --- finish outbox ----------------------------------------------------------------------------


async def test_finish_result_survives_a_django_outage(server, redis_sync, monkeypatch):
    monkeypatch.setattr(django_callbacks, "OUTBOX_MAX_DELAY", 1.0)
    battle, a, b, ws_a, ws_b = await two_players(server)
    await ws_a.send(action="start_battle_request")
    await ws_a.wait_for("battle_started")

    server.fake.finish_status = 503
    await ws_b.send(action="submit_code", language="python", code=CORRECT)
    done = await ws_a.wait_for("battle_finished")  # players are told at once
    assert done["data"]["winner_id"] == b

    await _eventually(lambda: any(json.loads(i)["battle_id"] == battle for i in redis_sync.lrange("outbox:finish", 0, -1)))
    assert (battle, b) not in server.fake.finishes

    server.fake.finish_status = 200
    await _eventually(lambda: (battle, b) in server.fake.finishes, timeout=20)
    await _eventually(lambda: not any(json.loads(i)["battle_id"] == battle for i in redis_sync.lrange("outbox:finish", 0, -1)))


async def test_outbox_drops_an_entry_django_refuses_for_good(server, redis_sync, monkeypatch):
    monkeypatch.setattr(django_callbacks, "OUTBOX_MAX_DELAY", 1.0)
    battle = next_id()
    server.fake.finish_status = 409
    redis_sync.rpush("outbox:finish", json.dumps({"battle_id": battle, "winner_id": 5}))
    try:
        await _eventually(lambda: not any(json.loads(i)["battle_id"] == battle for i in redis_sync.lrange("outbox:finish", 0, -1)), timeout=10)
    finally:
        server.fake.finish_status = 200
    assert (battle, 5) not in server.fake.finishes


async def test_django_client_retries_idempotent_calls_but_not_start(server):
    calls = []

    def flaky(request):
        calls.append(request.url.path)
        if len(calls) < 3:
            return httpx.Response(503, text="down")
        return httpx.Response(200, json={"ok": True})

    original = django_callbacks._client
    django_callbacks._client = httpx.AsyncClient(transport=httpx.MockTransport(flaky))
    try:
        assert await django_callbacks.join(1, 2) == {"ok": True}
        assert len(calls) == 3
        calls.clear()
        with pytest.raises(django_callbacks.DjangoError) as err:
            await django_callbacks.start_battle(1, 2)
        assert err.value.unavailable and len(calls) == 1  # start: one try
    finally:
        await django_callbacks._client.aclose()
        django_callbacks._client = original


# --- timers survive a restart -----------------------------------------------------------------


async def test_rearm_timers_after_restart_fires_time_up(server, redis_sync):
    from services import battle_flow

    battle = next_id()
    redis_sync.set(f"battle:{battle}:deadline", time.time() + 1)  # a battle that was running
    pubsub = redis_sync.pubsub()
    pubsub.subscribe(f"battle:{battle}:events")
    server.on_loop(battle_flow.rearm_timers())

    await _eventually(lambda: (battle, None) in server.fake.finishes, timeout=6)
    messages = [json.loads(m["data"]) for m in _drain(pubsub)]
    assert any(m["event"] == "battle_finished" and m["data"]["reason"] == "time_up" for m in messages)
    assert redis_sync.get(f"battle:{battle}:deadline") is None


def _drain(pubsub):
    out = []
    while (message := pubsub.get_message(timeout=0.2)) is not None:
        if message["type"] == "message":
            out.append(message)
    return out


# --- user_id is an int ------------------------------------------------------------------------


def test_user_id_from_jwt_is_an_int():
    payload = decode_access_token(token_for(42))
    assert payload["user_id"] == 42 and isinstance(payload["user_id"], int)


def test_non_numeric_user_id_is_an_invalid_token():
    import jwt

    from .conftest import JWT_KEY

    bad = jwt.encode({"user_id": "abc", "token_type": "access"}, JWT_KEY, algorithm="HS256")
    with pytest.raises(ValueError):
        decode_access_token(bad)
