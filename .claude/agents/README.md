# Sub-Agent Ecosystem

Global sub-agents synced to `~/.claude/agents/`. Available across all projects on this machine.

## Anatomy

Each agent is a Markdown file with YAML front matter. Valid Claude Code subagent fields:

| Field | Purpose |
|-------|---------|
| `name` | Unique identifier (kebab-case). |
| `description` | Precise, action-oriented trigger phrasing. The parent reads ONLY this block first (progressive disclosure) to decide whether to summon the agent — keep it tight. |
| `tools` | Comma-separated allow-list (e.g. `Read, Grep, Glob`). Omit to inherit all tools. There is no `disallowed_tools` field — restrict by listing only what's allowed. Read-only = omit Edit/Write. |
| `model` | Alias: `haiku`, `sonnet`, `opus`, or `inherit`. NOT a full model ID. |
| `maxTurns` | Optional cap on the agent's tool-use turns. |
| `skills` | Optional list of skills to preload. |

> Note: the common "sub-agent template" circulating online includes `memory:`, `color:`, and `disallowed_tools:` and lists `tools: [readonly]`. Those are **not** valid Claude Code subagent fields and are silently ignored or rejected. The files here use the real schema.

## The Roster

| Agent | Role | Model | Access |
|-------|------|-------|--------|
| `analyst` | Heavy research / context-gathering that would pollute the main window | sonnet | read-only + web |
| `code-reviewer` | Unbiased correctness + security review of a diff | sonnet | read-only + inspection Bash |
| `plan-roaster` | Adversarial red-team of a plan before implementation | opus | read-only |

## Orchestration Strategy (the parent's job)

The main session is the **orchestrator**. Sub-agents have a 1-to-1 relationship back to it — they cannot talk to each other. The parent owns delegation and synthesis.

1. **Map task → agent.** Match the work to a roster entry by its `description`. If nothing fits, do it directly or use the general-purpose agent.
2. **Delegate to protect context.** Hand off token-heavy reading (research, log/diff review, plan critique) so the raw material lands in the sub-agent's context, not the parent's. The parent keeps the conclusion.
3. **Parallelize independent work.** Launch independent sub-agents in a single message so they run concurrently (e.g. `analyst` gathering context while `code-reviewer` audits a separate diff). Never chain them when they don't depend on each other.
4. **Isolate for unbiased review.** Use `code-reviewer` and `plan-roaster` precisely because they run in a clean context — do not feed them the implementation rationale you want validated; let them reach their own conclusion.
5. **Synthesize.** Sub-agent final messages return to the parent only (not the user). Relay what matters, reconcile conflicting reports, and present one coherent answer.
6. **Right-size the model.** Default sub-agents to cheaper/faster models; reserve `opus` for genuine deep reasoning (e.g. `plan-roaster`). This protects the parent/Opus token budget.

## Adding an Agent

1. Drop a new `.md` file in this directory using the schema above.
2. Write the `description` for accurate auto-triggering — this is what prevents misfires.
3. Restrict `tools` to the minimum the role needs.
4. Add a row to the roster table and commit.
