# Default settings module for manage.py / wsgi.py / asgi.py.
# Runs behind Caddy -> web -> django: TLS ends at Caddy, Django sees plain HTTP.

import itertools
import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import INTERNAL_API_TOKEN, JWT_SIGNING_KEY, SECRET_KEY

DEBUG = False

# A leaked JWT key must not open the internal API (and vice versa).
_secrets = {
    "DJANGO_SECRET_KEY": SECRET_KEY,
    "JWT_SIGNING_KEY": JWT_SIGNING_KEY,
    "INTERNAL_API_TOKEN": INTERNAL_API_TOKEN,
}
for _name, _value in _secrets.items():
    if len(_value) < 32 or _value.startswith("change-me"):
        raise ImproperlyConfigured(
            f"{_name} is too weak for production: use 32+ random characters."
        )
for (_name_a, _value_a), (_name_b, _value_b) in itertools.combinations(
    _secrets.items(), 2
):
    if _value_a == _value_b:
        raise ImproperlyConfigured(
            f"{_name_a} and {_name_b} must be different values in production."
        )

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
# Caddy redirects http -> https; Django itself must keep answering plain HTTP
# (internal calls to http://django:8000, healthchecks).
SECURE_SSL_REDIRECT = False

# HTTPS=0: the site is served over plain HTTP (by IP, for now).
# HTTPS=1: served over TLS (domain) -> secure cookies and HSTS.
_https = os.environ.get("HTTPS", "0").strip()
if _https not in ("0", "1"):
    raise ImproperlyConfigured(f"HTTPS must be 0 or 1, got {_https!r}.")
HTTPS = _https == "1"
SESSION_COOKIE_SECURE = HTTPS
CSRF_COOKIE_SECURE = HTTPS
# Start small; raise it once TLS has proven stable.
SECURE_HSTS_SECONDS = 3600 if HTTPS else 0

SILENCED_SYSTEM_CHECKS = [
    # No includeSubDomains / preload on purpose: the shared server hosts other sites.
    "security.W005",
    "security.W021",
    # SECURE_SSL_REDIRECT is False on purpose, Caddy does the redirect.
    "security.W008",
]
