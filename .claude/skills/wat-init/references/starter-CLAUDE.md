# <PROJECT NAME>

> One-sentence description of what this project does and who runs it.

## Architecture: WAT (Workflows / Agents / Tools)

- **workflows/** — plain-language SOPs (one .md per workflow). Each doc
  lists Objective, Inputs, Steps, Tools called, Outputs, Error handling.
- **tools/** — deterministic Python scripts. One capability per file.
  Loads secrets from `.env`. Runnable standalone via
  `python tools/<name>.py`.
- **The agent (Claude)** — reads a workflow doc, orchestrates tools in
  order, inspects outputs, self-heals errors, updates docs when the SOP
  changes.
- **temp/** — scratch outputs (gitignored).
- **logs/** — run logs (gitignored).

## Secrets

All API keys in `.env` (gitignored). Never hardcode a secret in a `.py`
file. Every tool that needs a secret does:

```python
import os
from dotenv import load_dotenv
load_dotenv()
API_KEY = os.environ["THING_API_KEY"]
```

`.env.example` lists every expected variable with an empty value. Keep
it in sync when you add a new secret.

## How the agent should behave

- **Plan first.** For any non-trivial ask, propose steps and tools
  before writing code.
- **One tool, one job.** Each `.py` in `tools/` does ONE thing well.
  Don't create god-modules.
- **Self-heal.** On tool failure: read the traceback, edit the tool,
  re-run. Update the workflow doc if the SOP changed.
- **Trace everything.** Long-running tools should write a line to
  `logs/<workflow>-<date>.log` per step.
- **Local first, deploy second.** Get the workflow working end-to-end
  locally before invoking `modal-deploy`.

## How to add a new workflow

1. Create `workflows/<name>.md` from the template (below).
2. For each step that needs deterministic code, add or reuse a tool in
   `tools/`.
3. Test locally: run the tools in order, verify outputs.
4. Optionally: deploy to Modal via the `modal-deploy` skill for
   scheduled or webhook execution.

## Workflow template (copy into workflows/<name>.md)

```markdown
# <Workflow Name>

**Objective**: <one sentence>

**Trigger**: <manual | cron:"0 6 * * MON" | webhook>

**Inputs**:
- <input 1: source, format>
- <input 2>

**Steps**:
1. <what happens; which tool>
2. <what happens; which tool>
3. <output written to where>

**Tools called**:
- `tools/<a>.py` — <one line what it does>
- `tools/<b>.py`

**Outputs**:
- <where the deliverable lands: file, email, Slack, Sheet>

**Errors**:
- <known failure mode> → <what to do>
- <API rate limit> → retry with backoff, alert if > 5 min
```

## Tool template (copy into tools/<name>.py)

```python
"""<one-line what this tool does>.

Inputs (kwargs or CLI args):
    - <name>: <type> — <meaning>
Outputs:
    - <what it returns / writes>
"""
from __future__ import annotations
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def run(<args>) -> <return type>:
    ...

if __name__ == "__main__":
    # CLI entry: parse argv, call run(), print result
    ...
```

## Applied learning
Add a one-line bullet when something breaks the second time. Keeps this
project's memory sharp without a novel.

- (none yet)
