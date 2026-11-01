# Local development: put DJANGO_SETTINGS_MODULE=config.settings.local into backend/.env
# (manage.py loads that file before choosing the settings module).
# Without it manage.py / wsgi.py / asgi.py use config.settings.production.

import os

# Non-secret dev default. Secrets and POSTGRES_* have no defaults on purpose.
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from .base import *  # noqa: E402,F403

DEBUG = True
# runserver uses a new thread per connection, so persistent DB connections leak (one per TCP connection).
DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405
