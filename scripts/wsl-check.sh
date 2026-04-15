#!/bin/bash
# Detects if WSL has been installed since last check.
# If so, prints a reminder to run: wsl --install && rtk init -g inside WSL
# for transparent RTK hook mode.

if command -v wsl >/dev/null 2>&1 || [ -x "/c/Windows/System32/wsl.exe" ]; then
  WSL_STATUS=$(cmd //c "wsl --status" 2>/dev/null | head -1)
  if echo "$WSL_STATUS" | grep -qi "default"; then
    FLAG="$HOME/.claude/.rtk-wsl-ready-shown"
    if [ ! -f "$FLAG" ]; then
      echo "🎉 WSL detected! To unlock RTK transparent hook mode (60-90% token savings):"
      echo "   1. Open WSL: wsl"
      echo "   2. Install RTK: curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh"
      echo "   3. Enable hook: rtk init -g"
      echo "   4. Restart Claude Code"
      touch "$FLAG"
    fi
  fi
fi
exit 0
