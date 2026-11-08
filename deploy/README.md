# Deploy to the server

Server: `ubuntu@your-server`, project in `~/arthur/code_battles`. The code goes over rsync from the
laptop (`make deploy`), images are built on the server, there is no registry. Only `web` listens, on
`127.0.0.1:8010`; the shared Caddy (container `caddy`, network `host`) proxies to it.

## First deploy

1. **Code.** On the laptop, in the project root:
   ```
   make deploy        # will stop at preflight: there is no .env yet. That is expected.
   ```
   It copies the project including `backend/tests/tests.json` (not in git, ~90 MB) and never `.env`.
2. **`.env`.** On the server:
   ```
   cd ~/arthur/code_battles
   cp .env.example .env
   ```
   Fill it. Four secrets (`DJANGO_SECRET_KEY`, `JWT_SIGNING_KEY`, `INTERNAL_API_TOKEN`, `RUNNER_TOKEN`) and
   two passwords (`POSTGRES_PASSWORD`, `REDIS_PASSWORD`), each from its own `openssl rand -hex 32`.
   Check `ALLOWED_HOSTS=codebattles.online`, `CSRF_TRUSTED_ORIGINS=https://codebattles.online`, `HTTPS=1`, `NUM_PROXIES=2`.
3. **Deploy.** `make deploy` on the laptop, or `bash deploy/deploy.sh` on the server. It builds the
   images (including the sandbox images), migrates, starts everything and checks `/health`, `/ready`.
4. **Tasks and admin.** On the server:
   ```
   make import-tasks            # loads backend/tests/tests.json, 1000 tasks, safe to repeat
   make createsuperuser
   ```
   `/admin` is closed from the internet (404, see `frontend/Caddyfile`). Open it through a tunnel from the
   laptop: `ssh -L 8010:127.0.0.1:8010 ubuntu@<server>`, then `http://localhost:8010/admin/`.
5. **Caddy.** Section below. Until then the site answers on `http://127.0.0.1:8010` only.

## Shared Caddy

`deploy/code_battles.caddy` is one site block. The server's `/opt/caddy/Caddyfile` is mounted into the
container as a single file, so it must be edited **in place** (same inode). An editor or `mv` that
replaces the file leaves the container looking at the old content. Append only:

```
ls -l /opt/caddy/Caddyfile                      # who owns it; if root, run the next lines with sudo
cp /opt/caddy/Caddyfile ~/Caddyfile.bak-$(date +%F)
cat ~/arthur/code_battles/deploy/code_battles.caddy >> /opt/caddy/Caddyfile     # at the end, nothing else
docker exec caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
docker exec caddy caddy reload   --config /etc/caddy/Caddyfile --adapter caddyfile
```

If `validate` fails, put the backup back **in place** (`cat ~/Caddyfile.bak-... > /opt/caddy/Caddyfile`) and
reload. Do not `cp`/`mv` over the file.

Site address: `codebattles.online` (and `www.` redirecting to it). Caddy gets the certificate itself.
Moving an already appended IP block to the domain: replace the old `http://<ip> {` block in
`/opt/caddy/Caddyfile` with the content of `deploy/code_battles.caddy` (in place, see above), set
`HTTPS=1`, `ALLOWED_HOSTS=codebattles.online`, `CSRF_TRUSTED_ORIGINS=https://codebattles.online`
in `.env`, reload Caddy, then `make deploy`.
The access log is `/data/code_battles_access.log` inside the caddy container, with the `token` query
parameter removed (the WebSocket token travels there).

## Next deploys

`make deploy`. `deploy/deploy.sh` does: preflight (`.env` present, no `change-me`, secrets of 32+
characters and all different, 5+ GB free) -> `TAG` = date-time -> build -> `pg_dump` to `backups/`
(`scripts/backup.sh`) -> `migrate` -> `up -d --wait` -> smoke `/health`, `/ready`, runner `/ready` ->
write `.last_good_tag`. A failure after the build rolls back to the previous tag by itself.

## Rollback

```
make rollback                     # from the laptop, to .last_good_tag
make rollback tag=20261029-101500 # to a given tag (docker images 'code-battles-*' lists them)
bash deploy/rollback.sh [TAG]     # the same, on the server
```

Only containers go back. Migrations are not undone: if the new version changed the schema and the old
code cannot read it, restore the dump taken just before the deploy:
`make restore file=backups/daily/code_battles-<time>.dump` (on the server), then roll back.
Old images stay on the server; clean them with `docker image prune` once you are sure.
