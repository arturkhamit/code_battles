# ruff: noqa: S106
import pytest
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def _fresh_throttle_counters(settings):
    """Empty the Django cache (throttle counters) before every test.

    cache.clear() is FLUSHDB, so refuse to run it on anything but the tests' own Redis
    database (config/settings/test.py).
    """
    location = settings.CACHES["default"]["LOCATION"]
    if not location.endswith(f"/{settings.TEST_REDIS_DB}"):
        raise RuntimeError(f"Refusing to flush {location}: not the test Redis database.")
    cache.clear()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="player_one", email="player.one@example.com", password="S3cure-pass!"
    )
