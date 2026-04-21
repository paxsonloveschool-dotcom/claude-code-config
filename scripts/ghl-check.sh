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

# Probe GHL REST API with PIT token
echo "→ Probing GHL REST API (locations/$GHL_LOCATION_ID)..."
code=$(curl -s -o /tmp/ghl-probe.json -w "%{http_code}" \
  -H "Authorization: Bearer $GHL_API_KEY" \
  -H "Version: 2021-07-28" \
  "https://services.leadconnectorhq.com/locations/$GHL_LOCATION_ID")

if [ "$code" = "200" ]; then
  echo "✓ GHL REST API reachable, token valid for location"
else
  echo "✗ GHL REST API returned HTTP $code"
  cat /tmp/ghl-probe.json 2>/dev/null | head -c 400 || true
  echo
  exit 1
fi

# Probe GHL MCP endpoint (Streamable HTTP transport)
echo "→ Probing GHL MCP endpoint..."
mcp_code=$(curl -s -o /tmp/ghl-mcp-probe.json -w "%{http_code}" \
  -X POST \
  -H "Authorization: Bearer $GHL_API_KEY" \
  -H "locationId: $GHL_LOCATION_ID" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"ghl-check","version":"1.0"}}}' \
  "https://services.leadconnectorhq.com/mcp/")

case "$mcp_code" in
  200|202)
    echo "✓ GHL MCP endpoint reachable (HTTP $mcp_code)"
    ;;
  *)
    echo "✗ GHL MCP endpoint returned HTTP $mcp_code"
    cat /tmp/ghl-mcp-probe.json 2>/dev/null | head -c 400 || true
    echo
    exit 1
    ;;
esac
