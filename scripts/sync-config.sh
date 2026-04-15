#!/bin/bash
# Claude Code config auto-sync
# Pulls latest claude-code-config from GitHub and syncs files to ~/.claude/
# Runs silently on SessionStart. Non-destructive: only copies if changed.

REPO="$HOME/projects/claude-code-config"
LOG="$HOME/.claude/sync.log"

if [ ! -d "$REPO/.git" ]; then
  echo "[$(date '+%F %T')] sync skipped: repo not cloned at $REPO" >> "$LOG"
  exit 0
fi

cd "$REPO" || exit 0

# Pull latest (quiet, non-blocking on failure — e.g. offline)
git pull --quiet --rebase origin main 2>> "$LOG" || true

# Sync files only if they differ
sync_file() {
  local src="$1"
  local dst="$2"
  if [ -f "$src" ]; then
    if [ ! -f "$dst" ] || ! cmp -s "$src" "$dst"; then
      cp "$src" "$dst"
      echo "[$(date '+%F %T')] synced: $(basename "$src")" >> "$LOG"
    fi
  fi
}

sync_file "$REPO/CLAUDE.md"                    "$HOME/.claude/CLAUDE.md"
sync_file "$REPO/.claude/COMMON_MISTAKES.md"   "$HOME/.claude/COMMON_MISTAKES.md"
sync_file "$REPO/.claude/QUICK_START.md"       "$HOME/.claude/QUICK_START.md"
sync_file "$REPO/.claude/ARCHITECTURE_MAP.md"  "$HOME/.claude/ARCHITECTURE_MAP.md"

exit 0
