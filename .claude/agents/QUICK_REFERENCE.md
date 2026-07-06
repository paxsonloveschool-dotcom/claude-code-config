# Sub-Agent System — Quick Reference Card

> Concise guide for rapid lookup. Full details in README.md and DEPLOYMENT_GUIDE.md.

---

## One-Minute Overview

**Sub-agents** = specialized AI workers that parallel-execute focused tasks, each in isolation.

```
Parent (Orchestrator)
├─ Task A → Agent 1 (fast & cheap)
├─ Task B → Agent 2 (specialized)
├─ Task C → Agent 3 (isolated review)
└─ Synthesize results → Final output
```

**Benefit:** 7-10x token efficiency vs. sequential, fresh context for reviews, parallel execution.

---

## Agent Definitions at a Glance

| Agent | Use When | Model | Tools |
|-------|----------|-------|-------|
| **analyst** | Analyze logs, data, extract structure | Haiku | Readonly |
| **code-reviewer** | Deep code review, architecture | Sonnet | Readonly |
| **adversarial-verifier** | Test claims, find edge cases | Sonnet | Readonly |
| **content-writer** | Docs, blog posts, summaries | Haiku | Write/Edit/Read |

---

## YAML Template

```yaml
---
name: "agent-name"                    # kebab-case
description: "Use when [action]..."   # 1 sentence, specific
model: "claude-3-5-haiku"             # haiku|sonnet|opus
color: "blue"                         # UI indicator
memory: "none"                        # none|project|user|local
tools:
  - "readonly"                        # preset: all reads
# OR explicitly list: Read, Glob, Grep, Bash, Edit, Write
disallowed_tools:
  - "bash"
  - "edit"
---
```

---

## Instructions Template

```markdown
# Instructions
You are a [role]. Your mission is [goal].

## Core Objectives
1. [First priority]
2. [Second priority]

## Execution Steps
1. [How to start]
2. [Main task]
3. [Return results]

## Output Format
[JSON|Markdown|...] with fields [X, Y, Z]

## Constraints
[What NOT to do]
```

---

## Orchestration Patterns (Quick Decision Tree)

| Situation | Pattern | Parent Role |
|-----------|---------|-------------|
| 3+ independent tasks | **Parallel Analysis** | Delegate all at once; synthesize results |
| Task B needs Task A's output | **Sequential Refinement** | Run A → B → C in order |
| Need to verify a claim | **Verification Loop** | Delegate to adversarial-verifier; check verdict |
| Different review angles (security, perf, design) | **Review Panel** | Delegate to 3 agents in parallel; merge findings |
| Creating docs | **Documentation** | Analyst → Content-Writer → Code-Reviewer |
| 100+ items to triage | **Escalation/Triage** | Analyst finds all → Parent filters → Specialist deep-dive |

---

## Spawning an Agent (Code)

```javascript
const result = await Agent({
  description: "Use when [exact condition]",  // Must match agent's description
  prompt: "Your task...",
  
  // Optional:
  subagent_type: "general-purpose",          // Hint for fast matching
  model: "sonnet",                           // Override agent's default
  run_in_background: true,                   // For parallel execution
});
```

**Parallel Execution:**
```javascript
const [r1, r2, r3] = await Promise.all([
  Agent({ description: "...", prompt: "..." }),
  Agent({ description: "...", prompt: "..." }),
  Agent({ description: "...", prompt: "..." }),
]);
```

---

## File Locations

```
~/.claude/agents/                      # Global (all projects)
  ├── analyst.md
  ├── code-reviewer.md
  ├── adversarial-verifier.md
  ├── content-writer.md
  └── README.md

your-project/.claude/agents/          # Project-specific
  └── custom-agent.md
```

**Discovery:** Global agents always available; project agents shadow globals.

---

## Common Mistakes & Fixes

| Mistake | Fix |
|---------|-----|
| Agents talk to each other directly | Route everything through parent |
| No tool restrictions | Set `tools:` or `disallowed_tools:` explicitly |
| Verbose descriptions | Keep description to 1 action-oriented sentence |
| Using Opus for all sub-agents | Default Haiku; only upgrade for deep reasoning |
| Forgetting `memory: "none"` on one-off tasks | Add `memory: "none"` to save tokens |
| Both `tools` AND `disallowed_tools` specified | Use only ONE: whitelist OR blacklist |

---

## Token Efficiency Tips

1. **Batch independent work** → Use parallel execution (7-10x savings)
2. **Specify exact files/paths** → Don't dump entire codebases to agents
3. **Request structured output** → Use JSON if you'll parse results
4. **Set `memory: "none"`** → For one-off analyses
5. **Use right model tier** → Haiku for analysis, Sonnet for review, Opus for orchestration

---

## Deployment Checklist

- [ ] Agent file in `.claude/agents/` (global or project)
- [ ] YAML syntax valid (name, description, model, tools/disallowed_tools)
- [ ] Description is 1 sentence and unique
- [ ] Instructions section is clear (Core Objectives + Execution Steps + Output Format)
- [ ] Tool restrictions match agent capabilities
- [ ] Tested with real prompt in a session
- [ ] Committed to version control

---

## Troubleshooting at a Glance

| Problem | Diagnosis | Solution |
|---------|-----------|----------|
| Wrong agent triggered | Description too generic | Make description MORE specific |
| Agent not found | File not in agents/ directory | Move to `~/.claude/agents/` or `.claude/agents/` |
| Agent uses disallowed tool | Tool restriction too strict | Review `disallowed_tools` or add to `tools` whitelist |
| Token budget exceeded | Agent returns huge output | Add output constraints to agent definition |
| Agent makes mistakes | Ambiguous instructions | Add explicit constraints to agent definition |

---

## Output Formats (By Agent Type)

### Analyst
```json
{
  "summary": "Executive summary",
  "findings": [
    {
      "category": "Type",
      "severity": "critical|high|medium|low",
      "count": N,
      "examples": ["ex1", "ex2"],
      "recommendation": "Action"
    }
  ],
  "total_records_analyzed": N
}
```

### Code-Reviewer
```json
{
  "summary": "LGTM|Minor Issues|Blockers",
  "findings": [
    {
      "severity": "critical|high|medium|low",
      "category": "correctness|security|design|performance|simplification",
      "file": "path:lineN",
      "title": "Issue title",
      "description": "...",
      "recommendation": "..."
    }
  ],
  "praise": ["What was good"],
  "questions": ["Open questions"]
}
```

### Adversarial-Verifier
```json
{
  "claim": "The claim being tested",
  "verdict": "VERIFIED|PLAUSIBLE|REFUTED",
  "confidence": 0.0-1.0,
  "failure_modes_tested": [
    {
      "scenario": "Edge case",
      "code_location": "file:line",
      "handling": "How code handles it",
      "verdict": "handled|missing|incorrect"
    }
  ],
  "summary": "Judgment",
  "evidence": "Direct quote or reason"
}
```

### Content-Writer
```
Markdown file with:
- Proper heading hierarchy (#, ##, ###)
- Code blocks with language tags
- Tables, bullet lists, blockquotes
- Examples (tested)
- Links to source truth
```

---

## Links to Full Documentation

- **README.md** — System overview, architecture, common mistakes, deployment checklist
- **ORCHESTRATION_PATTERNS.md** — 6 patterns with code examples and decision tree
- **PARENT_ORCHESTRATOR_TEMPLATE.md** — Copy-paste templates for custom orchestrators
- **DEPLOYMENT_GUIDE.md** — Step-by-step setup, testing, monitoring, troubleshooting

---

## Examples

### Example: Parallel Code Audit (3 agents, no dependencies)
```javascript
const [security, performance, design] = await Promise.all([
  Agent({
    description: "Use when auditing code for security vulnerabilities",
    prompt: "Review src/auth.js for injection, auth, permission issues..."
  }),
  Agent({
    description: "Use when auditing code for performance issues",
    prompt: "Review src/api.js for N+1, inefficient loops, caching gaps..."
  }),
  Agent({
    description: "Use when auditing code for design and maintainability",
    prompt: "Review src/models.js for duplication, over-engineering..."
  })
]);

return { security, performance, design };
```

### Example: Sequential Analysis → Review (dependency)
```javascript
// Step 1: Analyze
const issues = await Agent({
  description: "Use when analyzing application logs for errors",
  prompt: "Read error.log and extract patterns..."
});

// Step 2: Review (uses Step 1 output)
const remediation = await Agent({
  description: "Use when providing remediation guidance for issues",
  prompt: `For these issues:\n${issues}\n\nProvide step-by-step fixes...`
});

return { issues, remediation };
```

### Example: Verification Loop (skeptical testing)
```javascript
const claim = "This code handles null inputs correctly";

const verdict = await Agent({
  description: "Use when testing claims about code edge cases",
  prompt: `Verify: "${claim}". Find all ways this could fail.`
});

if (verdict.verdict === "VERIFIED") {
  console.log("✅ Claim is solid");
} else {
  console.log("❌ Issues found; need revision");
}
```

---

**Version:** 1.0 | **Last Updated:** 2026-07-06 | **Category:** Reference
