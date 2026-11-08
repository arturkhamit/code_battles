#!/usr/bin/env bash
# pg_dump -Fc of the running postgres service into backups/. Keeps 7 daily and 4 weekly dumps.
# Run from anywhere (cron, make backup, deploy.sh). On the server it follows .last_good_tag.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [ -z "${TAG:-}" ] && [ -f .last_good_tag ]; then
    TAG=$(<.last_good_tag)
    export TAG
    export COMPOSE_FILE="${COMPOSE_FILE:-compose.yaml:deploy/compose.prod.yaml}"
fi

mkdir -p backups/daily backups/weekly
out="backups/daily/code_battles-$(date +%Y%m%d-%H%M%S).dump"

# -T: no tty (cron). The dump goes to a .part file, so a failed run never leaves a "good" name.
docker compose exec -T postgres sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$out.part"
# a dump that pg_restore cannot list is useless: fail loudly now, not at restore time
docker compose exec -T postgres pg_restore -l < "$out.part" > /dev/null
mv "$out.part" "$out"

# one weekly copy per 7 days
if [ -z "$(find backups/weekly -name '*.dump' -mtime -6 -print -quit)" ]; then
    cp "$out" backups/weekly/
fi

# rotation: newest 7 daily and 4 weekly stay
for spec in "daily 7" "weekly 4"; do
    read -r kind keep <<< "$spec"
    find "backups/$kind" -name '*.dump' -printf '%T@ %p\n' | sort -rn | tail -n +$((keep + 1)) | cut -d' ' -f2- | xargs -r rm -f --
done

echo "backup ok: $out ($(du -h "$out" | cut -f1))"
