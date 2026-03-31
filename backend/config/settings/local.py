# export DJANGO_SETTINGS_MODULE=config.settings.local
# RUN IT IN TERMINAL TO SET PROPER FILE FOR SETTINGS
# AND CHANGE os.environ.setdefault IN manage.py, asgi.py, wsgi.py

import os

from .base import *

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

ALLOWED_HOSTS = ["*"]

DEBUG = True

REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = os.environ["REDIS_PORT"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["POSTGRES_DB"],
        "USER": os.environ["POSTGRES_USER"],
        "PASSWORD": os.environ["POSTGRES_PASSWORD"],
        "HOST": os.environ["POSTGRES_HOST"],
        "PORT": 5432,
    }
}

CORS_ALLOW_ALL_ORIGINS = True
