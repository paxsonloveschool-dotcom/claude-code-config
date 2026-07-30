---
name: prompt-composer
description: >
  Compose a single structured, one-shot prompt that gets the task done in
  one turn instead of 3–4 iterative back-and-forths. Use when the user is
  about to fire off a request they'll obviously have to correct twice
  (missing format, missing constraints, missing acceptance criteria), or
  says "help me write a good prompt", "how should I phrase this",
  "batch these questions", or is drafting a request >2 sentences long
  without stating output shape.
  Iteration is where credits die — three iterations on a 30-turn thread
  cost more than the original ask times ten because the whole history
  re-ships each turn.
  Triggers: "help me write a prompt", "how should I ask", "batch this",
  "compose a prompt", "make this one shot", "prompt template",
  "one-shot this".
---

# prompt-composer — One-Shot Prompt Template

## Why

Every turn re-ships the full thread. A 50-turn chat costs ~10x per message
vs a fresh thread — because the model re-reads everything each request.
Every follow-up ("actually make it shorter", "use bullets instead") is
another full-thread re-read. Front-load the spec.

## The template

Fill this in, send once, don't iterate:

```
TASK
<one sentence: what you want done>

CONTEXT
<2–5 bullets of background the model can't infer>
- <constraint or fact>
- <constraint or fact>

INPUTS
<paste the code/text/data, or list the files to read>

OUTPUT SHAPE
- format: <markdown | JSON | code | plain>
- length: <e.g. "under 200 words", "one function", "3 bullets max">
- tone: <e.g. "terse technical", "explain to a beginner", "no fluff">
- structure: <e.g. "sections: Diagnosis / Fix / Test", or "just the diff">

CONSTRAINTS
- <hard rule, e.g. "don't touch other files">
- <hard rule, e.g. "match existing code style">
- <hard rule, e.g. "no comments unless the why is non-obvious">

ACCEPTANCE
- <what "done" looks like — e.g. "tests pass", "renders in dark mode">
- <how you'll verify — e.g. "I'll run pytest", "screenshot me the result">

OUT-OF-SCOPE
- <what to explicitly NOT do — e.g. "don't refactor unrelated code">
```

## Rules of thumb

- **Batch related questions.** If you have 4 questions about the same
  system, ask all 4 in one message. Each separate prompt re-ships the
  entire history — 4 prompts on a 40-turn thread = 4x40 turns of context
  billed, versus 1x40.
- **State the output shape first, not last.** "Give me X in the form Y"
  beats "give me X" followed by "actually make it Y".
- **Paste inputs, don't describe them.** "Fix the bug in
  `src/foo.py:42`" (with the file already in context) beats "there's a
  bug somewhere in foo".
- **Say what NOT to do.** "Don't add comments, don't refactor other
  code" is worth 5 prompts you won't need to send.
- **If it fits in one turn, put it in one turn.** Even a 500-line prompt
  is one turn's context; three 100-line prompts is three turns growing.

## When NOT to use

- Genuine exploration ("what do you think about X?") — iteration IS the
  point.
- Learning something new — back-and-forth Q&A is fine when short.
- Two-turn "clarify then execute" flows — that's not the same as
  iterating on output shape.

## Complementary skills

- **session-handoff** — when the thread hits ~60% or the task shifts.
- **agent-reach / cookie-guardian** — pull data cheaply once, feed it
  into the batched prompt.
