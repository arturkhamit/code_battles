# Django API. Build context: backend/
# Migrations are NOT run here: compose has a one-shot `migrate` service.

FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
# Code lives in /app/backend, so STATIC_ROOT (BASE_DIR.parent / "staticfiles") is /app/staticfiles
WORKDIR /app/backend
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY . .
# collectstatic needs settings to load: throwaway build-time values, they do not reach the image
RUN DJANGO_SECRET_KEY=build-only-secret-key-aaaaaaaaaaaaaaaaaaaaaaaa \
    JWT_SIGNING_KEY=build-only-jwt-key-bbbbbbbbbbbbbbbbbbbbbbbbbbbbb \
    INTERNAL_API_TOKEN=build-only-internal-token-cccccccccccccccccc \
    POSTGRES_DB=x POSTGRES_USER=x POSTGRES_PASSWORD=x POSTGRES_HOST=x \
    REDIS_URL=redis://x:6379/0 \
    .venv/bin/python manage.py collectstatic --noinput

FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
LABEL org.opencontainers.image.title="code-battles-django"
RUN groupadd --gid 10001 app \
 && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app/backend
COPY --from=builder /app /app
ENV PATH="/app/backend/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    WEB_CONCURRENCY=2 \
    GUNICORN_THREADS=4
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=4s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]
# exec form: SIGTERM reaches gunicorn. Workers and threads come from WEB_CONCURRENCY / GUNICORN_THREADS.
CMD ["gunicorn", "--config", "gunicorn.conf.py", "config.wsgi:application"]
