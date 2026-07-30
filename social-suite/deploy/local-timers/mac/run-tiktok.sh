#!/usr/bin/env bash
# Uploads the week's approved HP clips to TikTok's scheduler (song + Mon/Wed/Fri
# slots, up to 10 days out). Called by the weekly launchd timer, OR run by hand.
# The first ever run opens a browser to log in once (saves Tk_cookies_hp.json).
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$DIR/../config.env"

cd "$SOCIAL_SUITE_DIR"
exec "$PYTHON" automation/tiktok_browser_post.py --brand hp
