---
name: jarvis-task-manager
description: How Claude Code agents interact with the JARVIS task registry. Use when starting, completing, or checking status of business tasks to prevent duplicate work across Claude Code sessions.
---

# JARVIS Task Manager

The shared Claude Code task registry lives at:
```
~/.claude/jarvis/tasks.db  (SQLite)
```

The Python client lives at:
```
~/projects/claude-code-config/jarvis/client.py
```

PaxBot agents use a separate internal registry (`paxbot/jarvis/tasks.json`). Both track work — Claude Code sessions coordinate via SQLite, PaxBot agents coordinate via JSON.

---

## Before Starting ANY Business Task

Check for active duplicates first:

```python
import sys
sys.path.insert(0, r'C:\Users\highe\projects\claude-code-config\jarvis')
from client import check_duplicate, list_tasks

dupe = check_duplicate(["keyword1", "keyword2"])  # keywords from your objective
if dupe:
    print(f"Already in progress: [{dupe['task_id']}] @{dupe['owner']}: {dupe['objective']}")
    # Stop here — consume the existing result instead
else:
    print("No duplicate found — safe to proceed")
```

If a similar task is IN_PROGRESS — **do not re-do it**.

---

## Claim a Task

```python
import sys
sys.path.insert(0, r'C:\Users\highe\projects\claude-code-config\jarvis')
from client import claim_task

task_id = claim_task(
    objective="What you're about to do",
    owner="claude-code",          # or "ceo-agent", "sales-agent", etc.
    source="claude-code",
    expected_output="What done looks like",
    priority=3,                   # 1=critical 2=high 3=normal 4=low 5=backlog
)
print(f"Claimed task: {task_id}")
```

Save `task_id` — you need it to close the task.

---

## Complete a Task (with evidence)

```python
from client import complete_task

complete_task(
    task_id=task_id,
    result="One-sentence summary of what was accomplished",
    evidence="Proof: file written at X, test passed, API returned 200, etc.",
)
```

Never mark complete without real evidence. "I tried" is not evidence.

---

## Mark Blocked

```python
from client import block_task
block_task(task_id, reason="Waiting on Gmail app password — cannot send email")
```

---

## View Registry

```python
from client import list_tasks
tasks = list_tasks(status="IN_PROGRESS")
for t in tasks:
    print(f"[{t['task_id'][:8]}] @{t['owner']}: {t['objective'][:70]}")
```

---

## Quick One-Liner Check (Bash)

```bash
python3 -c "
import sys; sys.path.insert(0, r'C:\Users\highe\projects\claude-code-config\jarvis')
from client import list_tasks
tasks = list_tasks(limit=10)
print(f'{len(tasks)} recent tasks')
for t in tasks: print(f\"  [{t['status'][:2]}] @{t['owner']}: {t['objective'][:60]}\")
"
```

---

## Rules

1. **Check before claiming** — one keyword match = stop and coordinate
2. **Claim before working** — unclaimed = duplicatable
3. **Complete with evidence** — result + evidence fields both required
4. **Blocked = say why** — enables another agent to unblock you
5. **Failed = honest** — mark FAILED rather than silently abandoning
