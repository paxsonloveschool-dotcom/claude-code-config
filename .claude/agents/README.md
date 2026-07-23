# Claude Sub-Agent System

> Canonical reference for building production-grade multi-agent workflows across all projects.
> Location: `.claude/agents/` (project-level) or `~/.claude/agents/` (global)

## Overview

This directory contains specialized sub-agent definitions that extend Claude Code's capabilities through parallelization, token isolation, and domain-specific focus. Each agent is a self-contained Markdown file with YAML front matter that describes its role, model tier, tool restrictions, and behavioral contract.

## Architecture Principles

### 1. Progressive Disclosure
- YAML header is read FIRST to match trigger conditions
- Descriptions are tight (1 sentence) to avoid token bloat before agent activation
- Claude only instantiates the agent if the description matches the current task

### 2. Token Economy
- Parent agent handles orchestration and synthesis
- Sub-agents run at faster/cheaper tiers (Haiku/Sonnet) unless deep reasoning required
- Each agent operates in isolation with explicit tool boundaries
- No cross-agent communication; 1-to-1 relationships only back to parent session

### 3. Strict Boundaries
- Tools are EXPLICITLY allowed (whitelist) or EXPLICITLY disallowed (blacklist)
- Read-only agents have `disallowed_tools: ["bash", "edit", "write"]`
- Write-capable agents declare exactly which mutation tools they need
- No implicit permissions; every capability is declared upfront

## File Anatomy

```markdown
---
name: "agent_slug_name"
description: "Precise trigger: Use this agent when [specific condition]."
model: "claude-3-5-haiku"  # cheaper default; upgrade for deep reasoning
color: "pink"              # terminal/UI visual indicator
memory: "project"          # options: project|user|none|local
tools:
  - "readonly"             # preset: all read tools, no mutations
  # OR explicitly list:
  - "Bash"
  - "Read"
  - "Glob"
  - "Grep"
disallowed_tools:
  - "bash"                 # explicitly block write/execution
  - "Edit"
---

# Instructions
You are a [Role] specialist. Your job is [mission].

## Core Objectives
1. ...
2. ...

## Execution Steps
1. ...
2. ...

## Output Format
[Specify exactly how you return results to the parent]
```

## Agent Roles & Tier Mapping

| Role | Model | Use Case | Typical Tools |
|------|-------|----------|--------------|
| **Orchestrator** (parent) | Opus 4.8 | Breaks down tasks, delegates, synthesizes reports | All |
| **Analyst** | Haiku 4.5 | Data mining, log reading, scraping | Readonly |
| **Code Reviewer** | Sonnet 5 | Deep code analysis, architecture review | Readonly + Grep |
| **Adversarial Verifier** | Sonnet 5 | Tests claims, finds edge cases | Glob + Grep |
| **Writer** | Haiku 4.5 | Content generation, summarization | Write + Edit |
| **Executor** | Opus 4.8 | Complex multi-file refactors | All |

## How to Use

### Pattern 1: Parallel Independent Tasks
```
Parent (Opus):
  ├─ Agent 1: Audit logs for errors (Haiku, readonly)
  ├─ Agent 2: Review code style (Sonnet, readonly)
  └─ Agent 3: Extract metrics (Haiku, readonly)
  → Synthesize all findings into a single report
```

### Pattern 2: Clean-Context Review
```
Parent (Opus, full context):
  → Delegate to Reviewer (Sonnet, fresh context)
  ← Get unbiased findings back
  → Integrate findings without contamination
```

### Pattern 3: Isolated Execution
```
Parent (Opus, read-only):
  → Delegate write tasks to Executor (Opus, worktree isolation)
  ← Get results with proof (test output, logs)
  → Review diff, accept/reject, push
```

## Common Mistakes

❌ **Mistake:** Agents talk to each other
- **Fix:** All communication goes through parent session only

❌ **Mistake:** No tool restrictions (agent can do anything)
- **Fix:** Explicitly declare `tools` or `disallowed_tools` in YAML

❌ **Mistake:** Verbose descriptions that waste tokens
- **Fix:** Description ≤ 1 sentence; full context in # Instructions section

❌ **Mistake:** Sub-agents use Opus by default
- **Fix:** Default to Haiku/Sonnet; only upgrade when reasoning depth matters

❌ **Mistake:** Forgetting to set `memory: "none"` for one-off tasks
- **Fix:** Prevents token waste on irrelevant session history

## Deployment Checklist

- [ ] Agent file is named `agent-name.md` (kebab-case, lowercase)
- [ ] YAML block is valid and includes: `name`, `description`, `model`, `tools` or `disallowed_tools`
- [ ] Description is 1 sentence and action-oriented
- [ ] # Instructions section is clear and unambiguous
- [ ] Model choice matches task complexity (Haiku for simple, Sonnet for mid, Opus for deep)
- [ ] Tool restrictions are explicit (whitelist or blacklist, not both)
- [ ] Agent is placed in `.claude/agents/` (project) or `~/.claude/agents/` (global)
- [ ] Tested: Parent can spawn agent via `Agent(prompt)` with matching description

## Triggering Sub-Agents

In the parent session, use the `Agent` tool:

```python
Agent({
  description: "Quick audit of dependency licenses",  # Must match agent's description
  prompt: "Audit all dependencies in package.json and report license violations.",
  subagent_type: "analyzer",  # Optional: speed hint
  model: "haiku",              # Optional: override agent's default model
})
```

Claude matches your `description` parameter against all agent definitions (project + global) and spawns the best match.

## Best Practices

1. **Name agents by function, not project:**
   - ✅ `code-auditor.md` (reusable, shareable)
   - ❌ `social-suite-code-auditor.md` (project-specific, not discoverable)

2. **Keep agent descriptions action-oriented:**
   - ✅ "Use this agent when you need a security audit of code changes."
   - ❌ "General purpose code review agent for checking pull requests."

3. **Set `memory: "none"` for one-off tasks:**
   - Prevents token waste if agent spawns multiple times
   - Clears session history between invocations

4. **Use readonly agents for research:**
   - Faster execution, lower cost
   - Verifiable (can't accidentally mutate state)

5. **Isolate mutation agents:**
   - Use `isolation: "worktree"` when parallel agents write files
   - Prevents conflicts and allows safe rollback

## Examples in This Directory

- `analyst.md` — Data auditor for logs, CSVs, APIs
- `code-reviewer.md` — Deep code review with inline suggestions
- `adversarial-verifier.md` — Tests claims, finds edge cases
- `content-writer.md` — Documentation, blog posts, summaries

---

**Version:** 1.0 | **Last Updated:** 2026-07-06 | **Standards:** YAML frontmatter + Markdown instructions
