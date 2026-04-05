# Claude Code Configuration

## Context Files (load on demand, not at startup)
- `~/.claude/COMMON_MISTAKES.md` — Known pitfalls (read when debugging)
- `~/.claude/QUICK_START.md` — Daily commands (read when onboarding)
- `~/.claude/ARCHITECTURE_MAP.md` — System layout (read when exploring)

## Autopilot Mode
- All permissions are pre-approved. Do not ask for confirmation on tool usage.
- Execute tasks autonomously without pausing for approval.
- Only stop for genuinely ambiguous requirements, never for permission checks.

## Token Saving & Efficiency Rules

### Output Efficiency
- Be extremely concise. No preamble, no filler, no restating the request.
- Lead with action, not explanation. Do the thing, then summarize in 1 line.
- Never output code you just wrote back to the user — they can see the diff.
- Skip trailing summaries unless the user asks "what did you do?"
- Use short variable names in explanations. Don't re-explain what the user already knows.

### Tool Call Efficiency
- Batch all independent tool calls into a single parallel message.
- Never read a file you already have in context from this session.
- Use Grep/Glob before Read — only read files you actually need.
- Prefer Edit over Write for existing files (sends only the diff).
- Use agents for parallel independent subtasks to save main context.
- When exploring, use the Explore agent instead of multiple sequential searches.

### Context Window Management
- Do not repeat large code blocks in text output — reference by file:line instead.
- Compress reasoning. Internal chain-of-thought should be minimal.
- Drop completed context aggressively — once a subtask is done, move on.
- Use TodoWrite to track state instead of keeping it all in working memory.

### Two-Part Task Execution Pattern
When given a complex task, split it into exactly two phases:
1. **Phase 1 — Research & Plan**: Explore the codebase, understand requirements, design the approach. Output a brief plan.
2. **Phase 2 — Execute & Verify**: Implement all changes, run tests/builds, verify correctness.

Do not interleave research and implementation. Complete all research first, then execute.

### Avoid Waste
- Don't add comments, docstrings, or type annotations to unchanged code.
- Don't refactor adjacent code unless asked.
- Don't add error handling for impossible scenarios.
- Don't create abstractions for one-time operations.
- Don't create README or doc files unless explicitly asked.
- One simple solution > one clever solution.
