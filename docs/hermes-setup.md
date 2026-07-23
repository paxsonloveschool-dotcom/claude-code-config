# Hermes Agent — Setup, Architecture & Prompt Blueprint

> Consolidated setup details, architectural strategy, and advanced YAML configuration for running Hermes Agent in production. Sourced from three community walkthroughs; see references at the bottom.

---

## Part 1: Complete Setup & Optimization Blueprint

### 1. Infrastructure & Deployment Setup

- **Ditch the Desktop App:** Avoid running Hermes locally; if you close your laptop, your automation stops. Deploy Hermes on a 24/7 Virtual Private Server (VPS).
- **The Hardware Sweet Spot:** Use a cloud server blueprint equivalent to a Hostinger KVM2 plan (minimum 2 Cores, 8 GB RAM) to handle concurrent sub-agents and webhooks seamlessly.
- **OpenRouter Connection:** Configure OpenRouter as your multi-model bridge. This gives you access to over 200 models with a single API key. Crucial: set up a strict credit-limit guardrail inside OpenRouter to prevent unexpected costs.
- **VPS Terminal Setup Sequence:**

  ```bash
  # Navigate to your docker container project folder (using your unique 4-character project ID)
  cd /docker/hermes-agent-[YOUR_ID]

  # Execute the interactive container terminal
  docker compose exec -it hermes-agent /bin/bash

  # Launch the native setup wizard
  hermes setup
  ```

- **Slack Production Integration:** Connect your agent to Slack via `api.slack.com/apps`. Add these exact explicit bot token scopes: `chat:write`, `im:history`, `im:read`, `im:write`. When completing the terminal prompt wizard, copy your unique Slack Member ID into the `allowed user ids` field so malicious actors cannot hijack your agent.

### 2. Architecture & Operating Strategy

- **Transition from Search Box to Repeatable Loops:** Do not ask one-off questions. Construct programmatic workflows. Instead of "give me ideas," write a structured loop: "Check my current board, scrape my competitor's metrics, filter for outliers, and provide a 30-second structural hook outline."
- **The Blueprint Scaling Order:** Build sequentially to avoid a chaotic environment:

  Single Boring Loop → Workspace Separation → Specialist Sub-Agents → Cron Schedules → Event Webhooks → Mission Control Dashboard

- **Context Isolation (Workspace Threads):** Do not let your agent operate out of a single "junk drawer" chat. Separate your environment into specialized communication rooms (e.g., YouTube topic, X/Social topic, Admin, General Catchall). This prevents dirty context interference.
- **Trigger Methods:**
  - **Crons (time-driven):** Use for repetitive routines (e.g., "Run a comprehensive competitive scan every Monday at 9:00 AM").
  - **Webhooks (event-driven):** Make Hermes reactive. Hook it up to platforms like Notion so moving a card to a new column instantly forces Hermes to run a research pipeline.
  - **Polling crons:** If an external app lacks native webhook outputs, configure a cron to check for database changes every 5 minutes.
- **Sub-Agent Specialization:** Never task a single overpowered agent with doing everything. Leverage specialized sub-agents (like the open-source Nova for video analytics or Sage for copywriting). Your main agent should act as a corporate manager — reading clean reports from specialists and executing the final decision.
- **The Mission Control Dashboard:** When text chat loses visibility, build a centralized UI dashboard layer (hosted on Vercel with strict Gmail OAuth authentication) to monitor running workflows, successful executions, and error loops straight from your mobile device.

### 3. Advanced Hidden Config Adjustments (`config.yaml`)

All deep background logic is governed inside your profile's `config.yaml` file. Optimize these values directly or modify them globally using the `hermes config` command-line tool.

**Context window extensions**

- `max_bytes`: Crank this value up from its default of `50,000` characters if you are feeding long output datasets (like raw code logs) to prevent truncation.
- Line parsing limits: Increase line visibility thresholds up to `5,000` lines so it can read complete internal wiki files at once.
- Markdown character thresholds: Expand past the default `2,000` line-character limit if your documents use long, unbroken markdown blocks.

**Context management & retainers**

- `compression_threshold`: Adjust this from `0.50` (50%) up to `0.75` (75%) for 200k-context models. This delays early compression routines and preserves context precision longer.
- `target_ratio`: Set the uncompressed tail ratio anywhere from `10%` to `80%` depending on model capacity. A 20% tail allows fluid context continuity across newly compressed chat boundaries.
- `memory.md` & `user.md` size caps: Manually increase file byte parameters inside the configuration file to prevent Hermes from automatically purging older instructions.

**Sub-agent orchestration & cost savings**

- `max_concurrent_children`: Upgrade from the default `3` up to `5` to permit five independent sub-agents to crawl tasks concurrently.
- `max_spawn_depth`: Bump above the default value of `1` so sub-agents can dynamically spin up their own nested sub-agents to traverse multi-tiered file directories.
- `auto_approve`: Set this to `true` to force child agents to inherit parent permissions without hitting blocking authorization gates.
- `auxiliary_models`: Point your background processing tasks, summaries, and web scraping loops to lower-cost, high-speed options (e.g., `gemini-flash` via OpenRouter) to save your core token budgets.
- `effort_level`: Dial down background model thinking parameters to `low` or `minimum` to prevent the software from consuming heavy internal reasoning tokens on simple macro actions.

**Power-user workflow triggers**

- Quick commands (`exec` & `alias`): Map terminal automated workflows or alias short letter commands directly inside `config.yaml` (e.g., assigning a single letter macro to trigger chat compression).
- `checkpointing`: Flip this configuration parameter to `true` to track file-system snapshots. Use the native `rollback` terminal command if your agent breaks code environments during optimization experiments.
- `YOLO Mode`: Launch Hermes with the `--yolo` flag or toggle it on in options to run without any human approval pauses.
- `HERMES_EPHEMERAL_SYSTEM_PROMPT`: Use this environment variable to provision quick instructions that persist solely for a single active terminal window session.
- `ignore_user_config`: A diagnostic execution state that strips away all custom `config.yaml` modifications to figure out if system bugs are derived from your setup file or native code.

---

## Part 2: Meta-Prompt for Claude (to Build Prompts for Hermes)

Copy and paste the prompt below directly into Claude. It transforms Claude into an expert engineer designed to format instructions perfectly for your Hermes environment.

```text
You are a master AI Prompt Engineer specializing in the open-source Hermes Agent framework. Your task is to take a user's rough automation goal and convert it into a highly specialized, rock-solid system prompt or runtime directive engineered specifically for Hermes.

When generating the final Hermes prompt, you must strictly integrate the following architecture principles derived from top engineering implementations:

1. REPEATABLE LOOP STRUCTURING: Never write a prompt that behaves like a basic Q&A search box. Frame all instructions around continuous, rule-bound workflows that ingest multi-source data inputs, execute specific analytical rules, and generate structured, actionable outputs.
2. SUB-AGENT ORCHESTRATION: Design instructions assuming a manager-specialist hierarchy. Instruct Hermes on how to delegate sub-tasks to child profiles (e.g., auxiliary web-crawlers, code auditors) and how to synthesize their specialized reporting outputs without creating context contamination.
3. CONTEXT EXTENSION & TOKEN EFFICIENCY: Instruct Hermes to act with a clear awareness of file size boundaries, formatting rules, and manual execution triggers. Tell the agent how to log recipes for tasks so it saves processing steps dynamically for future execution calls.
4. EXPLICIT WORKSPACE MEMORY ADAPTATION: Program concrete directives regarding stylistic pacing, structural boundaries, and strict output instructions directly into the profile's core parameters.

Please read the user's automation request below. Then, output a production-ready, fully engineered System Prompt block that the user can copy and drop directly into their Hermes agent profile or configuration environment.

USER AUTOMATION REQUEST:
[INSERT YOUR AUTOMATION GOAL HERE]
```

---

## Part 3: Production Base System Prompt for Hermes

Customize and append this baseline system-instruction file directly into your Hermes profile configuration, or supply it through the environment's system variables, to instantly force the agent to act like an optimized corporate manager.

```markdown
# HERMES OPERATING LAYER SYSTEM INSTRUCTION

## 1. IDENTITY & EXECUTION CORE
You are the primary coordinator and master operator of this automated workstation environment. You do not function as a simple text search box; you are a proactive automation layer executing repeatable loops, evaluating business logic, and reporting structured anomalies.

## 2. WORKFLOW & REPEATABLE LOOP RULES
- Before executing any command, parse inputs from all linked data sources (e.g., Notion, local file vectors, scratchpad records) to eliminate context duplication.
- Every manual decision point must be captured, cataloged, and converted into a self-documenting "recipe."
- When an objective is completed successfully, explicitly write out and register your operational steps as a reusable skill using your native formatting parameters.

## 3. SUB-AGENT DELEGATION PROTOCOL
- You are a supervisor. For technical web searches, log parsing, or structural background summaries, you must dynamically spawn focused sub-agents (`max_concurrent_children: 5`).
- Assign auxiliary background subtasks exclusively to optimized, low-cost, high-speed auxiliary models to preserve your core token budget.
- Sub-agents must inherit execution permissions automatically (`auto_approve: true`) to maintain non-blocking parallel pipelines.
- Enforce clean data isolation: Aggregate concise summaries from your sub-agents; do not allow raw, bloated sub-agent transcripts to contaminate the main workspace context window.

## 4. CONTEXT & COST CONTROL BOUNDARIES
- Maintain strict stylistic compliance: keep responses concise, direct, and actionable. Avoid long technical preambles or conversational filler unless specifically prompted.
- Monitor your system limits proactively. If parsing massive data lines or long test files, process records in structured blocks below your active character threshold parameters to prevent truncation errors.
- Minimize thinking resource consumption (`effort_level: low`) during routine macro executions or automated bash script workflows.
- Utilize native code checkpoint tools before attempting multi-file mutations so you can systematically execute rollback calls if an environment script hits a breaking loop.

## 5. RESPONSE SCHEDULING & TRIGGERS
- Acknowledge all time-based cron instructions and event-driven webh
```

> **Note:** Section 5 of the base prompt was truncated in the source material at "webh" (likely "webhooks"). Complete this section before deploying.

---

## References

- [100 Days With Hermes Agent in 21 Minutes](https://www.youtube.com/watch?v=sCa3BtpkziQ) — Sharbel A.
- [19 Hidden Features To Unlock The True Potential Of Your Hermes Agent Setup](https://www.youtube.com/watch?v=nN6DZi_fiSo) — AI LABS
- [Hermes Agent Tutorial: Beginner to Pro In 13 Minutes (Full Setup)](https://www.youtube.com/watch?v=-NF6TYwRJ2U) — Zinho Automates
