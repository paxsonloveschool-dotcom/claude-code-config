---
name: wat-init
description: >
  Scaffold a new WAT-architecture project (Workflows / Agents / Tools).
  Splits non-deterministic reasoning (agent + markdown workflows) from
  deterministic execution (Python tools) so the same skeleton works for
  local runs, Modal cron deploys, or webhook triggers.
  Use when the user says "init this project", "start a new WAT project",
  "scaffold a workflow project", "set up automation", "create the
  workflows/tools structure", or when opening an empty repo that only
  contains a CLAUDE.md and the user asks to build something in it.
  Triggers: "wat init", "init this project", "scaffold WAT", "new
  automation project", "set up workflows and tools".
---

# wat-init — Scaffold a WAT-architecture project

## The pattern

```
project-root/
├── CLAUDE.md              ← project system prompt (see reference template)
├── .env                   ← secrets — NEVER commit
├── .env.example           ← keys with empty values, committed
├── .gitignore             ← ignores .env, /temp, __pycache__, .DS_Store
├── requirements.txt       ← Python deps
├── workflows/             ← plain-language SOPs (one .md per workflow)
│   └── example.md
├── tools/                 ← deterministic Python (one .py per capability)
│   └── example_tool.py
├── temp/                  ← scratch outputs (gitignored)
└── logs/                  ← run logs (optional; gitignored)
```

**Why the split**: the agent (Claude) does reasoning + orchestration; the
tools do the boring deterministic work (API calls, transforms, DB writes).
When a tool fails, the agent reads the log, edits the tool, re-runs. The
workflow markdown captures the SOP so a fresh session can pick it up.

## Steps

1. **Confirm the project has a CLAUDE.md.** If missing, ask the user
   what the project does (2–3 sentences), then generate one from the
   starter template at `references/starter-CLAUDE.md`.

2. **Create the directories**:
   ```bash
   mkdir -p workflows tools temp logs
   ```

3. **Drop in the standard files**:
   - `.gitignore` — see `references/gitignore-template`.
   - `.env.example` — enumerate expected env vars with empty values.
   - `.env` — copy of `.env.example` for local dev (add to .gitignore
     first — verify before creating).
   - `requirements.txt` — start with `python-dotenv`, add per-tool as
     you build.

4. **Seed one workflow + tool example** so the pattern is visible:
   - `workflows/example.md` — the SOP template (Objective / Inputs /
     Steps / Tools / Outputs / Errors).
   - `tools/example_tool.py` — the tool template (loads .env, docstring
     with I/O contract, `if __name__ == "__main__":` runnable).

5. **Initialize git** if not already a repo:
   ```bash
   git init
   git add . && git commit -m "chore: scaffold WAT project structure"
   ```

6. **Verify the scaffold**:
   - `ls -la` shows all dirs + files.
   - `.env` is NOT tracked (`git status --short` shouldn't list it).
   - `python -c "from dotenv import load_dotenv; load_dotenv()"` runs
     clean.

## After scaffolding — the build loop

Switch Claude Code to Plan Mode, describe the goal, let the agent
inspect and ask clarifying questions about:
- Data sources / APIs needed
- Delivery channels (email, Sheets, Slack, PDFs)
- Output format / schedule

Then let the agent build tools iteratively. The **self-heal loop** is:
tool fails → agent reads the traceback → agent edits the .py → re-runs
→ updates the workflow doc if the SOP changed. Don't intervene unless
it loops for 3+ rounds without progress.

## Complementary skills

- **prompt-composer** — before letting Plan Mode run, batch your
  clarifying inputs into one message so the plan is right on turn 1.
- **modal-deploy** — once the workflow runs cleanly locally, ship it to
  Modal for scheduled/webhook execution.
- **security-review** (built-in) — always run before pushing tools that
  touch APIs or write files.

## When NOT to use

- Existing project with its own structure — don't force WAT on it.
- Pure library/CLI/frontend project — no workflows, no automation. WAT
  is for orchestration + tool-heavy work.
- One-off scripts — a single `.py` beats scaffolding overhead.

Source: Nate Herk, "Master 95% of Claude Code in 36 Mins" —
https://www.youtube.com/@nateherk
