---
name: jarvis-agent-roster
description: Defines the 9 JARVIS business agents for Paxson Berkey's operations — roles, missions, domain ownership, and routing. Reference when deciding which agent should own a task or when delegating work.
---

# JARVIS Agent Roster

Paxson Berkey's business operations: **HP Landscaping** (Higher Purpose Landscaping LLC) and **Restore Marketing Co**.

---

## Agent Definitions

| Agent | Role | Owns |
|---|---|---|
| `personal` | Personal Assistant | Personal calendar, emails, to-dos, reminders, daily life |
| `ceo` | Chief Executive Advisor | Business strategy, cross-company decisions, executive briefings |
| `cfo` | Chief Financial Officer | Revenue, expenses, QuickBooks, cash flow, pricing, financial analysis |
| `sales` | Sales Manager | Lead pipeline, GHL contacts, follow-ups, proposals, deal closure |
| `marketing` | Marketing Manager | Restore Marketing campaigns, GHL CRM marketing flows, lead gen |
| `operations` | Operations Manager | HP Landscaping crew scheduling, job dispatch, weather, equipment |
| `hr` | HR Manager | Hiring, onboarding, employee relations, payroll coordination, HR policies |
| `admin` | Administrative Manager | Documents, contracts, invoices, compliance, vendor relationships, filing |
| `social` | Social Media Manager | Content creation and scheduling across Instagram, Facebook, LinkedIn, TikTok |

---

## Mission Statements

### personal
Manage Paxson's personal calendar, emails, to-dos, reminders, and daily life coordination.

### ceo
Drive high-level business strategy, synthesize cross-company insights, and support executive decisions for HP Landscaping and Restore Marketing.

### cfo
Track revenue, expenses, cash flow, and QuickBooks data; provide financial analysis and pricing recommendations. Alert on cash flow issues.

### sales
Manage the lead pipeline for both businesses. Own GHL contacts, follow-up sequences, proposals, and closing. Drive revenue.

### marketing
Execute Restore Marketing client campaigns, manage GHL CRM marketing automations, and generate qualified leads for both businesses.

### operations
Coordinate HP Landscaping crew scheduling, daily job dispatch, weather impact assessment, equipment tracking, and client job updates.

### hr
Manage all hiring funnels, employee onboarding, HR policies, payroll coordination, and performance issues.

### admin
Handle contracts, invoices, vendor communications, compliance requirements, business filing, and document management.

### social
Create and schedule social media content for HP Landscaping and Restore Marketing. Manage content calendars across all platforms.

---

## Routing Guide

When deciding which agent should own a task, match the primary objective:

- **Revenue / deals / leads** → `sales`
- **Campaigns / ads / content strategy** → `marketing`
- **Social posts / captions / scheduling** → `social`
- **Crew / jobs / scheduling / weather** → `operations`
- **Money / QuickBooks / margins** → `cfo`
- **Strategy / cross-business decisions** → `ceo`
- **Contracts / invoices / documents** → `admin`
- **People / hiring / HR** → `hr`
- **Everything personal** → `personal`

If a task spans multiple domains, route to the agent that owns the *outcome*, not the process. Outcomes:
- Close a deal → `sales` (even if it needs a proposal from `admin`)
- Grow revenue → `ceo` or `sales` depending on whether it's strategic or tactical
- Build a campaign → `marketing` (with `social` as sub-task owner for content)

---

## PaxBot Integration

PaxBot is running at `C:\Users\highe\paxbot\`. To route a task to a specific agent directly:

```bash
# From Claude Code — trigger a PaxBot agent directly via bot.py logic
# Or call the orchestrator handle() method targeting an agent
```

The orchestrator at `C:\Users\highe\paxbot\orchestrator.py` routes Telegram messages automatically. For Claude Code → PaxBot delegation, create a task in the shared registry with the appropriate `owner` field set to the agent name. PaxBot will pick it up.

---

## Proactive Schedules

| Time | Agent | Task |
|---|---|---|
| 7:00 AM daily | `ceo` | Morning briefing — email digest + calendar + active tasks |
| 2:00 PM daily | `sales` | Lead pipeline check — follow-ups due, GHL status |
| 5:00 PM Mon-Fri | `operations` | Daily wrap-up — jobs completed, crew status, tomorrow's schedule |
