#!/bin/zsh
# HP multi-company auto-poster — launchd runs this Mon/Wed/Fri at 11:00am.
# Posts each company's next clip (from its own Dropbox folder) to that company's
# Facebook / Instagram / TikTok / X / YouTube accounts. See automation/post_multi.py.

# Homebrew paths first so `node` (TikTok) and `ffmpeg` (uniquify) are found.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# Space consecutive Instagram posts apart (anti-spam / anti-ban).
export IG_STAGGER_SEC="${IG_STAGGER_SEC:-150}"

LOG="$HOME/hp-auto/autopost.log"
mkdir -p "$HOME/hp-auto"
echo "=== run $(date '+%Y-%m-%d %H:%M:%S') ===" >> "$LOG"

cd "$HOME/claude-code-config/social-suite" || { echo "no social-suite dir" >> "$LOG"; exit 1; }
exec "$HOME/hp-venv/bin/python" automation/post_multi.py >> "$LOG" 2>&1
