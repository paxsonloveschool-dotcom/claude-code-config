#!/usr/bin/env bash
# Posts ONE new HP clip to Instagram as a Reel with the next chosen song.
# Called by the launchd timer (Mon/Wed/Fri 11:00). Logs to ig_autopost.log.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$DIR/../config.env"

export IG_FOLDER IG_CREDS
cd "$SOCIAL_SUITE_DIR"
exec "$PYTHON" automation/ig_autopost.py
