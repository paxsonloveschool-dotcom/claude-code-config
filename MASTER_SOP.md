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

## 10. Deep Patterns Extracted From All Repos

### A. Token Optimizer (claude-token-optimizer)
- 4 essential files at startup (~800 tokens): CLAUDE.md, COMMON_MISTAKES, QUICK_START, ARCHITECTURE_MAP
- Zero-token historical context via `.claudeignore` (sessions, archives never auto-loaded)
- Topic-based loading: learnings files only when needed (~200-700 tokens each)
- Keep CLAUDE.md under 200 lines; split any file over 1,000 lines
- Include token cost estimates in docs/INDEX.md for navigation
- No content duplication — link to detail docs instead of copying
- Typical savings: 83-87% across 9 frameworks

### B. GodMode Context Management
- **Context thresholds**: 50% normal, 70% optimize, 80% `/compact`, 90% mandatory split, 95% emergency
- **Per-agent budgets**: architect 30-40%, builder 20-30%, validator 15-20%, scribe 10-15%
- **Progressive loading**: start with overview (file tree, git status), load files only when needed
- **Offload to reports**: agents write to disk, next agent reads file not chat history
- **Context restore prompt** after `/compact`: re-establish identity + rules + workflows in ~30 lines
- **Parallel quality gates**: validator + tester run simultaneously (40% faster)
- **Self-interruption triggers**: table of "if doing X, STOP and do Y"

### C. COG Second Brain Patterns
- **Integration states**: Active (use), Disabled (skip silently), Unknown (ask once)
- **Role packs**: match user role -> prioritize relevant skills
- **Agent modes**: Solo (one conversation) vs Team (delegate to sub-agents)
- **Pre-flight check**: every skill checks profile exists, reads preferences, runs `date`
- **Dedup pattern**: read last 3 briefs, extract URLs from frontmatter, skip covered stories
- **Auto-research**: decompose into 5-7 threads, spawn all in parallel, always include contrarian view
- **Verification-first**: 2+ sources per claim, confidence levels, 7-day freshness for news

### D. Obsidian Claude PKM Patterns
- **Goal cascade**: 3yr Vision -> Yearly -> Projects -> Monthly -> Weekly -> Daily
- **CLAUDE.local.md**: personal overrides not committed to git
- **GTD inbox processing**: 2-minute rule, classify as next-action/project/waiting/someday/reference
- **Energy-based time blocking**: Morning=deep focus, Afternoon=meetings, Evening=light tasks
- **Max 3 active high-priority goals** at once
- **Agent team parallelization**: collector + goal-analyzer + project-scanner run simultaneously
- **Smart review routing**: check time -> day of week -> day of month -> staleness -> override

### E. Second Brain Skills Patterns
- **"Context window is a public good"** — skills share it with everything else
- **Challenge each paragraph**: "Does Claude really need this?" / "Does this justify its token cost?"
- **Progressive disclosure (3 levels)**: Metadata always (~100 words) -> SKILL.md on trigger (<5k words) -> Resources on demand (unlimited)
- **SKILL.md max 500 lines** to minimize context bloat
- **Degrees of freedom**: High (text) / Medium (pseudocode) / Low (specific scripts)
- **`disable-model-invocation: true`** for deterministic skills (git ops, file moves) — zero LLM cost
- **Batch processing**: never >5 items at once, validate after each batch
- **SOP structure**: TL;DR -> Definition of Done (checklist) -> When to Use -> Prerequisites -> Process -> Verify -> Troubleshoot
- **Anti-patterns**: kill passive voice, "per company policy", "it is recommended that", "please ensure"

### F. Second Brain Starter Architecture
- **Memory hierarchy**: SOUL.md (personality) + USER.md (config) + MEMORY.md (decisions) = loaded every session. Daily logs = append-only short-term memory
- **Hook lifecycle**: SessionStart (inject context) -> PreCompact (save before compression) -> SessionEnd (save on exit)
- **Hybrid RAG**: 0.7 vector + 0.3 keyword, FastEmbed ONNX, incremental indexing
- **Integration pattern**: each integration = Python module with dataclass -> auth -> query -> formatter -> CLI
- **Heartbeat pattern**: Python gathers data BEFORE invoking Claude, LLM reasons over pre-loaded context, ~$0.05/run vs $0.38 with MCP
- **Security 3 layers**: Sanitize (pattern detect + escape) -> Guardrails (pre-check + LLM eval) -> API Key Isolation (Python handles auth, LLM sees only data)

---

## 11. Implementation Playbook (Condensed)

### Quick Wins (done)
1. ✅ CLAUDE.md autopilot + efficiency rules
2. ✅ settings.json permissions
3. ✅ .claudeignore blocking noise
4. ✅ 4-file context structure
5. ✅ MASTER_SOP.md as single source of truth
6. ✅ Python 3.12.10 + pip 25.0.1 verified
7. ✅ Obsidian v1.12.7 installed
8. ✅ claude-squad v1.0.17 Windows binary installed (in PATH)

### Next Session Priorities
1. Install **oh-my-claudecode** plugin (30-50% more token savings) — requires `/plugin` slash command in Claude Code UI, cannot install via bash
2. Set up **obsidian-mind** vault (persistent memory across sessions)
3. Implement **context thresholds** (auto-compact at 70%, mandatory at 90%)
4. Add **session hooks** from GodMode (SessionStart context injection)
5. Create **role pack** from COG (prioritize skills by your work type)
6. **GHL HP Landscaping workflows** — Chrome must be pre-authenticated; see GHL_WORKFLOW_NOTES.md

### Recently Completed (2026-04-05)
- ✅ Python 3.12.10 — confirmed installed at `AppData/Local/Programs/Python/Python312/python.exe`, pip 25.0.1
- ✅ Obsidian v1.12.7 — installed via winget
- ✅ claude-squad v1.0.17 — Windows binary at `~/tools/claude-squad.exe` and `~/AppData/Local/Microsoft/WindowsApps/claude-squad.exe` (in PATH)
- ⚠️ oh-my-claudecode — NOT installable via bash; requires `/plugin marketplace add` in Claude Code UI
- ⚠️ GHL workflow audit — blocked by Chrome MCP timeout (GHL SPA + unauthenticated Chrome); see GHL_WORKFLOW_NOTES.md

### Future Phases
- Deploy Khoj self-hosted second brain
- Set up claude-squad for parallel agents (binary ready at ~/tools/claude-squad.exe)
- Implement heartbeat pattern (Python pre-loads data, Claude reasons)
- Add integration modules (Gmail, Calendar, Slack)
- Build custom skills with progressive disclosure

---

## 12. Obsidian Mind — Full Reference

### 15 Slash Commands
| Command | Purpose |
|---------|---------|
| `/standup` | Morning kickoff — load context, review yesterday, surface priorities |
| `/dump` | Freeform capture — auto-classifies and routes to correct folder |
| `/wrap-up` | Session review — verify notes, indexes, links, run brag-spotter |
| `/humanize` | Rewrite notes to sound like you, not AI |
| `/weekly` | Cross-session synthesis, North Star alignment, uncaptured wins |
| `/capture-1on1` | Parse meeting notes into structured 1:1 note |
| `/incident-capture` | Reconstruct incidents from Slack |
| `/slack-scan` | Deep scan Slack for evidence about a person/project |
| `/peer-scan` | Scan peer's GitHub PRs for review prep |
| `/review-brief` | Generate review brief (manager or peer version) |
| `/self-review` | Write self-assessment with charcount validation |
| `/review-peer` | Write peer review with per-project feedback |
| `/vault-audit` | Deep structural audit — orphans, links, frontmatter, stale notes |
| `/vault-upgrade` | Import/migrate content from another vault |
| `/project-archive` | Archive completed project, update all indexes |

### 9 Subagents
| Agent | Purpose |
|-------|---------|
| brag-spotter | Find uncaptured wins and competency gaps |
| context-loader | Load all vault context about a topic |
| cross-linker | Find missing wikilinks and orphan notes |
| people-profiler | Bulk create person notes from Slack profiles |
| review-fact-checker | Verify claims in review drafts against vault sources |
| review-prep | Aggregate all performance evidence for review period |
| slack-archaeologist | Full Slack reconstruction with timeline |
| vault-librarian | Vault maintenance — orphans, broken links, stale notes |
| vault-migrator | Classify and migrate content from any source vault |

### 5 Session Hooks
| Hook | What It Does |
|------|-------------|
| SessionStart (`session-start.sh`) | QMD re-index, inject North Star, active work, recent git changes, open tasks, file listing |
| UserPromptSubmit (`classify-message.py`) | Auto-classify messages as decisions/incidents/wins/1:1s, inject routing hints |
| PostToolUse (`validate-write.py`) | Validate frontmatter and wikilinks on new/edited .md files |
| PreCompact (`pre-compact.sh`) | Backup session transcript before context compaction (keeps last 30) |
| Stop | Print end-of-session checklist |

### Vault Structure
```
Home.md                    # Entry point
CLAUDE.md                  # 339-line operating manual
brain/
├── North Star.md          # Goals — read every session
├── Memories.md            # Memory index
├── Key Decisions.md
└── Patterns.md
work/
├── active/                # 1-3 current projects
├── archive/YYYY/          # Completed work
├── incidents/
└── 1-1/                   # Meeting notes by person
org/
├── people/                # One note per person
└── teams/                 # One note per team
perf/
├── Brag Doc.md            # Running win log
├── competencies/          # Framework notes
└── evidence/              # PR scans, review artifacts
thinking/                  # Drafts and session logs
templates/                 # Note templates
```

### Key Rules
- Graph-first: a note without links is a bug
- All notes get YAML frontmatter (date, description, tags)
- Memory lives in vault `brain/` notes, not `~/.claude/`
- Never modify `.obsidian/` directory
- Git sync is user-controlled

---

---

## 13. GHL (GoHighLevel) Workflows

See `GHL_WORKFLOW_NOTES.md` for full details.

**Agency:** Restore Marketing (restoremarketingco@gmail.com)
**Auth:** Google SSO

| Sub-Account | Location ID |
|-------------|-------------|
| HP Landscaping | Gqozcy4LpsUukpaWg9b3 |
| Bison Metal Building | — |
| Blacktop Towing | — |
| Language Learning Center | — |
| Restore Marketing | — |

**Status (2026-04-05):** HP Landscaping workflow is built and working; minor changes needed. Chrome must be pre-authenticated before automated audit can run. GHL SPA requires 15+ seconds to load — navigate manually first.

---

*Last updated: 2026-04-05*
*Repo: https://github.com/paxsonloveschool-dotcom/claude-code-config*
