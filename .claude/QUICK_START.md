# Quick Start

## Daily Commands
- `gh auth status` — check GitHub login (should show `paxsonloveschool-dotcom`)
- `gh repo create <name> --public --clone` — new repo
- `git add -A && git commit -m "msg" && git push` — ship it

## Claude Code
- Rules: `~/.claude/CLAUDE.md` (autopilot + hybrid model + token efficiency)
- Settings: `~/.claude/settings.json` (permissions + SessionStart/Stop hooks)
- Mistakes: `~/.claude/COMMON_MISTAKES.md`
- Canonical source: `~/projects/claude-code-config/` (pushed to GitHub)

## Syncing Config Across Devices
```bash
# Edit the canonical version
cd ~/projects/claude-code-config
# ... make changes ...
git add -A && git commit -m "msg" && git push

# Other devices pick up changes automatically on next session start
# (SessionStart hook runs sync-config.sh)

# Or force a sync manually:
bash ~/.claude/sync-config.sh
```

## RTK (Token Compression, Manual Mode)
On Windows, the transparent hook doesn't work — prefix heavy commands manually:
```bash
rtk git diff              # 80% savings
rtk git log -n 10         # 80% savings
rtk grep "pattern" .      # 75% savings
rtk test cargo test       # 90% savings
rtk gain                  # View accumulated savings
```
Full transparent mode requires WSL (see Pending Setup in ARCHITECTURE_MAP.md).

## GitHub App for @claude Tagging
Once installed (see ARCHITECTURE_MAP.md Pending Setup), open any Issue in a repo that has `.github/workflows/claude.yml` and comment `@claude <task>`. Claude will execute via GitHub Actions — no local machine needed.
