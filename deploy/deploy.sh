#!/usr/bin/env bash
# Update a running SeeHere server to the latest code (Task 34). Run on the server:
#
#   bash /opt/seehere/deploy/deploy.sh            # pull, rebuild, migrate, restart
#
# The images in use are tagged :previous first, so deploy/rollback.sh can return to them.
# Database migrations run before the new API and worker start (the `migrate` service).
set -euo pipefail
cd "$(dirname "$0")"
COMPOSE=(docker compose -f docker-compose.prod.yml)

if [ -d ../.git ]; then
  git -C .. pull --ff-only
fi

for image in seehere-backend seehere-web; do
  if docker image inspect "${image}:latest" >/dev/null 2>&1; then
    docker tag "${image}:latest" "${image}:previous"
  fi
done

"${COMPOSE[@]}" build
"${COMPOSE[@]}" up -d --remove-orphans
"${COMPOSE[@]}" ps

domain="$(grep '^SEEHERE_DOMAIN=' .env | cut -d= -f2)"
for _ in $(seq 1 30); do
  if curl -fsS --max-time 5 "https://${domain}/api/health" >/dev/null 2>&1; then
    echo "Deployed: https://${domain}"
    exit 0
  fi
  sleep 4
done
echo "Health check failed. Inspect logs, or run deploy/rollback.sh" >&2
exit 1
