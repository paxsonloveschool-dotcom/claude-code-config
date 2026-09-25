#!/bin/bash
# Claude Code config auto-sync
# Pulls latest claude-code-config from GitHub and syncs files + helper scripts to ~/.claude/
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

# Sync all files in a directory (non-recursive)
sync_dir() {
  local src_dir="$1"
  local dst_dir="$2"
  if [ -d "$src_dir" ]; then
    mkdir -p "$dst_dir"
    for src in "$src_dir"/*; do
      [ -f "$src" ] || continue
      sync_file "$src" "$dst_dir/$(basename "$src")"
    done
  fi
}

# Config docs
sync_file "$REPO/CLAUDE.md"                    "$HOME/.claude/CLAUDE.md"
sync_file "$REPO/SESSION_HANDOFF.md"           "$HOME/.claude/SESSION_HANDOFF.md"
sync_file "$REPO/.claude/COMMON_MISTAKES.md"   "$HOME/.claude/COMMON_MISTAKES.md"
sync_file "$REPO/.claude/QUICK_START.md"       "$HOME/.claude/QUICK_START.md"
sync_file "$REPO/.claude/ARCHITECTURE_MAP.md"  "$HOME/.claude/ARCHITECTURE_MAP.md"

# Helper scripts
sync_file "$REPO/scripts/sync-config.sh"       "$HOME/.claude/sync-config.sh"
sync_file "$REPO/scripts/wsl-check.sh"         "$HOME/.claude/wsl-check.sh"
sync_file "$REPO/scripts/code-map.sh"          "$HOME/.claude/code-map.sh"
sync_file "$REPO/scripts/daily-log.sh"         "$HOME/.claude/daily-log.sh"

# JARVIS skills (each in its own directory with SKILL.md)
sync_dir "$REPO/skills/jarvis-constitution"  "$HOME/.claude/skills/jarvis-constitution"
sync_dir "$REPO/skills/jarvis-task-manager"  "$HOME/.claude/skills/jarvis-task-manager"
sync_dir "$REPO/skills/jarvis-agent-roster"  "$HOME/.claude/skills/jarvis-agent-roster"

# Ensure scripts are executable
chmod +x "$HOME/.claude/sync-config.sh" "$HOME/.claude/wsl-check.sh" \
         "$HOME/.claude/code-map.sh" "$HOME/.claude/daily-log.sh" 2>/dev/null

exit 0
