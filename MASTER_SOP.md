# Master SOP — Claude Code Second Brain & Agent System

> This file is the single source of truth for operating Claude Code with maximum efficiency.
> Load this file at session start. Everything else loads on demand.

---

## 1. System Architecture

### Config Locations
| File | Purpose | Loads |
|------|---------|-------|
| `~/CLAUDE.md` | Autopilot + efficiency rules | Every session (~450 tokens) |
| `~/.claude/settings.json` | Permission auto-approvals | System-level |
| `~/.claude/COMMON_MISTAKES.md` | Known pitfalls | On demand (~350 tokens) |
| `~/.claude/QUICK_START.md` | Daily commands | On demand (~100 tokens) |
| `~/.claude/ARCHITECTURE_MAP.md` | System layout | On demand (~150 tokens) |
| `~/.claudeignore` | Blocks old sessions from context | System-level |
| **Total startup cost:** | | **~450 tokens** |

### Cloned Repos (local at `C:\Users\highe\`)
| Repo | Category | Stars |
|------|----------|-------|
| `obsidian-mind/` | Claude + Obsidian vault system | — |
| `obsidian-ai-agent/` | Claude Code plugin for Obsidian | — |
| `obsidian-agent-client/` | Multi-agent in Obsidian (ACP) | — |
| `letta-obsidian/` | Stateful AI agent for Obsidian | — |
| `obsidian-ai-agents/` | Markdown-defined AI agents | — |
| `obsidian-claude-pkm/` | Cascading goals + 4 AI agents | 1.3k |
| `khoj/` | Self-hosted AI second brain | 33.9k |
| `second-brain-skills/` | Claude Code skills collection | 619 |
| `second-brain-starter/` | PRD generator for custom brain | 156 |
| `COG-second-brain/` | Self-evolving, 17 skills | 296 |
| `ClaudeCode_GodMode-On/` | Multi-agent orchestration | — |
| `claude-token-optimizer/` | Token-saving doc structure | — |

### GitHub
- **Account:** paxsonloveschool-dotcom
- **Config repo:** https://github.com/paxsonloveschool-dotcom/claude-code-config
- **Auth:** Classic PAT with full scopes, stored in gh CLI keyring

---

## 2. Token Saving Rules (Implemented)

### Output Rules
- No preamble, no filler, no restating the request
- Lead with action, summarize in 1 line after
- Never echo code back — user sees the diff
- Skip trailing summaries unless asked
- Short variable names in explanations

### Tool Call Rules
- Batch all independent calls into one parallel message
- Never re-read a file already in context
- Grep/Glob before Read — only read what's needed
- Edit over Write for existing files (diff only)
- Use agents for parallel independent subtasks
- Explore agent for multi-step searches

### Context Window Rules
- Reference code by file:line, don't repeat blocks
- Minimal chain-of-thought reasoning
- Drop completed context aggressively
- TodoWrite for state tracking, not working memory
- `.claudeignore` blocks: sessions/, backups/, shell-snapshots/, plugins/, node_modules/, .git/, *.log

### Two-Part Execution
1. **Phase 1 — Research & Plan**: Explore, understand, design. Output brief plan.
2. **Phase 2 — Execute & Verify**: Implement, test, verify. No interleaving.

### Avoid Waste
- No comments/docstrings/types on unchanged code
- No adjacent refactoring unless asked
- No error handling for impossible scenarios
- No abstractions for one-time ops
- No README/docs unless explicitly asked
- Simple > clever

---

## 3. Context Folder Structure (Token-Optimized)

```
C:\Users\highe\
├── CLAUDE.md                          # Session rules (~450 tokens, auto-loaded)
├── .claudeignore                      # Blocks noise from context
├── .claude/
│   ├── settings.json                  # Autopilot permissions
│   ├── COMMON_MISTAKES.md             # Load when debugging (~350 tokens)
│   ├── QUICK_START.md                 # Load when onboarding (~100 tokens)
│   └── ARCHITECTURE_MAP.md            # Load when exploring (~150 tokens)
├── claude-code-config/                # Git repo (pushed to GitHub)
│   ├── CLAUDE.md
│   ├── .claudeignore
│   ├── .claude/
│   │   ├── settings.json
│   │   ├── COMMON_MISTAKES.md
│   │   ├── QUICK_START.md
│   │   └── ARCHITECTURE_MAP.md
│   └── MASTER_SOP.md                  # THIS FILE
└── [cloned repos]/                    # Reference only, not in context
```

### Key Principle: Load on Demand
- Only CLAUDE.md loads every session (~450 tokens)
- Everything else is pulled in ONLY when needed
- Old sessions, backups, snapshots are `.claudeignore`'d
- Cloned repos stay outside context — grep into them only when needed

---

## 4. Active Integrations (MCP Servers)

| Server | Status | Use |
|--------|--------|-----|
| Claude in Chrome | Connected | Browser automation |
| Google Calendar | Connected | Calendar management |
| Gmail | Connected | Email management |
| Cloudflare | Connected | Workers, D1, KV, R2 |
| Figma | Connected | Design automation |
| Google Drive | Connected | Doc search/fetch |
| Claude Preview | Connected | Dev server preview |
| MCP Registry | Connected | Discover new MCPs |
| Scheduled Tasks | Connected | Cron jobs |

---

## 5. Research Results — Best Systems Found

### Second Brain (Top 3)
1. **Khoj** (33.9k⭐) — Self-hostable, every LLM, PDFs/Notion/Obsidian
2. **Obsidian Mind** — Vault-first memory, 5 hooks, 9 subagents, 15 commands
3. **COG** — Self-evolving, 17 skills, multi-agent support

### Agent Swarms (Top 3)
1. **oh-my-claudecode** (24.1k⭐) — 19 agents, 5 modes, 30-50% token savings
2. **Ruflo** (29.9k⭐) — 100+ agents, swarm hierarchies, Claude MCP native
3. **claude-squad** (6.8k⭐) — Parallel agents in isolated worktrees

### Claude Code Specific (Top 3)
1. **wshobson/agents** (33k⭐) — 182 agents, 147 skills, 95 commands
2. **ClaudeCode GodMode** — 8 specialized agents, dual quality gates
3. **Composio Agent Orchestrator** (5.8k⭐) — Parallel agents with own PRs

### Token Optimization (Top 2)
1. **claude-token-optimizer** — 4-file structure, 83-87% reduction
2. **claude-token-efficient** — 63% output reduction, 17.4% cost savings

---

## 6. Pending Implementation (Next Steps)

### Priority 1 — Install oh-my-claudecode
```
/plugin marketplace add https://github.com/Yeachan-Heo/oh-my-claudecode
/plugin install oh-my-claudecode
```
- 19 agents, Autopilot mode, 30-50% token savings built-in

### Priority 2 — Set up Obsidian Mind vault
```bash
cd ~/obsidian-mind
# Open as Obsidian vault
# Fill brain/North Star.md with goals
# Run claude in vault directory
```

### Priority 3 — Install claude-squad
```bash
# Windows: download from GitHub releases
# Manages parallel Claude agents in tmux
```

### Priority 4 — Deploy Khoj (self-hosted second brain)
```bash
cd ~/khoj
docker-compose up -d
# Connect to localhost:42110
```

### Priority 5 — Explore COG skills
```bash
cd ~/COG-second-brain
# Review skills/ directory
# Cherry-pick useful ones into your setup
```

---

## 7. Session Start Checklist

When starting a new Claude Code session:
1. CLAUDE.md auto-loads (autopilot + efficiency rules)
2. If debugging → read `~/.claude/COMMON_MISTAKES.md`
3. If lost → read `~/.claude/ARCHITECTURE_MAP.md`
4. If new commands → read `~/.claude/QUICK_START.md`
5. For full context → read this `MASTER_SOP.md`
6. Never load everything at once — on demand only

---

## 8. Git Workflow

```bash
export PATH="/c/Program Files/GitHub CLI:$PATH"
cd ~/claude-code-config
git add -A && git commit -m "update: description" && git push
```

---

## 9. Known Issues

1. GitHub tokens need `repo` scope — no-scope tokens silently fail
2. Windows paths: forward slashes in bash, backslashes in PowerShell
3. `gh` CLI needs PATH export each bash session
4. No SSH keys on this machine — use HTTPS + token
5. `gh auth login --web` times out fast — use `--with-token` instead

---

*Last updated: 2026-04-05*
*Repo: https://github.com/paxsonloveschool-dotcom/claude-code-config*
