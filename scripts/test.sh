#!/usr/bin/env bash
# Django + FastAPI test suites against throwaway Postgres and Redis (docker, loopback ports
# 55432 / 56379), removed afterwards. Needs uv. Run from anywhere: scripts/test.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

cleanup() { docker rm -f cbt-pg cbt-redis > /dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup
docker run -d --rm --name cbt-pg -e POSTGRES_DB=cb -e POSTGRES_USER=cb -e POSTGRES_PASSWORD=cb_pw \
    -p 127.0.0.1:55432:5432 postgres:16-alpine > /dev/null
docker run -d --rm --name cbt-redis -p 127.0.0.1:56379:6379 redis:7-alpine > /dev/null
until docker exec cbt-pg pg_isready -U cb -d cb > /dev/null 2>&1; do sleep 1; done

(cd backend && uv sync --frozen -q &&
    POSTGRES_DB=cb POSTGRES_USER=cb POSTGRES_PASSWORD=cb_pw POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=55432 \
    REDIS_URL=redis://127.0.0.1:56379/0 .venv/bin/python -m pytest -q)
(cd fastapi_app && uv sync --frozen -q &&
    TEST_REDIS_URL=redis://127.0.0.1:56379/15 .venv/bin/python -m pytest -q)
