#!/bin/bash
# Make --dangerously-skip-permissions permanent in user settings.
# Merges permissions.defaultMode=bypassPermissions and
# skipDangerousModePermissionPrompt=true into ~/.claude/settings.json,
# preserving every other key. Idempotent.
# Usage: ensure-bypass-permissions.sh [target-settings.json]

TARGET="${1:-$HOME/.claude/settings.json}"
mkdir -p "$(dirname "$TARGET")"
[ -f "$TARGET" ] || echo '{}' > "$TARGET"

if command -v jq >/dev/null 2>&1; then
  tmp="$TARGET.tmp.$$"
  jq '.skipDangerousModePermissionPrompt = true
      | .permissions = ((.permissions // {}) + {defaultMode: "bypassPermissions"})' \
     "$TARGET" > "$tmp" && mv "$tmp" "$TARGET" || { rm -f "$tmp"; exit 1; }
elif command -v python3 >/dev/null 2>&1; then
  python3 - "$TARGET" <<'PY' || exit 1
import json, sys
p = sys.argv[1]
with open(p) as f:
    s = json.load(f)
s["skipDangerousModePermissionPrompt"] = True
s.setdefault("permissions", {})["defaultMode"] = "bypassPermissions"
with open(p, "w") as f:
    json.dump(s, f, indent=2)
    f.write("\n")
PY
else
  echo "ensure-bypass-permissions: need jq or python3; set permissions.defaultMode manually in $TARGET" >&2
  exit 1
fi

exit 0
