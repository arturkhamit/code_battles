# The runner service (not the sandbox images: those are runner/sandbox/*/Dockerfile).
# Build context: runner/
FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159 AS build
RUN pip install --no-cache-dir uv==0.12.23
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12-slim@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159
RUN groupadd --gid 10002 runner \
 && useradd --uid 10002 --gid 10002 --no-create-home --shell /usr/sbin/nologin runner
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY app ./app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
USER 10002:10002
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=4s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]
# One process: the concurrency limit and the queue live in it. A run takes up to ~75 s, so the
# graceful stop waits that long for the runs in flight.
# --workers 1 explicit: semaphore is per-process, WEB_CONCURRENCY from shared .env would multiply sandboxes
CMD ["uvicorn", "app.main:get_app", "--factory", "--workers", "1","--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "80"]
