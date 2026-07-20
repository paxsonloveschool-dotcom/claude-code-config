#!/usr/bin/env bash
# Removes the HP launchd timers and the scheduled wake.  Run:  bash uninstall.sh
set -euo pipefail
AGENTS="$HOME/Library/LaunchAgents"
for label in com.hp.ig.autopost com.hp.tiktok.autopost; do
  launchctl unload "$AGENTS/$label.plist" 2>/dev/null || true
  rm -f "$AGENTS/$label.plist"
  echo "removed $label"
done
sudo pmset repeat cancel || echo "! could not cancel wake schedule (run: sudo pmset repeat cancel)"
echo "DONE ✅  Timers + scheduled wake removed."
