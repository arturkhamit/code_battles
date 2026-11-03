# ruff: noqa: S106
import itertools
import json

import pytest
import redis
from django.core.cache.backends.redis import RedisCache
from infrastructure.messaging import battle_events

from apps.battles.models import Battle
from apps.battles.throttles import BattleCreateThrottle, InviteLookupThrottle
from apps.tasks.models import Task


@pytest.fixture
def task(db):
    """Battles can only be created on a task that exists."""
    return Task.objects.create(id=1, name="162_A", description="d", cf_rating=800)


@pytest.fixture
def make_user(django_user_model):
    numbers = itertools.count(1)

    def make():
        n = next(numbers)
        return django_user_model.objects.create_user(
            username=f"user_{n}", email=f"user{n}@example.com", password="S3cure-pass!"
        )

    return make


@pytest.fixture
def make_battle(task, make_user):
    def make(creator=None, **fields):
        fields = {"type": "1v1", "task": task.id, "duration": 15, "max_participants": 2, **fields}
        return Battle.objects.create(creator=creator or make_user(), **fields)

    return make


@pytest.fixture(autouse=True)
def published(monkeypatch):
    """Events that would go to Redis, as (battle_id, event). Nothing leaves the process."""
    sent = []

    def record(channel, payload):
        sent.append((int(channel.split(":")[1]), json.loads(payload)))

    monkeypatch.setattr(battle_events.redis_client, "publish", record)
    return sent


@pytest.fixture
def redis_down(monkeypatch):
    """Redis refuses connections: both the event publisher and the throttle counters."""
    dead = "redis://127.0.0.1:1/0"  # nothing listens on port 1
    monkeypatch.setattr(
        battle_events, "redis_client", redis.Redis.from_url(dead, socket_connect_timeout=1)
    )
    for throttle in (BattleCreateThrottle, InviteLookupThrottle):
        monkeypatch.setattr(throttle, "cache", RedisCache(dead, {}))


@pytest.fixture
def internal(api, settings, django_capture_on_commit_callbacks):
    """Call an internal endpoint as FastAPI does. The on_commit hooks run when the call
    ends, as they would after a real commit (the test itself never commits)."""

    def call(method, path, body=None):
        auth = {"HTTP_AUTHORIZATION": f"Bearer {settings.INTERNAL_API_TOKEN}"}
        with django_capture_on_commit_callbacks(execute=True):
            if method == "get":
                return api.get(path, **auth)
            return getattr(api, method)(path, body or {}, format="json", **auth)

    return call
