#!/usr/bin/env bash
# Verify GHL MCP server is reachable and credentials are loaded.
set -euo pipefail

cd "$(dirname "$0")/.."

# Load .env if present
if [ -f .env ]; then
  set -a; . ./.env; set +a
fi

missing=0
if [ -z "${GHL_API_KEY:-}" ]; then
  echo "✗ GHL_API_KEY not set (check .env)"
  missing=1
else
  echo "✓ GHL_API_KEY loaded (${#GHL_API_KEY} chars)"
fi

if [ -z "${GHL_LOCATION_ID:-}" ]; then
  echo "✗ GHL_LOCATION_ID not set"
  missing=1
else
  echo "✓ GHL_LOCATION_ID = $GHL_LOCATION_ID"
fi

[ $missing -eq 1 ] && exit 1

# Probe the MCP package is installable
echo "→ Probing @highlevel/mcp-server via npx..."
if npx -y -p @highlevel/mcp-server --version >/dev/null 2>&1; then
  echo "✓ @highlevel/mcp-server available"
else
  echo "⚠  npx probe failed — package may need first-time install on next MCP start"
fi

# Probe GHL API directly with PIT token
echo "→ Probing GHL API (locations/$GHL_LOCATION_ID)..."
code=$(curl -s -o /tmp/ghl-probe.json -w "%{http_code}" \
  -H "Authorization: Bearer $GHL_API_KEY" \
  -H "Version: 2021-07-28" \
  "https://services.leadconnectorhq.com/locations/$GHL_LOCATION_ID")

if [ "$code" = "200" ]; then
  echo "✓ GHL API reachable, token valid for location"
else
  echo "✗ GHL API returned HTTP $code"
  cat /tmp/ghl-probe.json 2>/dev/null | head -c 400 || true
  echo
  exit 1
fi
