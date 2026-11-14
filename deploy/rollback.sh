#!/usr/bin/env bash
# Return to the images that ran before the last deploy/deploy.sh (Task 34).
#
#   bash /opt/seehere/deploy/rollback.sh
#
# Migrations are additive in this project, so the previous code runs on the newer schema.
# If a release ever drops or renames columns, restore the database backup taken before it
# (deploy/backup-db.sh) as well.
set -euo pipefail
cd "$(dirname "$0")"

for image in seehere-backend seehere-web; do
  docker image inspect "${image}:previous" >/dev/null 2>&1 || {
    echo "No ${image}:previous image; nothing to roll back to." >&2
    exit 1
  }
done
SEEHERE_VERSION=previous docker compose -f docker-compose.prod.yml up -d --no-build api worker web
docker compose -f docker-compose.prod.yml ps
