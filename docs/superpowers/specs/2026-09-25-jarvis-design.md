# JARVIS System Design
**Date:** 2026-09-25  
**Status:** Approved — implementing

## Overview
JARVIS is a unified multi-agent governance layer for Paxson Berkey's business operations. It governs both PaxBot (Telegram-facing Python agents) and Claude Code sessions through a shared file-based task registry and a set of Claude Code skills encoding the JARVIS operating constitution.

## Goals
- Persistent task tracking across sessions and runtimes
- No duplicate work between PaxBot agents and Claude Code sessions
- Verified completions (evidence required, not just attempt)
- Proactive autonomous execution via scheduled cron triggers

## Architecture

```
~/projects/claude-code-config/
├── skills/jarvis/
│   ├── jarvis-constitution.md       # 19-rule operating discipline
│   ├── jarvis-task-manager.md       # Registry CRUD instructions
│   └── jarvis-agent-roster.md       # 9-agent role/mission definitions
├── jarvis/
│   ├── client.py                    # Python registry client
│   └── schema.sql                   # SQLite schema

~/.claude/jarvis/                    # Runtime (not in repo)
├── tasks.db                         # Shared SQLite task registry
├── reports/                         # Agent output reports
└── knowledge/                       # Durable cross-session knowledge

C:\Users\highe\paxbot\
├── agents/base.py                   # + _claim_task, _complete_task, _block_task
└── agents/*.py                      # + JARVIS system prompt prefix
└── orchestrator.py                  # + duplicate check before routing
```

## Task Registry Schema

```sql
CREATE TABLE tasks (
    task_id      TEXT PRIMARY KEY,
    objective    TEXT NOT NULL,
    owner        TEXT DEFAULT 'unowned',
    status       TEXT DEFAULT 'PENDING',
    priority     INTEGER DEFAULT 3,
    source       TEXT,
    created_at   TEXT,
    updated_at   TEXT,
    expected_output TEXT,
    result       TEXT,
    evidence     TEXT,
    dependencies TEXT
);
```

Valid statuses: `PENDING` `IN_PROGRESS` `BLOCKED` `REVIEW` `COMPLETED` `FAILED` `CANCELLED`

## Skills

### jarvis-constitution
The 19-rule JARVIS operating constitution adapted for Paxson's businesses. Pre-fills:
- `AGENT_ROLE` = "business operations worker inside the JARVIS system"
- `AGENT_MISSION` = "execute Paxson Berkey's business objectives across HP Landscaping and Restore Marketing with discipline, no duplicate work, and verified results"

### jarvis-task-manager
Teaches Claude Code agents how to interact with `~/.claude/jarvis/tasks.db`:
- Check for existing IN_PROGRESS tasks matching your objective before starting
- Claim a task (set owner + IN_PROGRESS)
- Report completion with evidence
- Mark blocked with reason

### jarvis-agent-roster
Defines the 9 business agents with role, mission, and domain ownership:
personal, ceo, social, marketing, sales, operations, admin, hr, cfo

## PaxBot Upgrades

**BaseAgent additions:**
- `_claim_task(objective, source) → task_id`
- `_complete_task(task_id, result, evidence)`
- `_block_task(task_id, reason)`
- `_check_duplicate(objective) → Optional[task_id]`

**All agents:** 5-line JARVIS discipline prefix in system_prompt (prime directive, verify before claiming done, no duplicate work).

**Orchestrator:** Before routing, check registry for similar IN_PROGRESS task. If found, return status instead of re-processing.

## Proactive Scheduling (CronCreate)
- `0 7 * * *` → CEO morning briefing
- `0 14 * * *` → Sales lead pipeline check  
- `0 17 * * 1-5` → Operations daily wrap-up

## Data Flow
1. Input arrives (Telegram / Claude Code / Cron)
2. Check registry for duplicate IN_PROGRESS → return status if found
3. Claim task (owner = agent name, status = IN_PROGRESS)
4. Execute with tools
5. Verify result
6. Mark COMPLETED with evidence (or BLOCKED/FAILED with reason)
7. Push result to Telegram if unattended

## Build Split (Parallel Sessions)
- **This session:** JARVIS skills (3 files) + cron setup
- **highe-c0:** Python client + SQLite schema + runtime directory init
- **highe-fe:** PaxBot agent upgrades (base.py + all agents + orchestrator)
