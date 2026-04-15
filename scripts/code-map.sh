#!/bin/bash
# Generates a compact, token-efficient code map of the current working directory.
# Output: ~/.claude/memory/code-maps/<cwd-slug>.md
# Called by SessionStart hook. Only regenerates if older than 1 hour or repo changed.

set -e

CWD="$(pwd)"
SLUG="$(echo "$CWD" | sed 's|[/\\:]|_|g' | sed 's|^_||')"
MAP_DIR="$HOME/.claude/memory/code-maps"
MAP_FILE="$MAP_DIR/${SLUG}.md"

mkdir -p "$MAP_DIR"

# Skip if not a code directory
if [ ! -d "$CWD" ] || [ "$CWD" = "$HOME" ]; then
  exit 0
fi

# Skip if not in a git repo AND not in a known project dir
if [ ! -d "$CWD/.git" ] && [ ! -f "$CWD/package.json" ] && [ ! -f "$CWD/Cargo.toml" ] && [ ! -f "$CWD/pyproject.toml" ] && [ ! -f "$CWD/go.mod" ]; then
  exit 0
fi

# Freshness check — regenerate if older than 1 hour
if [ -f "$MAP_FILE" ]; then
  AGE=$(( $(date +%s) - $(stat -c %Y "$MAP_FILE" 2>/dev/null || echo 0) ))
  if [ "$AGE" -lt 3600 ]; then
    exit 0
  fi
fi

# Build the map
{
  echo "# Code Map — $(basename "$CWD")"
  echo ""
  echo "> Generated: $(date '+%F %T')"
  echo "> Path: \`$CWD\`"
  echo ""

  # Git state
  if [ -d "$CWD/.git" ]; then
    echo "## Git State"
    echo '```'
    cd "$CWD"
    git log -1 --oneline 2>/dev/null && echo "Branch: $(git branch --show-current 2>/dev/null)"
    echo "Uncommitted: $(git status --porcelain 2>/dev/null | wc -l) files"
    echo '```'
    echo ""
  fi

  # Manifest / config
  echo "## Project Manifest"
  for f in package.json Cargo.toml pyproject.toml go.mod requirements.txt README.md CLAUDE.md; do
    if [ -f "$CWD/$f" ]; then
      echo "- \`$f\` ($(wc -l < "$CWD/$f" 2>/dev/null || echo '?') lines)"
    fi
  done
  echo ""

  # Directory tree (depth 2, excluding noise)
  echo "## Directory Tree (depth 2)"
  echo '```'
  cd "$CWD"
  find . -maxdepth 2 -type d \
    ! -path '*/node_modules*' \
    ! -path '*/.git*' \
    ! -path '*/.next*' \
    ! -path '*/dist*' \
    ! -path '*/build*' \
    ! -path '*/__pycache__*' \
    ! -path '*/target*' \
    ! -path '*/.venv*' \
    2>/dev/null | head -40 | sort
  echo '```'
  echo ""

  # Key source files (top 20 by size, sensible extensions)
  echo "## Key Source Files"
  echo '```'
  find . -type f \
    \( -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" \
       -o -name "*.py" -o -name "*.rs" -o -name "*.go" -o -name "*.md" \) \
    ! -path '*/node_modules/*' \
    ! -path '*/.git/*' \
    ! -path '*/dist/*' \
    ! -path '*/build/*' \
    ! -path '*/__pycache__/*' \
    2>/dev/null | head -30 | while read -r f; do
      size=$(wc -l < "$f" 2>/dev/null || echo 0)
      printf "%5d  %s\n" "$size" "$f"
    done | sort -rn | head -20
  echo '```'
  echo ""

  # File count summary
  echo "## Stats"
  echo '```'
  echo "Total tracked files: $(git ls-files 2>/dev/null | wc -l)"
  echo "Total lines of code: $(find . -type f \( -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.py' -o -name '*.rs' -o -name '*.go' \) ! -path '*/node_modules/*' ! -path '*/.git/*' -exec cat {} + 2>/dev/null | wc -l)"
  echo '```'
} > "$MAP_FILE"

exit 0
