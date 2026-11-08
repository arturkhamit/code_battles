# ruff: noqa: S101, S106
import asyncio
import itertools
import json
import os
import threading
import time
from urllib.parse import urlsplit

import httpx
import jwt
import pytest
import redis as sync_redis
import uvicorn
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

# The settings are read when `main` is imported, so they are fixed here first. Plain assignment:
# a developer's fastapi_app/.env must not leak into the tests.
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:56381/15")
JWT_KEY = "test-jwt-signing-key-0123456789abcdef0123456789"
os.environ.update(
    ENVIRONMENT="production",
    LOG_LEVEL="WARNING",
    REDIS_URL=TEST_REDIS_URL,
    DJANGO_INTERNAL_URL="http://django.test/internal",
    RUNNER_URL="http://runner.test",
    JWT_SIGNING_KEY=JWT_KEY,
    INTERNAL_API_TOKEN="test-internal-api-token-0123456789abcdef01",
    RUNNER_TOKEN="test-runner-token-0123456789abcdef0123456",
    CORS_ALLOWED_ORIGINS="",
    MAX_CONCURRENT_RUNS="2",
    SUBMIT_COOLDOWN_SECONDS="1",
    WS_CONNECTS_PER_MINUTE="20",
)

import main  # noqa: E402
from services import django_callbacks, runner_client  # noqa: E402

from .fake_django import FakeDjango  # noqa: E402
from .fake_runner import CORRECT, FAIL_HIDDEN, SLOW, WRONG, FakeRunner  # noqa: E402, F401

_ids = itertools.count(1000)


def next_id() -> int:
    return next(_ids)


def token_for(user_id: int, username: str | None = None) -> str:
    # simplejwt puts user_id into the token as a string
    return jwt.encode(
        {"user_id": str(user_id), "username": username or f"user{user_id}",
         "token_type": "access", "exp": int(time.time()) + 600},
        JWT_KEY, algorithm="HS256",
    )


class WS:
    def __init__(self, conn):
        self.conn = conn
        self.seen: list[dict] = []

    async def send(self, **message):
        await self.conn.send(json.dumps(message))

    async def send_raw(self, text: str):
        await self.conn.send(text)

    async def wait_for(self, event: str, timeout: float = 5.0) -> dict:
        async def loop():
            async for raw in self.conn:
                message = json.loads(raw)
                self.seen.append(message)
                if message["event"] == event:
                    return message
            raise AssertionError(f"socket closed ({self.conn.close_code}) while waiting for {event}")

        try:
            return await asyncio.wait_for(loop(), timeout)
        except TimeoutError:
            raise AssertionError(f"no {event!r} within {timeout}s; got {[m['event'] for m in self.seen]}") from None

    async def closed(self, timeout: float = 5.0) -> tuple[int, str]:
        async def drain():
            try:
                async for raw in self.conn:
                    self.seen.append(json.loads(raw))
            except ConnectionClosed:
                pass

        await asyncio.wait_for(drain(), timeout)
        return self.conn.close_code, self.conn.close_reason

    def events(self) -> list[str]:
        return [m["event"] for m in self.seen]

    async def close(self):
        await self.conn.close()


class Server:
    def __init__(self, port, fake, runner, loop):
        self.port, self.fake, self.runner, self.loop = port, fake, runner, loop
        self.http = f"http://127.0.0.1:{port}"

    async def connect(self, battle_id, user_id, *, role=None, invite=None, username=None, token=None):
        query = f"token={token or token_for(user_id, username)}"
        query += f"&role={role}" if role else ""
        query += f"&invite={invite}" if invite else ""
        conn = await connect(f"ws://127.0.0.1:{self.port}/ws/battle/{battle_id}?{query}", max_size=None)
        return WS(conn)

    async def rest(self, method, path, user_id=None, **kwargs):
        headers = {"Authorization": f"Bearer {token_for(user_id)}"} if user_id else {}
        async with httpx.AsyncClient(base_url=self.http, timeout=10) as client:
            return await client.request(method, path, headers=headers, **kwargs)

    def battle(self, creator, **kwargs) -> int:
        battle_id = next_id()
        self.fake.add_battle(battle_id, creator, **kwargs)
        return battle_id

    def on_loop(self, coro):
        """Run a coroutine on the server's own event loop and wait for it."""
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(10)


@pytest.fixture(scope="session")
def redis_sync():
    client = sync_redis.Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    if urlsplit(TEST_REDIS_URL).path.strip("/") != "15":
        pytest.exit("TEST_REDIS_URL must use database 15: the tests flush it", returncode=2)
    try:
        client.flushdb()
    except sync_redis.ConnectionError:
        pytest.exit(f"Redis is not reachable at {TEST_REDIS_URL}", returncode=2)
    yield client
    client.flushdb()
    client.close()


@pytest.fixture(scope="session")
def server(redis_sync):
    fake = FakeDjango()
    runner = FakeRunner()
    django_callbacks._transport = httpx.MockTransport(fake.handler)
    runner_client._transport = httpx.MockTransport(runner.handler)
    config = uvicorn.Config(main.app, host="127.0.0.1", port=0, log_level="warning", lifespan="on")
    uv = uvicorn.Server(config)
    holder = {}

    def run():
        loop = holder["loop"] = asyncio.new_event_loop()
        loop.run_until_complete(uv.serve())

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    deadline = time.time() + 10
    while not uv.started and time.time() < deadline:
        time.sleep(0.05)
    assert uv.started, "server did not start"
    port = uv.servers[0].sockets[0].getsockname()[1]
    yield Server(port, fake, runner, holder["loop"])
    uv.should_exit = True
    thread.join(10)
    django_callbacks._transport = None
    runner_client._transport = None


@pytest.fixture(autouse=True)
def _fresh_runner(request):
    """Every test starts with a runner that has seen nothing and behaves by the code text."""
    if "server" in request.fixturenames:
        request.getfixturevalue("server").runner.reset()
