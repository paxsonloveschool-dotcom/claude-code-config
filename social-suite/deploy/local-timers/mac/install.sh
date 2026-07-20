#!/usr/bin/env bash
# Installs the HP local posting timers on macOS (launchd) and schedules the Mac
# to WAKE itself for them, so it can sleep the rest of the time.
#
#   Instagram : Mon/Wed/Fri 11:00  (posts one Reel per run — instant, no scheduler)
#   TikTok    : Mon 10:30 weekly    (uploads the week's batch to TikTok's scheduler)
#   Wake      : Mon/Wed/Fri 10:25   (pmset wakes the Mac ~5 min before the runs)
#
# Run:  bash install.sh
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -f "$DIR/../config.env" ]]; then
  echo "ERROR: config.env not found. Copy and edit it first:"
  echo "   cp \"$DIR/../config.example.env\" \"$DIR/../config.env\""
  exit 1
fi
# shellcheck source=/dev/null
source "$DIR/../config.env"

# --- sanity checks -----------------------------------------------------------
[[ -d "$SOCIAL_SUITE_DIR" ]] || { echo "ERROR: SOCIAL_SUITE_DIR not found: $SOCIAL_SUITE_DIR"; exit 1; }
[[ -f "$SOCIAL_SUITE_DIR/automation/ig_autopost.py" ]] || { echo "ERROR: social-suite path looks wrong (no automation/ig_autopost.py)."; exit 1; }
command -v "$PYTHON" >/dev/null 2>&1 || { echo "ERROR: python not found: $PYTHON"; exit 1; }

chmod +x "$DIR/run-ig.sh" "$DIR/run-tiktok.sh"
LOGDIR="$DIR/../logs"; mkdir -p "$LOGDIR"
AGENTS="$HOME/Library/LaunchAgents"; mkdir -p "$AGENTS"

write_plist() {  # label  script  logbase  <calendar-dicts>
  local label="$1" script="$2" logbase="$3" cal="$4"
  cat > "$AGENTS/$label.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$script</string>
  </array>
  <key>StartCalendarInterval</key>
  <array>
$cal
  </array>
  <key>StandardOutPath</key><string>$logbase.log</string>
  <key>StandardErrorPath</key><string>$logbase.err</string>
</dict>
</plist>
PLIST
  launchctl unload "$AGENTS/$label.plist" 2>/dev/null || true
  launchctl load "$AGENTS/$label.plist"
  echo "  loaded $label"
}

# Instagram — Mon(1)/Wed(3)/Fri(5) at 11:00
IG_CAL="    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>11</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>3</integer><key>Hour</key><integer>11</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Weekday</key><integer>5</integer><key>Hour</key><integer>11</integer><key>Minute</key><integer>0</integer></dict>"

# TikTok — Mon(1) at 10:30 (weekly batch upload to TikTok's own scheduler)
TT_CAL="    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>10</integer><key>Minute</key><integer>30</integer></dict>"

echo "Installing launchd timers..."
write_plist "com.hp.ig.autopost"     "$DIR/run-ig.sh"     "$LOGDIR/ig_autopost"     "$IG_CAL"
write_plist "com.hp.tiktok.autopost" "$DIR/run-tiktok.sh" "$LOGDIR/tiktok_autopost" "$TT_CAL"

echo ""
echo "Scheduling the Mac to WAKE for these runs (needs your password)..."
echo "  (wakes Mon/Wed/Fri at 10:25 so TikTok 10:30 + Instagram 11:00 both fire)"
sudo pmset repeat wakeorpoweron MWF 10:25:00 || {
  echo "  ! pmset failed — set it manually: sudo pmset repeat wakeorpoweron MWF 10:25:00"; }

echo ""
echo "DONE ✅  Timers installed. The Mac must be plugged in and ASLEEP (not shut"
echo "down) at those times — it will wake itself, post, and sleep again."
echo "Check wake schedule:  pmset -g sched"
echo "Logs:                 $LOGDIR/"
