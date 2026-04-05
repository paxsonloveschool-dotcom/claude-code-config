# Quick Start

## Daily Commands
- `gh auth status` — check GitHub login
- `gh repo create <name> --public --clone` — new repo
- `git add -A && git commit -m "msg" && git push` — ship it

## GitHub Auth (this machine)
```bash
export PATH="/c/Program Files/GitHub CLI:$PATH"
echo "YOUR_TOKEN" | gh auth login --with-token
```

## Claude Code
- Settings: ~/.claude/settings.json (autopilot mode ON)
- Rules: ~/CLAUDE.md (token efficiency ON)
- Mistakes: ~/.claude/COMMON_MISTAKES.md
