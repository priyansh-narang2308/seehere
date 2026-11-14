#!/usr/bin/env bash
# Dump the SeeHere database to deploy/backups/ (Task 34). Keeps the 7 newest dumps.
#
#   bash /opt/seehere/deploy/backup-db.sh
#   restore: gunzip -c backups/<file>.sql.gz | docker compose -f docker-compose.prod.yml exec -T db psql -U seehere seehere
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p backups
chmod 700 backups
file="backups/seehere-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U seehere seehere | gzip > "$file"
ls -1t backups/*.sql.gz | tail -n +8 | xargs -r rm --
echo "$file"
