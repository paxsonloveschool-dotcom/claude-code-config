# Claude Code Configuration

> Canonical source. Synced to `~/.claude/CLAUDE.md` on this machine.
> Repo: https://github.com/paxsonloveschool-dotcom/claude-code-config

## Context Files (load on demand, not at startup)
- `~/.claude/COMMON_MISTAKES.md` — Known pitfalls (read when debugging)
- `~/.claude/QUICK_START.md` — Daily commands (read when onboarding)
- `~/.claude/ARCHITECTURE_MAP.md` — System layout (read when exploring)
- `~/.claude/SESSION_HANDOFF.md` — Resume state for multi-session work
- `~/.claude/memory/MEMORY.md` — Live business state (Paxson, HP Landscaping, Restore)
- `~/.claude/memory/daily/YYYY-MM-DD.md` — Today's session log (auto-created by SessionStart hook)
- `~/.claude/memory/clients/` — Per-client files (hp-landscaping.md, restore.md)
- `~/.claude/memory/decisions/` — Decision log (why we made the choices we made)
- `~/.claude/memory/code-maps/` — Per-project codebase snapshots (auto-regenerated every session)
- `~/.claude/memory/sessions/` — Compressed session summaries (managed by claude-mem plugin)

**Memory is LOCAL-ONLY by default.** Content contains real client data and never gets pushed to public GitHub. Only the tooling scripts are in the `claude-code-config` repo.

## Autopilot Mode
- All tool permissions are pre-approved. Do not ask for confirmation on tool usage.
- Execute tasks autonomously on Bash, Read, Write, Edit, Agent, and MCP calls.
- Only stop for: (a) genuinely ambiguous requirements the plan didn't capture, or (b) destructive/irreversible actions outside the current scope.

## Confidence Before Coding (Plan Mode)
- Aim for 95% confidence in WHAT to build before starting non-trivial implementation.
- Ask clarifying questions about requirements, scope, and constraints — NOT about permissions.
- Once the plan is solid, switch to autopilot execution.

## Two-Part Task Execution
1. **Phase 1 — Research & Plan**: Explore, understand, design the approach. Output a brief plan.
2. **Phase 2 — Execute & Verify**: Implement all changes, run tests/builds, prove it works.

Do not interleave research and implementation. Complete all research first, then execute.

## Model Usage (Hybrid Strategy)
- **Opus 4.6** — Plan Mode, architecture, deep reasoning. Front-load intelligence so execution one-shots.
- **Sonnet 4.6** — executing a solid plan, routine edits, multi-file refactors.
- **Haiku 4.5** — sub-agents, formatting, summarization, simple lookups.
- Default: Opus for the plan, Sonnet for implementation once the plan is confirmed.

## Self-Verification (Always Prove It Works)
- Never report a task complete without proof. Run tests, start a dev server, open the preview browser, check logs, or hit the API.
- UI/frontend: start the server and confirm in a browser before declaring done.
- Backend/logic: run tests or execute the code path.
- If verification isn't possible, say so explicitly — never claim success without evidence.

## Token Saving & Efficiency Rules

### Output Efficiency
- Be extremely concise. No preamble, no filler, no restating the request.
- Lead with action, not explanation. Do the thing, then summarize in 1 line.
- Never output code you just wrote back to the user — they can see the diff.
- Skip trailing summaries unless asked "what did you do?"

### Tool Call Efficiency
- Batch all independent tool calls into a single parallel message.
- Never read a file you already have in context from this session.
- Use Grep/Glob before Read — only read files you actually need.
- Prefer Edit over Write for existing files (diff only).
- Use `@filename` references over broad directory searches.
- Use agents for parallel independent subtasks to save main context.
- When exploring, use the Explore agent over multiple sequential searches.

### Context Window Management
- Reference code by `file:line` rather than re-quoting large blocks.
- Compress reasoning. Internal chain-of-thought should be minimal.
- Drop completed context aggressively — once a subtask is done, move on.
- Use TodoWrite to track state instead of keeping it in working memory.
- Disconnect unused MCP servers — each loads tool defs every turn; prefer CLIs.
- Mind the 5-min prompt cache — breaks >5 min reprocess full context at full cost.
- Keep this CLAUDE.md under 200 lines — loaded as system context every turn.

### Session Management
- After completing a distinct task, suggest `/clear` if moving to something unrelated.
- At ~60% context capacity, proactively suggest `/compact` with preservation notes.
- Batch instructions in one message — 3 separate prompts cost ~3x one combined prompt.

### Avoid Waste
- No comments, docstrings, or type annotations on unchanged code.
- Don't refactor adjacent code unless asked.
- No error handling for impossible scenarios.
- No abstractions for one-time operations.
- Don't create README or doc files unless explicitly asked.
- One simple solution > one clever solution.

## Visibility
- Run `/context` periodically to see what's eating tokens (history vs files).
- Run `/cost` to check session spend.
- Keep `/status-line` on for live context-window usage.

## Session Timing
- Peak hours (8am–2pm ET) drain session windows faster — save big refactors and multi-agent work for evenings/weekends.

## Sub-Agents
- Delegate one-off tasks to sub-agents, especially Haiku-capable ones.
- Agent workflows use 7–10x more tokens — use sparingly.
- Only spin up sub-agents when parallelization genuinely helps.

## Skills & Specialization
- Before starting niche work, check if a relevant skill is loaded or available via the Skill tool.
- For recurring business workflows, build a custom skill with `anthropic-skills:skill-creator` instead of re-explaining each session.

## GitHub Action on New Repos
When starting work in a new git repo, run `/install-github-app` so `@claude` tagging works on PRs/Issues from any device.

## Per-Repo CLAUDE.md (Team Memory)
Each repo may have its own `./CLAUDE.md` with project-specific rules, checked into git for team memory. When a mistake is corrected inside a repo, add a one-liner to THAT repo's CLAUDE.md — not this global one.

## RTK (Token Compression) — Manual Mode on Windows
RTK v0.36.0 binary at `~/.local/bin/rtk.exe`. On native Windows, the transparent hook mode is unavailable — use manually for heavy commands:
- `rtk git diff`, `rtk git log`, `rtk grep <pattern>`, `rtk test <cmd>` → 60–90% token savings
- Full hook-based rewriting requires WSL. Install WSL later to unlock it.

## VoxCPM Narration (Content Funnel)
- Setup: `~/projects/VoxCPM` (Python 3.11 venv via uv)
- Wrapper: `~/projects/VoxCPM/narrate.sh "text" output.wav`
- Model: `openbmb/VoxCPM2` (2B params, 30 languages, 48kHz, voice cloning)
- CPU-only on this machine (no NVIDIA CUDA). Expect ~10-20x realtime.
- First run downloads ~4-8 GB weights to `~/.cache/huggingface/`
- Scripts and docs committed at `tools/voxcpm/` in this repo
- For real-time: use HF Spaces demo at https://huggingface.co/spaces/OpenBMB/VoxCPM-Demo

## Applied Learning
Add a one-line bullet (under 15 words) whenever something fails repeatedly, I have to re-explain, or a workaround is found. No explanations.

- (none yet)
