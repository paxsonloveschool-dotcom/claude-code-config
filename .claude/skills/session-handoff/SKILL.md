---
name: session-handoff
description: >
  Migrate the current Claude Code session's working context into a fresh
  session without losing progress, so you don't burn full-priced tokens
  re-reading a bloated history. Use when (a) context is >150k tokens or the
  status line shows ~60%+, (b) about to switch to an unrelated task, (c) the
  session has sat idle >1h and the 1-hour cache TTL will expire on next
  message, or (d) the user says "handoff", "wrap up and continue fresh",
  "compact this", "reset context", "save state and clear".
  Prefer this over `/compact` — /compact can be slow and loses nuance.
  Triggers: "handoff", "session handoff", "hand off this session",
  "wrap up and continue", "start fresh with context", "save and reset",
  "compact and continue", "clear but keep progress".
---

# session-handoff — Clean Context Migration

Prompt caching (subscription): the whole session prefix stays cached for
**1 hour of inactivity**. Every message you send after that hour re-writes
the prefix at full price. `/model` toggles and dual-model setups (`opus plan`)
also invalidate the cache prefix on every switch. So the cheapest state is
a **fresh session seeded with a tight summary** — this skill produces that.

## Step 1 — Have the current session generate its handoff summary

Send this prompt in the current session, verbatim:

```
Generate a session handoff summary. Output ONLY the summary — no preamble,
no meta-commentary. Sections:

1. **Task** — one sentence: what we're doing and why.
2. **Progress so far** — bullets of completed work, each with file:line
   refs where relevant. Skip abandoned dead-ends.
3. **Files touched** — a bullet list of paths modified or created, with
   a 1-line note of what each contains.
4. **Architecture / decisions** — bullets of choices made and their
   rationale (only decisions a fresh session would need to respect).
5. **Open threads** — anything half-done, deferred, or awaiting a check.
6. **Next step** — the exact next command / edit / question, phrased so a
   fresh session can act on it without re-deriving intent.
7. **Skills / tools in play** — list the skills, MCP servers, or CLIs
   this task depends on (agent-reach, cookie-guardian, gh CLI, etc.).

Keep it under 400 words. Assume the reader has never seen this session.
```

## Step 2 — Copy the summary output

Full text into clipboard. Optionally save to
`~/.claude/memory/sessions/YYYY-MM-DD-<task>.md` for later replay.

## Step 3 — Reset

```
/clear
```

## Step 4 — Seed the fresh session

Paste the summary as the first user turn, prefixed with:

```
Resuming a previous session. Below is the handoff summary. Read it,
confirm you understand the state, then execute the "Next step" section.

<paste summary>
```

## When NOT to use

- Session is <30k tokens and cache is warm → just keep going, no gain.
- Task about to end in 1-2 turns → finish first, then handoff isn't needed.
- Cross-session state that must persist (client data, decisions log) →
  write to `~/.claude/memory/` files first; the handoff summary only
  covers ephemeral working state.

## Cache hygiene at a glance

| Situation                               | Do this                             |
|-----------------------------------------|-------------------------------------|
| Session idle >1h                        | Handoff → new session               |
| Switching to unrelated task             | Handoff → new session               |
| Context ~60%+ (see `/status-line`)      | Handoff → new session               |
| Want Opus for planning, Sonnet for code | Pick one and stick with it per      |
|                                         | session; don't `/model` toggle      |
| Edited `CLAUDE.md` mid-session          | Safe — takes effect on next restart |
| Large docs to reference                 | Put in `~/.claude/memory/` or a     |
|                                         | web-chat Project, not paste in turn |

Source of the mechanics: Nate Herk, "Give Me 10 Mins and I'll Save You
Millions of Claude Tokens" — https://www.youtube.com/watch?v=6cEQEba0i2A
