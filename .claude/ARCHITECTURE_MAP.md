# Architecture Map

## Config Locations
- `~/.claude/CLAUDE.md` — Global session rules (autopilot, efficiency, hybrid model, verification)
- `~/.claude/settings.json` — Permission auto-approvals + SessionStart/Stop/Notification hooks
- `~/.claude/COMMON_MISTAKES.md` — Known pitfalls
- `~/.claude/QUICK_START.md` — Daily commands
- `~/.claude/ARCHITECTURE_MAP.md` — This file
- `~/.claude/sync-config.sh` — Auto-sync from repo on SessionStart
- `~/.claude/wsl-check.sh` — Detects WSL install and prints RTK hook unlock steps
- `~/projects/claude-code-config/` — Canonical repo (pushed to GitHub, synced to ~/.claude/ on session start)

## Active Integrations
- GitHub CLI (gh) 2.89.0 — authenticated as `paxsonloveschool-dotcom` with `repo` scope
- Git 2.53.0 — configured as `Paxson Berkey <paxsonloveschool@gmail.com>`
- RTK 0.36.0 — binary at `~/.local/bin/rtk.exe` (manual mode on Windows)
- Claude in Chrome MCP — connected
- Google Calendar MCP — connected
- Gmail MCP — connected
- Cloudflare MCP — connected
- Figma MCP — connected
- Google Drive MCP — connected
- Claude Preview MCP — connected

## Auto-Sync Pipeline
Every Claude Code session start runs:
1. `bash ~/.claude/sync-config.sh` — pulls latest from `claude-code-config` repo, copies changed files to `~/.claude/`
2. `bash ~/.claude/wsl-check.sh` — detects WSL install (one-time reminder for RTK hook mode)
3. Session start banner + this architecture map

## Pending Setup (user physical actions required)
- **WSL install** — run `wsl --install` in PowerShell as Admin, reboot, set Linux user/pwd. Unlocks RTK transparent hook mode (60-90% token savings on Bash calls).
- **Claude GitHub App** — install from https://github.com/apps/claude, authorize for `claude-code-config` repo
- **ANTHROPIC_API_KEY secret** — add to `claude-code-config` repo secrets for `@claude` tagging on Issues/PRs

## Optional Future Work
- Agent swarm system (oh-my-claudecode / claude-squad) — researched in MASTER_SOP.md, not yet installed
