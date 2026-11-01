# ruff: noqa: S105
# Settings for pytest (see pytest.ini): local settings plus throwaway secrets.
# pytest-django loads settings before conftest.py, so the secrets live here.
# Postgres and Redis settings still come from the environment.

import os
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

os.environ.setdefault("DJANGO_SECRET_KEY", "test-django-secret-key-0123456789abcdef0123456789")
os.environ.setdefault("JWT_SIGNING_KEY", "test-jwt-signing-key-0123456789abcdef0123456789ab")
os.environ.setdefault("INTERNAL_API_TOKEN", "test-internal-api-token-0123456789abcdef012345")

from .local import *  # noqa: E402,F403
from .local import REDIS_URL  # noqa: E402

# tests never run collectstatic; without this whitenoise warns about the missing STATIC_ROOT
WHITENOISE_AUTOREFRESH = True

# Throttle counters live in the Django cache and the tests reset them with cache.clear(),
# which is FLUSHDB. Keep that on a Redis database of its own so a shared Redis is never flushed.
TEST_REDIS_DB = 15
if urlsplit(REDIS_URL).path.strip("/") == str(TEST_REDIS_DB):
    raise ImproperlyConfigured(
        f"REDIS_URL uses database {TEST_REDIS_DB}, which the tests flush. "
        "Point REDIS_URL at another database."
    )
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": urlsplit(REDIS_URL)._replace(path=f"/{TEST_REDIS_DB}").geturl(),
    }
}

# A real hash (PBKDF2, ~0.3 s) on every failed login would make the throttling tests crawl.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
