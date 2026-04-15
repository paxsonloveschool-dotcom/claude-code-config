#!/bin/bash
# Claude Code God Mode Bootstrap
# Sets up the full token-efficiency + Superpowers stack on any new device.
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/paxsonloveschool-dotcom/claude-code-config/main/bootstrap.sh | bash
# OR
#   git clone https://github.com/paxsonloveschool-dotcom/claude-code-config ~/projects/claude-code-config
#   bash ~/projects/claude-code-config/bootstrap.sh

set -e

REPO="$HOME/projects/claude-code-config"
REPO_URL="https://github.com/paxsonloveschool-dotcom/claude-code-config.git"
CLAUDE_DIR="$HOME/.claude"

echo ""
echo "╔════════════════════════════════════════════════════╗"
echo "║   Claude Code God Mode Bootstrap                   ║"
echo "║   Full token-efficiency + Superpowers stack        ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""

# --- Prerequisite checks ---
echo "[1/7] Checking prerequisites..."
command -v git >/dev/null 2>&1 || { echo "ERROR: git not installed"; exit 1; }
command -v claude >/dev/null 2>&1 || {
  # Try adding npm global bin to PATH
  if [ -d "$HOME/AppData/Roaming/npm" ]; then
    export PATH="$PATH:$HOME/AppData/Roaming/npm"
  fi
  command -v claude >/dev/null 2>&1 || {
    echo "ERROR: claude CLI not installed. Run: npm install -g @anthropic-ai/claude-code"
    exit 1
  }
}
echo "  ✔ git, claude CLI available"

# --- Clone or update repo ---
echo "[2/7] Cloning/updating canonical config repo..."
if [ -d "$REPO/.git" ]; then
  cd "$REPO"
  git pull --quiet --rebase origin main
  echo "  ✔ pulled latest from $REPO"
else
  mkdir -p "$HOME/projects"
  git clone "$REPO_URL" "$REPO"
  echo "  ✔ cloned to $REPO"
fi

# --- Sync files to ~/.claude/ ---
echo "[3/7] Syncing config files to $CLAUDE_DIR..."
mkdir -p "$CLAUDE_DIR"
cp "$REPO/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md"
cp "$REPO/SESSION_HANDOFF.md" "$CLAUDE_DIR/SESSION_HANDOFF.md"
cp "$REPO/.claude/COMMON_MISTAKES.md" "$CLAUDE_DIR/COMMON_MISTAKES.md"
cp "$REPO/.claude/QUICK_START.md" "$CLAUDE_DIR/QUICK_START.md"
cp "$REPO/.claude/ARCHITECTURE_MAP.md" "$CLAUDE_DIR/ARCHITECTURE_MAP.md"
echo "  ✔ 5 config files synced"

# --- Install sync scripts ---
echo "[4/7] Installing sync scripts..."
cp "$REPO/scripts/sync-config.sh" "$CLAUDE_DIR/sync-config.sh" 2>/dev/null || {
  # Inline fallback if scripts/ doesn't exist in repo yet
  cat > "$CLAUDE_DIR/sync-config.sh" << 'SYNC_EOF'
#!/bin/bash
REPO="$HOME/projects/claude-code-config"
LOG="$HOME/.claude/sync.log"
[ -d "$REPO/.git" ] || { echo "[$(date '+%F %T')] sync skipped: repo not cloned" >> "$LOG"; exit 0; }
cd "$REPO" || exit 0
git pull --quiet --rebase origin main 2>> "$LOG" || true
sync_file() {
  local src="$1" dst="$2"
  [ -f "$src" ] || return
  if [ ! -f "$dst" ] || ! cmp -s "$src" "$dst"; then
    cp "$src" "$dst"
    echo "[$(date '+%F %T')] synced: $(basename "$src")" >> "$LOG"
  fi
}
sync_file "$REPO/CLAUDE.md"                    "$HOME/.claude/CLAUDE.md"
sync_file "$REPO/SESSION_HANDOFF.md"           "$HOME/.claude/SESSION_HANDOFF.md"
sync_file "$REPO/.claude/COMMON_MISTAKES.md"   "$HOME/.claude/COMMON_MISTAKES.md"
sync_file "$REPO/.claude/QUICK_START.md"       "$HOME/.claude/QUICK_START.md"
sync_file "$REPO/.claude/ARCHITECTURE_MAP.md"  "$HOME/.claude/ARCHITECTURE_MAP.md"
exit 0
SYNC_EOF
}
chmod +x "$CLAUDE_DIR/sync-config.sh"
echo "  ✔ sync-config.sh installed and executable"

# --- Install Superpowers plugins ---
echo "[5/7] Installing Superpowers plugin stack..."
if ! claude plugin marketplace list 2>/dev/null | grep -q "superpowers-marketplace"; then
  claude plugin marketplace add obra/superpowers-marketplace 2>&1 | tail -1
fi
for plugin in superpowers episodic-memory elements-of-style; do
  if ! claude plugin list 2>/dev/null | grep -q "$plugin@superpowers-marketplace"; then
    claude plugin install "$plugin@superpowers-marketplace" 2>&1 | tail -1
  else
    echo "  ✔ $plugin already installed"
  fi
done

# --- RTK binary (optional, Windows-friendly) ---
echo "[6/7] Checking RTK..."
if [ ! -f "$HOME/.local/bin/rtk.exe" ] && [ ! -f "$HOME/.local/bin/rtk" ]; then
  echo "  ℹ RTK not installed on this device. Install manually:"
  echo "    Windows: https://github.com/rtk-ai/rtk/releases"
  echo "    macOS:   brew install rtk"
  echo "    Linux:   curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh"
else
  echo "  ✔ RTK binary found at ~/.local/bin/"
fi

# --- Final report ---
echo "[7/7] Bootstrap complete!"
echo ""
echo "╔════════════════════════════════════════════════════╗"
echo "║   Still needs physical action (one-time setup):    ║"
echo "╠════════════════════════════════════════════════════╣"
echo "║ 1. Install WSL (Windows only, for RTK hook mode):  ║"
echo "║    Open PowerShell as Admin, run: wsl --install    ║"
echo "║                                                    ║"
echo "║ 2. Install Claude GitHub App:                      ║"
echo "║    https://github.com/apps/claude                  ║"
echo "║                                                    ║"
echo "║ 3. Add ANTHROPIC_API_KEY to your repo secrets:     ║"
echo "║    https://github.com/paxsonloveschool-dotcom/     ║"
echo "║    claude-code-config/settings/secrets/actions     ║"
echo "╚════════════════════════════════════════════════════╝"
echo ""
echo "Start a new Claude Code session to see the god-mode setup in action:"
echo "  claude"
echo ""
