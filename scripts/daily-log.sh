#!/bin/bash
# Ensures today's daily log file exists in ~/.claude/memory/daily/
# Appends a session-start timestamp to it.
# Called by SessionStart hook.

set -e

TODAY=$(date '+%Y-%m-%d')
TIME=$(date '+%H:%M %Z')
DAILY_DIR="$HOME/.claude/memory/daily"
DAILY_FILE="$DAILY_DIR/${TODAY}.md"

mkdir -p "$DAILY_DIR"

# Create today's file if missing
if [ ! -f "$DAILY_FILE" ]; then
  cat > "$DAILY_FILE" << EOF
# Daily Log — $TODAY

> Auto-created by SessionStart hook. Append timestamped entries as work happens.
> One entry per meaningful decision or milestone.

## Sessions

EOF
fi

# Append session start marker (only if we haven't logged one in the last 10 minutes)
LAST_ENTRY=$(tail -20 "$DAILY_FILE" 2>/dev/null | grep -c "session start" || echo 0)
LAST_TIME_LINE=$(grep "session start" "$DAILY_FILE" 2>/dev/null | tail -1)

# Append new session start line
echo "- **$TIME** — session start" >> "$DAILY_FILE"

exit 0
