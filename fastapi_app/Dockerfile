# FastAPI: REST /api/tasks and WebSocket /ws. Build context: fastapi_app/
# One uvicorn process on purpose: battle state and limits live in Redis, but the in-process
# supervisors (idle listener, deadlines) are written for a single worker.

FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY . .

FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
LABEL org.opencontainers.image.title="code-battles-fastapi"
RUN groupadd --gid 10001 app \
 && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
COPY --from=builder /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=4s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]
# Behind the web proxy: trust X-Forwarded-* from it. 262144 = WS message cap (256 KiB).
# --workers 1 explicit: uvicorn would otherwise read WEB_CONCURRENCY from the shared .env
CMD ["uvicorn", "main:app", "--workers", "1", "--host", "0.0.0.0", "--port", "8000","--proxy-headers", "--forwarded-allow-ips=*", "--ws-max-size", "262144", "--timeout-graceful-shutdown", "20"]
