# Session Handoff — Claude Code God Mode Setup

> Last updated: 2026-04-15
> Canonical source. Synced to `~/.claude/SESSION_HANDOFF.md` via SessionStart hook.
> Read this when picking up multi-session work or onboarding a new device.

## The Big Picture

This repo is the canonical source of truth for Claude Code configuration across all of Paxson's devices. A SessionStart hook auto-pulls the latest version on every new Claude Code session, so any change committed here propagates automatically.

**God-mode stack installed:**
- `superpowers` — 14-skill agentic framework (clarify → design → plan → execute → verify, TDD, visual dashboard)
- `episodic-memory` — semantic search across past Claude Code conversations (persistent memory between sessions)
- `elements-of-style` — Strunk writing rules for clear communication
- Merged global CLAUDE.md with Nate Herk's 18 Token Hacks + Boris's best practices
- Auto-sync pipeline (SessionStart hook pulls from this repo every session)
- RTK v0.36.0 binary for manual token compression (Windows manual mode; full hook mode pending WSL)

## Resume Checklist

### ✅ Fully Done (committed + pushed)
- [x] Global CLAUDE.md merged (109 lines, under 200-line ceiling)
- [x] Git identity set (`Paxson Berkey <paxsonloveschool@gmail.com>`)
- [x] `~/projects/claude-code-config` cloned, canonical repo
- [x] RTK v0.36.0 binary installed (`~/.local/bin/rtk.exe`, Windows PATH configured)
- [x] `sync-config.sh` auto-sync script + SessionStart hook
- [x] `wsl-check.sh` — auto-detects WSL install, prints RTK hook unlock steps
- [x] Stop hook reminds to push config changes
- [x] `.github/workflows/claude.yml` committed (ready for `@claude` tagging)
- [x] COMMON_MISTAKES.md updated with RTK Windows gotchas
- [x] ARCHITECTURE_MAP.md, QUICK_START.md, MASTER_SOP.md refreshed
- [x] **Superpowers plugin installed** (v5.0.7, user scope)
- [x] **episodic-memory plugin installed** (v1.0.15 — cross-session semantic memory)
- [x] **elements-of-style plugin installed** (v1.0.0)
- [x] Broken `autofix-bot` plugin removed

### 🖱️ Still Requires Physical Clicks (blocked at hard limits)
1. **Install WSL** — Run `wsl --install` in admin PowerShell, reboot, set Linux user/pwd. Unlocks RTK transparent hook mode (60–90% token savings on Bash calls).
2. **Install Claude GitHub App** — https://github.com/apps/claude → Install → select `claude-code-config`. Enables `@claude` tagging on Issues/PRs from any device.
3. **Add `ANTHROPIC_API_KEY` secret** — https://github.com/paxsonloveschool-dotcom/claude-code-config/settings/secrets/actions → New repository secret → paste key from https://console.anthropic.com/settings/keys

### 🔮 Optional Future Work
- Install `superpowers-chrome` plugin (BETA, direct Chrome DevTools Protocol access)
- Install `superpowers-lab` plugin (experimental: tmux automation, MCP discovery, Slack messaging)
- Build custom skill for HP Landscaping invoice/estimate workflow using `anthropic-skills:skill-creator`

## Bootstrap a New Device

Run this one-liner on any new machine to inherit the full setup:

```bash
curl -fsSL https://raw.githubusercontent.com/paxsonloveschool-dotcom/claude-code-config/main/bootstrap.sh | bash
```

Or, if you prefer to inspect first:

```bash
git clone https://github.com/paxsonloveschool-dotcom/claude-code-config ~/projects/claude-code-config
bash ~/projects/claude-code-config/bootstrap.sh
```

The bootstrap script:
1. Clones this repo to `~/projects/claude-code-config`
2. Copies CLAUDE.md + .claude/* files to `~/.claude/`
3. Installs `sync-config.sh` and `wsl-check.sh`
4. Sets up SessionStart hook in `~/.claude/settings.json`
5. Installs Superpowers, episodic-memory, elements-of-style plugins via `claude plugin install`
6. Prints the 3 physical-click items (WSL, GitHub App, API key)

## Key Paths

| Path | Purpose |
|---|---|
| `~/.claude/CLAUDE.md` | Global config, loaded every session |
| `~/.claude/SESSION_HANDOFF.md` | This file (synced from repo) |
| `~/.claude/settings.json` | Permissions + Notification/SessionStart/Stop hooks + enabledPlugins |
| `~/.claude/sync-config.sh` | Auto-sync from repo on session start |
| `~/.claude/wsl-check.sh` | WSL detection + RTK unlock reminder |
| `~/projects/claude-code-config/` | Canonical repo (pushed to GitHub) |
| `~/.local/bin/rtk.exe` | RTK binary (Windows, manual mode) |
| `~/.claude/plugins/cache/superpowers-marketplace/` | Installed Superpowers plugins |

## Known Gotchas

1. **Native Windows + RTK**: hook mode unavailable, legacy `--claude-md` injection bloats CLAUDE.md by ~140 lines. Fix = WSL.
2. **Side-chat Claude conversations** have no tool execution. For real execution, use `claude` command in git-bash or Claude.lnk desktop shortcut.
3. **Slash commands** (`/plugin`, `/install-github-app`, `/context`, `/cost`, `/clear`, `/compact`) only run inside Claude Code REPL — NOT from bash. But `claude plugin install` (without the slash) IS a valid bash subcommand. Use it for automation.
4. **GitHub auth scope**: Tokens need `repo` scope for push/create. No-scope tokens silently fail.
5. **Windows paths**: forward slashes in bash, backslashes in PowerShell. Mix causes silent failures.
6. **`claude` not in git-bash PATH by default**: it's at `~/AppData/Roaming/npm/claude`. Either `export PATH="$PATH:$HOME/AppData/Roaming/npm"` in `.bashrc` or type the full path.

## Resume Prompt Template

When starting fresh in a new session:

```
Read ~/.claude/CLAUDE.md and ~/.claude/SESSION_HANDOFF.md.
Tell me what's currently set up, what's still pending (physical-click items only),
and how to use the Superpowers /brainstorm, /plan, /execute skills for my next task.
```
