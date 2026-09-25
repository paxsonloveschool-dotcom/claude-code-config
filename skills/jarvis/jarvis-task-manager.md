---
name: jarvis-task-manager
description: How Claude Code agents interact with the JARVIS task registry. Use when starting, completing, or checking status of business tasks to prevent duplicate work across PaxBot and Claude Code sessions.
---

# JARVIS Task Manager

The shared task registry lives at:
```
C:\Users\highe\paxbot\jarvis\tasks.json
```

Both PaxBot (Python agents) and Claude Code sessions read/write this file. It's JSON, no server required.

---

## Before Starting ANY Business Task

Run this check first (use the Bash tool):

```bash
python3 -c "
import json
REGISTRY = r'C:\Users\highe\paxbot\jarvis\tasks.json'
with open(REGISTRY) as f:
    tasks = json.load(f)
active = [t for t in tasks if t['status'] == 'IN_PROGRESS']
print(f'{len(active)} active tasks:')
for t in active:
    print(f\"  [{t['task_id']}] @{t['owner']}: {t['objective'][:80]}\")
" 2>/dev/null || echo "Registry empty or unavailable"
```

If a similar task is already IN_PROGRESS by another agent — **do not duplicate it**. Check the result and continue from there.

---

## Claim a Task

```python
import json, uuid
from datetime import datetime

REGISTRY = r'C:\Users\highe\paxbot\jarvis\tasks.json'

with open(REGISTRY) as f:
    tasks = json.load(f)

task = {
    "task_id": str(uuid.uuid4())[:8],
    "objective": "YOUR OBJECTIVE HERE",
    "owner": "claude-code",        # or the specific role: "ceo", "sales", etc.
    "status": "IN_PROGRESS",
    "priority": "normal",           # critical | high | normal | low
    "created_at": datetime.now().isoformat(),
    "updated_at": datetime.now().isoformat(),
    "result": None,
    "failure": None,
}
tasks.append(task)

with open(REGISTRY, 'w') as f:
    json.dump(tasks, f, indent=2)

print(f"Claimed task {task['task_id']}")
```

Save the `task_id` — you need it to release the task.

---

## Complete a Task (with evidence)

```python
import json
from datetime import datetime

REGISTRY = r'C:\Users\highe\paxbot\jarvis\tasks.json'
TASK_ID = "YOUR_TASK_ID"
RESULT = "Brief description of what was accomplished + evidence"

with open(REGISTRY) as f:
    tasks = json.load(f)

for t in tasks:
    if t['task_id'] == TASK_ID:
        t['status'] = 'COMPLETED'
        t['result'] = RESULT
        t['updated_at'] = datetime.now().isoformat()
        break

with open(REGISTRY, 'w') as f:
    json.dump(tasks, f, indent=2)

print(f"Task {TASK_ID} completed")
```

---

## Mark Blocked

```python
# Same pattern, set status='BLOCKED', result=None, failure="reason why blocked"
```

---

## View Full Registry Summary

```bash
python3 -c "
import json
REGISTRY = r'C:\Users\highe\paxbot\jarvis\tasks.json'
with open(REGISTRY) as f:
    tasks = json.load(f)
by_status = {}
for t in tasks:
    by_status.setdefault(t['status'], []).append(t)
for status, items in sorted(by_status.items()):
    print(f'{status}: {len(items)}')
    for t in items[-3:]:
        print(f\"  [{t['task_id']}] @{t['owner']}: {t.get('result') or t['objective'][:60]}\")
"
```

---

## Rules

1. **Always check before claiming** — don't start work another agent already owns
2. **Always claim before working** — unclaimed work can be duplicated
3. **Always release with evidence** — "completed" without evidence doesn't count
4. **If blocked, say why** — another agent or human may be able to unblock you
