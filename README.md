# code_battles

Code duels: Django (accounts, battles, tasks) + FastAPI (REST tasks, WebSocket battles) + React SPA.
User code runs in sandbox containers started by `runner/` through a socket proxy. Everything runs from
one `compose.yaml`; the only published port is `web` on `127.0.0.1:8010`.

```
shared Caddy (server) -> 127.0.0.1:8010 -> web (SPA + routing) -> django:8000   /api/accounts, /api/battles, /admin (SSH tunnel only), /static, /health, /ready
                                                                -> fastapi:8000 /api/tasks, /ws
                                          postgres, redis, runner -> docker-proxy -> sandboxes (internal networks)
```

`/internal/*`, `/docs`, `/redoc`, `/openapi.json` answer 404 at the entry point.

## Run locally

Needs Docker and `uv` (tests only), Node only for `make lint`.

```
cp .env.example .env          # replace every change-me (openssl rand -hex 32); for localhost set
                              # ALLOWED_HOSTS= (empty) and CSRF_TRUSTED_ORIGINS=http://localhost:8010
make sandbox-images           # once: images the runner starts (it never pulls)
make up                       # build + start, waits until healthy
make import-tasks             # needs backend/tests/tests.json (not in git)
make createsuperuser
```

Open http://localhost:8010. `make logs s=django`, `make shell`, `make down` (data volumes stay).
For work without Docker for the apps: `backend/.env.example` and `fastapi_app/.env.example`.

## Tests, lint, dependencies

```
make test         # Django (296) + FastAPI (76) against throwaway postgres/redis; needs uv
make lint         # ruff (F,E9,B) for both backends, eslint for the frontend
make migration name=add_x     # on the host, needs backend/.env
make update-deps  # uv lock --upgrade, npm update, pip-audit
```

Dependencies: `backend/pyproject.toml` + `uv.lock`, `fastapi_app/pyproject.toml` + `uv.lock`; group `dev`
for tests, group `dataset` (`uv sync --group dataset`) only for `backend/tests/main.py`, which downloads the dataset.

## Deploy, rollback

See `deploy/README.md`. In short: `make deploy` (rsync + `deploy/deploy.sh` over ssh), `make rollback`.
Server and path are `SERVER=ubuntu@your-server`, `DEPLOY_PATH=~/arthur/code_battles` (override on the
command line).

## Backup and restore

```
make backup                                   # backups/daily/*.dump (pg_dump -Fc, checked with pg_restore -l)
make restore file=backups/daily/code_battles-20261029-030000.dump   # stops web/django/fastapi, replaces data
```

Kept: 7 daily and 4 weekly dumps, in `backups/` next to the project. Redis (AOF in the `redis_data` volume)
only holds live battle state and counters, it is not backed up.

## Cron on the server (`crontab -e` as the user that runs docker)

```
# daily backup at 03:00
0 3 * * *  cd ~/arthur/code_battles && scripts/backup.sh >> backups/backup.log 2>&1
# close pending battles nobody joined, hourly
7 * * * *  cd ~/arthur/code_battles && make expire-battles >> logs/cron.log 2>&1
# drop expired JWT blacklist rows, daily at 03:30
30 3 * * * cd ~/arthur/code_battles && make flush-tokens >> logs/cron.log 2>&1
# monitoring: /health every 5 minutes (alert hook of your choice instead of logger)
*/5 * * * * curl -fsS -m 10 http://127.0.0.1:8010/health >/dev/null || logger -t code_battles "health check failed"
```

`mkdir -p ~/arthur/code_battles/logs` first. An external monitor on `http://<site>/health` is better than
the local one. Watch also: disk (`df -h`), leftover sandbox containers
(`docker ps -a --filter label=cb.sandbox=1`; the runner's reaper removes them after 2 minutes).

## Layout

| | |
|---|---|
| `backend/` | Django, `Dockerfile`, gunicorn (gthread; `WEB_CONCURRENCY`, `GUNICORN_THREADS`) |
| `fastapi_app/` | FastAPI, `Dockerfile` (one uvicorn process) |
| `frontend/` | React SPA, `Dockerfile` (build -> Caddy), `Caddyfile` is the routing table |
| `runner/` | sandbox runner and the sandbox images, see `runner/README.md` |
| `compose.yaml` | the stack; profiles `tools` (import-tasks) and `build-only` (sandbox images) |
| `deploy/` | production override, `deploy.sh`, `rollback.sh`, Caddy block for the server |
| `scripts/` | `backup.sh`, `test.sh` |
