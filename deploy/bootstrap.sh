#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 24.04 Vultr Cloud Compute instance for SeeHere (Task 34).
# Run as root (cloud-init runs it for you):
#
#   curl -fsSL https://raw.githubusercontent.com/priyansh-narang2308/seehere/main/deploy/bootstrap.sh | bash
#   or, with the code already copied to /opt/seehere:  bash /opt/seehere/deploy/bootstrap.sh
#
# It installs Docker from Docker's own apt repository, opens only SSH/HTTP/HTTPS in the firewall,
# adds swap, writes deploy/.env (domain from the server's public IP via sslip.io, random database
# password) and starts the stack. Re-running it is safe: existing settings are kept.
set -euo pipefail

REPO_URL="${SEEHERE_REPO:-https://github.com/priyansh-narang2308/seehere.git}"
APP_DIR="${SEEHERE_DIR:-/opt/seehere}"

log() { printf '\n== %s\n' "$*"; }

log "Packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q ca-certificates curl git ufw openssl

if ! command -v docker >/dev/null; then
  log "Docker (official apt repository)"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -q
  apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
fi

log "Firewall: SSH, HTTP, HTTPS only"
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

if ! swapon --show | grep -q /swapfile; then
  log "Swap (4 GB) as a safety margin for speech-to-text"
  fallocate -l 4G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

if [ ! -d "$APP_DIR/.git" ] && [ ! -f "$APP_DIR/deploy/docker-compose.prod.yml" ]; then
  log "Code"
  git clone --depth 50 "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR/deploy"

if [ ! -f .env ]; then
  log "Settings (deploy/.env)"
  ip="$(curl -fsS --max-time 5 http://169.254.169.254/v1/interfaces/0/ipv4/address 2>/dev/null || true)"
  [ -n "$ip" ] || ip="$(curl -fsS --max-time 5 https://api.ipify.org)"
  domain="${SEEHERE_DOMAIN:-${ip//./-}.sslip.io}"
  cp .env.prod.example .env
  sed -i "s|^SEEHERE_DOMAIN=.*|SEEHERE_DOMAIN=${domain}|" .env
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(openssl rand -hex 24)|" .env
  chmod 600 .env
fi

log "Build and start"
docker compose -f docker-compose.prod.yml up -d --build

domain="$(grep '^SEEHERE_DOMAIN=' .env | cut -d= -f2)"
log "Waiting for https://${domain}"
for _ in $(seq 1 60); do
  if curl -fsS --max-time 5 "https://${domain}/api/health/live" >/dev/null 2>&1; then
    echo "SeeHere is live at https://${domain}"
    exit 0
  fi
  sleep 5
done
echo "Not reachable yet. Check: docker compose -f docker-compose.prod.yml ps && docker compose -f docker-compose.prod.yml logs --tail 50"
exit 1
