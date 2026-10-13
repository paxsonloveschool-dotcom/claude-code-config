# Sub-Agent Deployment Guide

> Step-by-step instructions for deploying, testing, and managing your sub-agent system.

---

## Phase 1: Setup (One-Time)

### 1.1 Directory Structure
```
~/.claude/agents/                    # Global agents (all projects)
  ├── README.md                      # (this system overview)
  ├── analyst.md
  ├── code-reviewer.md
  ├── adversarial-verifier.md
  ├── content-writer.md
  ├── ORCHESTRATION_PATTERNS.md
  ├── PARENT_ORCHESTRATOR_TEMPLATE.md
  └── DEPLOYMENT_GUIDE.md            # (this file)

your-project/.claude/agents/         # Project-specific agents
  ├── README.md
  └── custom-agent.md
```

### 1.2 Verify Setup
```bash
# Check that agents are discoverable
ls -la ~/.claude/agents/
ls -la your-project/.claude/agents/

# Agents in both locations are available globally; project agents shadow global ones
```

---

## Phase 2: Creating a Custom Agent (Template)

### 2.1 Copy the Template
Choose a base agent (analyst, code-reviewer, etc.) and copy it:
```bash
cp ~/.claude/agents/analyst.md ~/.claude/agents/my-custom-agent.md
```

### 2.2 Edit the YAML Header
```markdown
---
name: "my-agent"                           # kebab-case, lowercase
description: "Use when you need to..."     # ONE sentence, action-oriented
model: "claude-3-5-haiku"                  # haiku|sonnet|opus based on complexity
color: "purple"                            # terminal UI indicator
memory: "none"                             # none|project|user|local
tools:                                     # whitelist approach
  - "readonly"                             # OR list explicitly: Read, Glob, Grep, Bash, Edit, Write
disallowed_tools:                          # blacklist (if using whitelist, omit this)
  - "bash"
  - "edit"
---
```

**YAML Rules:**
- ✅ `tools: ["readonly"]` = all read tools, no mutations
- ✅ `tools: ["Read", "Glob", "Grep", "bash"]` = specific tools only
- ❌ `tools: ["*"]` = don't use wildcards
- ❌ Both `tools` AND `disallowed_tools` = use one or the other, not both

### 2.3 Edit Instructions Section
```markdown
# Instructions
You are a [Role] specialist. Your mission is [specific goal].

## Core Objectives
1. [What this agent does first]
2. [What it does second]

## Execution Steps
1. [How it starts]
2. [Process for the main task]
3. [How it returns results]

## Output Format
[JSON? Markdown? Bullet list?]

## Constraints
[What it's NOT allowed to do]
```

### 2.4 Test the Agent
```bash
# In a test session, use the Agent tool:
Agent({
  description: "Use when you need to...",  # Must match your agent's description exactly
  prompt: "Here's the task...",
  # Claude will match your description against all agent definitions
  # If it matches your custom agent, it will be spawned
})
```

---

## Phase 3: Deploying in Your Project

### 3.1 Project-Level Agents
For agents used by your specific team on a specific project:

```bash
# Create project-level agents directory
mkdir -p your-project/.claude/agents/

# Copy agents you want customized for your project
cp ~/.claude/agents/analyst.md your-project/.claude/agents/project-analyzer.md

# Customize the copy
# (Don't modify global agents; keep them reusable)
```

### 3.2 Project CLAUDE.md Integration
Add sub-agent guidance to your project's CLAUDE.md:

```markdown
## Sub-Agents

This project uses specialized agents for parallel tasks:
- **project-analyzer**: Custom agent for analyzing [project-specific data]
- **code-reviewer**: Global agent, customized via prompts for [your standards]
- **security-auditor**: Custom agent focused on [your security model]

When delegating tasks, use Agent() with descriptions matching the agent definitions.

### Orchestration Guidelines
- Use Parallel pattern for log analysis + code review (independent)
- Use Sequential pattern for feature audit → design review → implementation
- Always delegate to adversarial-verifier before merging complex changes
```

### 3.3 Commit and Share
```bash
# Stage agent files
git add your-project/.claude/agents/*.md

# Commit with clear message
git commit -m "Add project-specific sub-agents for [purpose]"

# Push to team repo
git push origin your-branch
```

---

## Phase 4: Operating Sub-Agents

### 4.1 Triggering an Agent (Parent Orchestrator)

**Syntax:**
```javascript
Agent({
  description: "Use this agent when [exact trigger condition]",
  prompt: "Your task here...",
  // Optional overrides:
  subagent_type: "general-purpose",  // speeds up matching
  model: "sonnet",                   // override agent's model
  run_in_background: true,           // for parallel execution
})
```

**Description Matching:**
- Your `description` parameter is matched EXACTLY against agent definitions
- Keep descriptions specific and unique
- ✅ "Use this agent when you need to review code for design patterns"
- ❌ "Use for code review" (too generic, might not match)

### 4.2 Parallel Orchestration
```javascript
const [result1, result2, result3] = await Promise.all([
  Agent({
    description: "Use when analyzing logs for errors",
    prompt: "Read error.log and find patterns...",
    run_in_background: true,
  }),
  Agent({
    description: "Use for code review with architecture focus",
    prompt: "Review api.js for design issues...",
    run_in_background: true,
  }),
  Agent({
    description: "Use when testing claims about edge cases",
    prompt: "Verify pagination handles empty results...",
    run_in_background: true,
  }),
]);
```

### 4.3 Sequential Orchestration
```javascript
// Step 1: Analyze
const findings = await Agent({
  description: "Use when analyzing logs for errors",
  prompt: "Read error.log and find patterns...",
});

// Step 2: Escalate (use findings in next task)
const recommendations = await Agent({
  description: "Use when providing remediation guidance",
  prompt: `For these findings:\n${findings}\n\nProvide specific fixes...`,
});

// Return synthesized result
return { findings, recommendations };
```

---

## Phase 5: Monitoring & Maintenance

### 5.1 Agent Health Checks
```bash
# Verify YAML syntax in agent files
for f in ~/.claude/agents/*.md; do
  echo "Checking $f..."
  head -15 "$f" | grep -E "^(name|description|model|tools):"
done

# Look for common mistakes
grep -l "disallowed_tools.*tools:" ~/.claude/agents/*.md  # both specified
grep -l '```' ~/.claude/agents/*.md | head -5             # check formatting
```

### 5.2 Performance Tuning
If agents are running slower than expected:

1. **Check model assignment:**
   - Haiku for simple analysis? ✅
   - Sonnet for code review? ✅
   - Opus for orchestration only? ✅

2. **Check tool restrictions:**
   - Is agent waiting for permissions? (add to settings.json allowlist)
   - Is agent trying to use disallowed tools? (fix agent definition)

3. **Check description precision:**
   - Vague descriptions → longer matching time
   - Use specific, unique descriptions

### 5.3 Versioning
Keep a changelog when you update agents:

```markdown
# agent-name.md

## Version History

### v1.1 (2026-07-06)
- Added explicit null-check handling
- Upgraded to claude-3-5-sonnet
- Fixed output format to return JSON

### v1.0 (2026-07-01)
- Initial release
```

---

## Phase 6: Troubleshooting

### Issue: Agent Not Triggering
**Problem:** "Agent matched 'general-purpose' instead of my custom agent"

**Solutions:**
1. Check description precision: Make it MORE specific
   - ❌ "Use for analysis" (too generic)
   - ✅ "Use when you need to audit application logs for error patterns"

2. Verify file location:
   ```bash
   # Agent in wrong directory?
   find ~/.claude -name "*.md" -path "*/agents/*"
   ```

3. Check YAML syntax:
   ```bash
   # YAML parsing issues?
   head -20 ~/.claude/agents/your-agent.md | grep -E "^(---|name:|description:)"
   ```

### Issue: Agent Exceeds Token Budget
**Problem:** Sub-agent returns massive output, wastes context

**Solutions:**
1. Add output constraint to agent definition:
   ```markdown
   ## Output Format
   Always return:
   - Summary (max 100 words)
   - Top 5 findings (JSON array)
   - No raw data dumps
   ```

2. Adjust prompt to parent agent:
   ```javascript
   Agent({
     description: "...",
     prompt: "Analyze logs and return ONLY top 10 errors as JSON: [{severity, message, count}]",
   })
   ```

3. Check agent's `memory` setting:
   - Use `memory: "none"` for one-off analysis
   - Prevents agent from loading full session history

### Issue: Agent Makes Mistakes
**Problem:** Agent misunderstands task or produces incorrect output

**Solutions:**
1. Add guardrails in agent definition:
   ```markdown
   ## Constraints
   - Do NOT assume file exists; verify first with Glob
   - Do NOT return raw output; always structure as JSON
   - Do NOT modify code unless explicitly asked
   ```

2. Add verification loop to orchestrator:
   ```javascript
   const result = await Agent({...});
   
   // Verify before using
   if (!result.findings || result.findings.length === 0) {
     // Re-run with clarified prompt
   }
   ```

3. Escalate to higher model:
   ```javascript
   Agent({
     description: "...",
     prompt: "...",
     model: "opus",  // upgrade if Haiku/Sonnet not sufficient
   })
   ```

---

## Phase 7: Advanced Patterns

### 7.1 Custom Agent Inheritance
Create a base agent, then specialize:

```markdown
# Global: analyst.md
Generic analyzer for any data source

# Project: social-suite/analyst-instagram.md
Specialization: "Use when analyzing Instagram insights data"
Inherits most behavior from analyst.md but with Instagram-specific parsing
```

### 7.2 Agent Chains
Agents that call other agents:

```javascript
// Agent A: Analyzer
const data = await Agent({
  description: "Use for log analysis",
  prompt: "Analyze error.log...",
});

// Inside Agent A, you could delegate to Agent B:
// But this is NOT recommended; keep agents independent and let parent orchestrate

// Better: Parent orchestrates both
const [data, review] = await Promise.all([
  Agent({ description: "analyze logs" }),
  Agent({ description: "review analysis" })
]);
```

### 7.3 Agent with Memory (Recurring Context)
For agents that run repeatedly in the same session:

```markdown
---
memory: "project"  # Retain session context across invocations
---
```

Use when:
- Agent runs multiple times in same session
- Later invocations benefit from earlier context
- NOT appropriate for one-off analysis (wastes tokens)

---

## Rollout Checklist

Before deploying agents to your team:

- [ ] All YAML syntax is valid
- [ ] Descriptions are specific and unique
- [ ] Agent definitions are in `.claude/agents/`
- [ ] Tool restrictions match agent capabilities
- [ ] README.md documents all agents in the project
- [ ] Test agents in a real session (don't just validate syntax)
- [ ] Document custom orchestration patterns in project CLAUDE.md
- [ ] Commit agent definitions to version control
- [ ] Add links to agent docs in PR templates or contribution guides

---

## Support & Escalation

### For Quick Help
1. Check `agents/README.md` (overview)
2. Check `ORCHESTRATION_PATTERNS.md` (common patterns)
3. Review `PARENT_ORCHESTRATOR_TEMPLATE.md` (examples)

### For Custom Agents
1. Start with an existing agent template
2. Customize YAML + Instructions section
3. Test with real prompts in a session
4. Iterate based on results

### For Complex Workflows
1. Read ORCHESTRATION_PATTERNS.md (all 6 patterns)
2. Use PARENT_ORCHESTRATOR_TEMPLATE.md (examples)
3. Start simple (2-3 agents), then scale
4. Monitor token usage; adjust as needed

---

**Version:** 1.0 | **Last Updated:** 2026-07-06 | **Status:** Production Ready
