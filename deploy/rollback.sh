#!/usr/bin/env bash
# Back to a built tag: deploy/rollback.sh [TAG]   (default: the one in .last_good_tag)
# Only the containers go back. Migrations are not undone: if the new version changed the
# schema in a way the old code cannot read, restore a dump too (make restore file=...).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

TAG=${1:-$(cat .last_good_tag 2>/dev/null || true)}
[ -n "$TAG" ] || { echo "no TAG given and no .last_good_tag" >&2; exit 1; }
export TAG
export COMPOSE_FILE=compose.yaml:deploy/compose.prod.yaml

for image in django fastapi runner web; do
    docker image inspect "code-battles-$image:$TAG" > /dev/null \
        || { echo "image code-battles-$image:$TAG does not exist (docker images 'code-battles-*')" >&2; exit 1; }
done

echo "== rolling back to $TAG"
docker compose up -d --wait --no-build --remove-orphans

port=$(grep -E '^CODE_BATTLES_PORT=' .env | tail -n 1 | cut -d= -f2- || true)
port=${port:-8010}
for path in /health /ready; do
    curl -fsS --retry 10 --retry-delay 3 --retry-connrefused "http://127.0.0.1:$port$path" > /dev/null
    echo "smoke $path ok"
done
echo "== rollback ok: $TAG"
