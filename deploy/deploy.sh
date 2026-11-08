#!/usr/bin/env bash
# Deploy on the server, from ~/arthur/code_battles:   deploy/deploy.sh
# preflight -> TAG=date-time -> build -> backup -> migrate -> up --wait -> smoke -> .last_good_tag
# A failure after the stack was touched rolls back to the previous .last_good_tag.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

export COMPOSE_FILE=compose.yaml:deploy/compose.prod.yaml
stage=preflight
previous=$(cat .last_good_tag 2>/dev/null || true)

env_value() { grep -E "^$1=" .env | tail -n 1 | cut -d= -f2- || true; }

on_error() {
    echo "DEPLOY FAILED at stage: $stage" >&2
    case "$stage" in
        preflight | build)
            echo "Nothing was changed on the running stack." >&2 ;;
        *)
            if [ -n "$previous" ]; then
                echo "Rolling back to $previous" >&2
                deploy/rollback.sh "$previous" >&2 || echo "ROLLBACK FAILED, fix by hand (docker compose logs)" >&2
                echo "If the migration had already changed the schema, restore the dump: make restore file=<backups/daily/...>" >&2
            else
                echo "First deploy: nothing to roll back to. See: docker compose logs" >&2
            fi ;;
    esac
    exit 1
}
trap on_error ERR

# ---- 1. preflight ---------------------------------------------------------------------------
[ -f .env ] || { echo ".env is missing (cp .env.example .env and fill it)" >&2; exit 1; }
if grep -q 'change-me' .env; then
    echo ".env still has change-me values:" >&2
    grep -n 'change-me' .env | cut -d= -f1 >&2
    exit 1
fi
secrets=(DJANGO_SECRET_KEY JWT_SIGNING_KEY INTERNAL_API_TOKEN RUNNER_TOKEN)
declare -A seen=()
for name in "${secrets[@]}"; do
    value=$(env_value "$name")
    [ "${#value}" -ge 32 ] || { echo "$name is missing or shorter than 32 characters" >&2; exit 1; }
    [ -z "${seen[$value]:-}" ] || { echo "$name equals ${seen[$value]}: the secrets must differ" >&2; exit 1; }
    seen[$value]=$name
done
for name in POSTGRES_PASSWORD REDIS_PASSWORD; do
    [ -n "$(env_value "$name")" ] || { echo "$name is empty" >&2; exit 1; }
done
free_gb=$(df --output=avail -BG . | tail -n 1 | tr -dc '0-9')
[ "$free_gb" -ge 5 ] || { echo "Only ${free_gb} GB free, need 5+" >&2; exit 1; }
[ -f backend/tests/tests.json ] || echo "note: backend/tests/tests.json is missing, tasks cannot be imported (make import-tasks)"
port=$(env_value CODE_BATTLES_PORT)
port=${port:-8010}

# ---- 2. tag ---------------------------------------------------------------------------------
TAG=$(date +%Y%m%d-%H%M%S)
export TAG
echo "== deploying TAG=$TAG (previous: ${previous:-none})"

# ---- 3. build: app images and the sandbox images (the runner never pulls) --------------------
stage=build
docker compose --profile build-only build

# ---- 4. backup before the schema changes ------------------------------------------------------
stage=backup
if [ -n "$previous" ]; then
    scripts/backup.sh
else
    echo "first deploy: no database yet, backup skipped"
fi

# ---- 5. migrate -------------------------------------------------------------------------------
stage=migrate
docker compose up -d --wait postgres redis
docker compose run --rm --no-deps migrate

# ---- 6. start ---------------------------------------------------------------------------------
stage=up
docker compose up -d --wait --remove-orphans

# ---- 7. smoke through the published port --------------------------------------------------------
stage=smoke
for path in /health /ready; do
    curl -fsS --retry 10 --retry-delay 3 --retry-connrefused "http://127.0.0.1:$port$path" > /dev/null
    echo "smoke $path ok"
done
docker compose exec -T runner python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/ready', timeout=5)"
echo "smoke runner /ready ok"

# ---- 8. done ----------------------------------------------------------------------------------
echo "$TAG" > .last_good_tag
echo "== deploy ok: $TAG"
