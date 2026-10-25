# Orchestration Patterns: Parent Agent Strategy Guide

> How to break down complex tasks and coordinate sub-agents for maximum efficiency.

## Core Principle
**The parent is the conductor.** It decides what work to delegate, when, and in what order. Sub-agents execute in isolation and return results back to the parent for synthesis.

```
Parent (Orchestrator)
├─ Delegates Task A to Sub-Agent-1
├─ Delegates Task B to Sub-Agent-2
├─ Waits for results
└─ Synthesizes findings into final output
```

---

## Pattern 1: Parallel Analysis (No Dependencies)

**When to use:** Multiple independent analyses that can happen simultaneously.
- Audit logs for errors (Analyst)
- Review code style (Code-Reviewer)
- Test claim about edge cases (Adversarial-Verifier)

**Parent role:**
1. Delegate all three tasks to respective agents simultaneously (use parallel `Agent()` calls)
2. Wait for all results
3. Merge findings into a single prioritized report

**Code sketch:**
```javascript
// Parent orchestrator
const [logs_audit, code_review, edge_case_verdict] = await Promise.all([
  Agent({
    description: "Analyze logs for error patterns",
    prompt: "Read logs/error.log and extract...",
    run_in_background: true,
  }),
  Agent({
    description: "Review code changes for design issues",
    prompt: "Review the diff in src/api.js...",
    run_in_background: true,
  }),
  Agent({
    description: "Test the claim that pagination handles edge cases",
    prompt: "Verify that pagination.js correctly handles empty results...",
    run_in_background: true,
  }),
]);

// Merge results
return synthesize({
  logs: logs_audit,
  code: code_review,
  verification: edge_case_verdict,
});
```

**Benefits:**
- All tasks run concurrently (wall-clock time = slowest task)
- Token efficiency: parallel execution uses ~7-10x fewer tokens than sequential

---

## Pattern 2: Sequential Refinement (Dependency Chain)

**When to use:** Each step builds on the previous result.
1. Analyst finds anomalies
2. Code-Reviewer explains the root cause
3. Parent decides on fix

**Parent role:**
1. Run Analyst first
2. Pass Analyst findings to Code-Reviewer
3. Synthesize final recommendation

**Code sketch:**
```javascript
// Step 1: Analyze
const anomalies = await Agent({
  description: "Find anomalies in deployment logs",
  prompt: "Review deploy.log and find unusual patterns...",
});

// Step 2: Explain (using Step 1 output)
const explanation = await Agent({
  description: "Explain why these anomalies occurred",
  prompt: `Given these anomalies:\n${anomalies}\n\nExamine the source code to explain...`,
});

// Step 3: Parent synthesizes
return {
  anomalies,
  explanation,
  recommendation: "Based on both findings, we should...",
};
```

**Benefits:**
- Each agent has fresh context (no contamination)
- Results feed into the next step naturally
- Parent stays in control of flow

---

## Pattern 3: Verification Loop (Skeptical Review)

**When to use:** You want to verify a claim or test a solution before committing.
1. You propose a solution
2. Adversarial-Verifier tests it
3. If REFUTED, return to drafting; if VERIFIED, proceed

**Parent role:**
1. Propose solution/claim
2. Delegate to Adversarial-Verifier
3. Check verdict: VERIFIED → proceed, REFUTED → debug

**Code sketch:**
```javascript
// Parent has written a solution
const solution = "My code now correctly handles null input by checking !== null";

// Verify
const verdict = await Agent({
  description: "Test the claim about null handling in code",
  prompt: `Verify this claim: "${solution}". Find all ways it could fail.`,
});

if (verdict.verdict === "VERIFIED") {
  console.log("✅ Solution is solid, proceed");
  return true;
} else {
  console.log("❌ Issues found, need to revise");
  return false;
}
```

**Benefits:**
- Catches bugs before they get to production
- Fresh perspective (agent isn't invested in solution)
- Automated safety check

---

## Pattern 4: Parallel Review Panel (Multiple Lenses)

**When to use:** Complex decision that benefits from diverse perspectives.
- One reviewer focuses on security
- One focuses on performance
- One focuses on maintainability

**Parent role:**
1. Break down review criteria
2. Delegate to 2-3 agents in parallel, each with different lens
3. Aggregate findings

**Code sketch:**
```javascript
const [security_audit, perf_audit, design_audit] = await Promise.all([
  Agent({
    description: "Audit code for security vulnerabilities",
    prompt: "Review src/auth.js for auth/permission issues, SQL injection, etc.",
  }),
  Agent({
    description: "Audit code for performance issues",
    prompt: "Review src/api.js for N+1 queries, inefficient loops, etc.",
  }),
  Agent({
    description: "Audit code for design and maintainability",
    prompt: "Review src/models.js for code smell, over-engineering, etc.",
  }),
]);

return {
  security: security_audit,
  performance: perf_audit,
  design: design_audit,
};
```

**Benefits:**
- Catches issues each specialist might miss
- Parallel execution = faster than serial reviews
- Each agent is focused, not overwhelmed

---

## Pattern 5: Documentation Generation

**When to use:** Creating or updating docs (README, API reference, tutorials).
1. Analyst extracts structure from code
2. Content-Writer drafts documentation
3. Code-Reviewer fact-checks the docs
4. Parent merges final version

**Parent role:**
1. Delegate extraction to Analyst
2. Delegate writing to Content-Writer
3. Delegate fact-check to Code-Reviewer
4. Synthesize feedback and finalize

**Code sketch:**
```javascript
// Step 1: Extract API structure
const api_structure = await Agent({
  description: "Extract API endpoints and their signatures",
  prompt: "Read src/routes/*.js and list all endpoints with parameters...",
});

// Step 2: Draft docs
const draft = await Agent({
  description: "Generate API documentation",
  prompt: `Using this structure:\n${api_structure}\n\nGenerate a README for the API.`,
});

// Step 3: Fact-check
const review = await Agent({
  description: "Verify API docs match actual code",
  prompt: `Review this draft against the actual code. Is it accurate?\n${draft}`,
});

return {
  draft,
  review,
  final: "Merge feedback into final docs",
};
```

**Benefits:**
- Automation reduces doc maintenance burden
- Each step adds value (structure → draft → verification)
- Docs stay in sync with code

---

## Pattern 6: Escalation / Triage

**When to use:** Filter large datasets or results, then escalate for deeper analysis.
1. Analyst finds issues (100 items)
2. Parent filters to top 5 by severity
3. Code-Reviewer does deep dive on top 5

**Parent role:**
1. Run Analyst (broad sweep)
2. Triage results by severity/impact
3. Escalate top-N items to specialist review

**Code sketch:**
```javascript
// Step 1: Broad sweep
const issues = await Agent({
  description: "Find all code issues in the codebase",
  prompt: "Audit src/ for dead code, unused imports, console.logs, etc.",
});

// Step 2: Triage (parent logic)
const critical = issues.findings
  .filter(f => f.severity === "critical")
  .slice(0, 5);

// Step 3: Deep review on critical items
const deep_review = await Agent({
  description: "Provide detailed remediation guidance for code issues",
  prompt: `For these critical issues:\n${JSON.stringify(critical)}\n\nProvide step-by-step fix instructions...`,
});

return {
  all_issues: issues,
  critical,
  deep_review,
};
```

**Benefits:**
- Filters out noise early
- Focuses expensive (Sonnet/Opus) agents on high-impact work
- Keeps context manageable

---

## Anti-Patterns to Avoid

### ❌ Cross-Agent Communication
```javascript
// WRONG: Agent-1 talks to Agent-2
Agent-1 → (result) → Agent-2
          └─ (direct)

// RIGHT: All results flow through parent
Agent-1 ─────┐
             ├─→ Parent ←─┐
Agent-2 ─────┘            │
                    Parent synthesizes
```

### ❌ Mixing Roles
```javascript
// WRONG: One agent does 5 unrelated things
Agent: "Analyze logs AND review code AND test claims AND write docs"

// RIGHT: Delegate to specialists
Analyst → logs
Code-Reviewer → code
Adversarial-Verifier → claims
Content-Writer → docs
```

### ❌ Agents with Unlimited Tools
```javascript
// WRONG: Sub-agent can do anything
disallowed_tools: []

// RIGHT: Explicit boundaries
disallowed_tools: ["bash", "edit"]  # read-only analyst
```

### ❌ No Verification
```javascript
// WRONG: Parent trusts agent output blindly
result = Agent(prompt)
return result  # No verification!

// RIGHT: Parent verifies and synthesizes
result = Agent(prompt)
if (result.error) { handle_error() }
synthesized = merge_with_other_results(result)
return synthesized
```

---

## Decision Tree: Which Pattern?

```
START
  │
  ├─ Are the tasks independent? (no shared context)
  │  YES → Pattern 1: Parallel Analysis
  │  NO  ↓
  │
  ├─ Does Task B depend on Task A's output?
  │  YES → Pattern 2: Sequential Refinement
  │  NO  ↓
  │
  ├─ Do you need to verify a claim?
  │  YES → Pattern 3: Verification Loop
  │  NO  ↓
  │
  ├─ Are there 3+ different review angles?
  │  YES → Pattern 4: Review Panel
  │  NO  ↓
  │
  ├─ Is this about docs/content generation?
  │  YES → Pattern 5: Documentation
  │  NO  ↓
  │
  ├─ Are there 100+ items to triage?
  │  YES → Pattern 6: Escalation/Triage
  │  NO  ↓
  │
  └─ Pattern 2: Sequential Refinement (default)
```

---

## Checklist: Before Delegating

- [ ] Is the task well-defined and unambiguous?
- [ ] Does the agent description match the actual task?
- [ ] Have I provided enough context (file paths, code snippets, examples)?
- [ ] Am I expecting structured output (JSON) or prose?
- [ ] Should the agent have `memory: "none"` (one-off) or `memory: "project"` (ongoing)?
- [ ] Are the tool restrictions appropriate for the task?
- [ ] Can the parent synthesize/verify the results?

---

## Token Efficiency Tips

1. **Batch independent tasks:** Use `run_in_background: true` for parallel execution
2. **Clear context:** Provide exact file paths, line numbers, not entire codebases
3. **Structured output:** Request JSON when results will be synthesized
4. **One-off vs. recurring:** Set `memory: "none"` for one-off analyses
5. **Model choice:** Use Haiku for analysis, Sonnet for review, Opus only for orchestration

---

## Example: Full End-to-End Workflow

**Task:** "Refactor the authentication module and ensure it's correct and secure."

```javascript
// STEP 1: Analyze current state
const analysis = await Agent({
  description: "Analyze authentication module for structure and issues",
  prompt: "Read src/auth/index.js and identify complexity areas...",
});

// STEP 2: Plan refactor (parent + context)
const plan = {
  current_issues: analysis.issues,
  target_structure: "Move auth logic to separate classes",
  timeline: "2 hours",
};

// STEP 3: Review refactor approach (parallel)
const [security_check, design_check] = await Promise.all([
  Agent({
    description: "Audit authentication refactor for security risks",
    prompt: `Refactor plan: ${JSON.stringify(plan)}. Identify security holes...`,
  }),
  Agent({
    description: "Review authentication refactor design",
    prompt: `Refactor plan: ${JSON.stringify(plan)}. Is this maintainable?...`,
  }),
]);

// STEP 4: Refactor (parent writes code)
// [Parent edits files using Edit tool]

// STEP 5: Verify refactor
const verification = await Agent({
  description: "Verify authentication refactor handles edge cases",
  prompt: "Test null inputs, invalid tokens, concurrent requests...",
});

// STEP 6: Synthesize
return {
  plan,
  pre_refactor_analysis: analysis,
  design_review: design_check,
  security_review: security_check,
  post_refactor_verdict: verification,
  status: verification.verdict === "VERIFIED" ? "READY TO COMMIT" : "NEEDS REVISION",
};
```

---

**Version:** 1.0 | **Last Updated:** 2026-07-06 | **Used by:** Parent orchestrators
