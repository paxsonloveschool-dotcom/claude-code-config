#!/usr/bin/env bash
#
# Postiz one-shot bootstrap for a fresh Ubuntu server (built for Oracle
# Cloud "Always Free", works on any Ubuntu 22.04/24.04 VPS).
#
# It will:
#   1. Install Docker (if missing)
#   2. Open the OS firewall on 80/443  <-- the #1 Oracle gotcha
#   3. Set up your free DuckDNS subdomain + auto-IP-updater
#   4. Generate secrets and write .env
#   5. Launch Postiz
#
# Run it from inside the postiz/ folder:
#   chmod +x setup.sh && ./setup.sh
#
set -euo pipefail

cd "$(dirname "$0")"
say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ask() { local p="$1" d="${2:-}" v; read -rp "$p${d:+ [$d]}: " v; echo "${v:-$d}"; }

# --- 0. sudo check ---------------------------------------------------------
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"

# --- 1. Docker -------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  say "Installing Docker..."
  curl -fsSL https://get.docker.com | $SUDO sh
else
  say "Docker already installed: $(docker --version)"
fi

# --- 2. Firewall (Oracle ships iptables defaulting to REJECT) --------------
say "Opening ports 80 and 443 in the OS firewall..."
if command -v iptables >/dev/null 2>&1; then
  for port in 80 443; do
    if ! $SUDO iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null; then
      $SUDO iptables -I INPUT 1 -m state --state NEW -p tcp --dport "$port" -j ACCEPT
    fi
  done
  # Persist across reboots if the tooling is present
  if command -v netfilter-persistent >/dev/null 2>&1; then
    $SUDO netfilter-persistent save || true
  else
    $SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent >/dev/null 2>&1 \
      && $SUDO netfilter-persistent save || \
      echo "  (could not persist iptables — make sure to re-open 80/443 after reboot)"
  fi
  echo "  Done. NOTE: you ALSO must add ingress rules for 80/443 in the"
  echo "  Oracle console (VCN > Security List). See ORACLE_FREE_SETUP.md."
fi

# --- 3. DuckDNS ------------------------------------------------------------
say "DuckDNS free domain setup"
echo "  Create a subdomain + grab your token at https://duckdns.org (sign in, free)."
DUCK_SUB=$(ask "  DuckDNS subdomain (just the name, e.g. 'hplandscaping')")
DUCK_TOKEN=$(ask "  DuckDNS token")
DOMAIN="${DUCK_SUB}.duckdns.org"

say "Pointing $DOMAIN at this server + installing auto-updater (every 5 min)..."
UPDATE_CMD="curl -fsS 'https://www.duckdns.org/update?domains=${DUCK_SUB}&token=${DUCK_TOKEN}&ip='"
RESP=$(eval "$UPDATE_CMD" || true)
[ "$RESP" = "OK" ] && echo "  DuckDNS: OK ($DOMAIN -> this server)" \
                   || echo "  DuckDNS returned: '$RESP' (double-check subdomain/token)"
# cron keeps the IP fresh if the server's public IP ever changes
CRON_LINE="*/5 * * * * $UPDATE_CMD >/dev/null 2>&1"
( crontab -l 2>/dev/null | grep -v 'duckdns.org/update' ; echo "$CRON_LINE" ) | crontab -

# --- 4. .env ---------------------------------------------------------------
if [ -f .env ]; then
  say ".env already exists — leaving it untouched."
else
  say "Generating secrets and writing .env..."
  cat > .env <<EOF
DOMAIN=${DOMAIN}
JWT_SECRET=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 16)
DISABLE_REGISTRATION=false
EOF
  # ARM servers need a pinned arm64 image tag
  if [ "$(uname -m)" = "aarch64" ] || [ "$(uname -m)" = "arm64" ]; then
    echo ""; echo "  Detected ARM (aarch64)."
    TAG=$(ask "  Postiz arm64 image tag (find newest '-arm64' tag at github.com/gitroomhq/postiz-app/pkgs/container/postiz-app)" "v2.21.0-arm64")
    echo "POSTIZ_IMAGE=ghcr.io/gitroomhq/postiz-app:${TAG}" >> .env
  fi
  echo "  .env created."
fi

# --- 5. Launch -------------------------------------------------------------
say "Launching Postiz (first boot pulls images + runs migrations, ~2-3 min)..."
$SUDO docker compose up -d

cat <<EOF

==========================================================================
  Postiz is starting.

  Watch progress:   ${SUDO} docker compose logs -f postiz
  Then open:        https://${DOMAIN}

  (HTTPS cert is issued automatically on first visit — give it ~30s.)
  First account you register is the admin. After that, set
  DISABLE_REGISTRATION=true in .env and run: ${SUDO} docker compose up -d
==========================================================================
EOF
