# Postiz Project — Session Resume Note

> Saved 2026-06-17. Pick up here next session.

## Where we are
Built a complete free, self-hostable social-media content-automation system
under `postiz/`. **All code is committed + pushed.**

- **PR #16 — MERGED** into `main`: full Postiz deploy (docker-compose + Caddy
  auto-HTTPS), free Oracle Cloud path (cloud-init self-install + DuckDNS),
  setup.sh, Makefile, GO_LIVE.md runbook, content-automation kit
  (plan_calendar.py + schedule_posts.py), 40 ready captions for HP Landscaping
  + Restore (general + winter), and a phone-triggerable GitHub Action.
- **PR #17 — OPEN (draft)** on branch `claude/postiz-channel-labels`:
  friendly channel-label system (`channels.json`) so posts target one business
  and never leak to the other. Verified isolation + fail-safe. **Decision
  pending: merge it or leave draft.**

## The open decision (this is what to resume on)
User does NOT want to put a credit card into Oracle. We compared no-card paths:
1. **Free app (Buffer/Metricool)** — no card, no server, no code; monthly limits.
   User leaned here, wanted more explanation (given).
2. **Own computer + Cloudflare Tunnel** — no card, owned, but device must stay on.
3. **Oracle + virtual card** — explained the card is an anti-bot ID check (not a
   charge); Oracle never bills Always Free; safest via a Privacy.com/bank
   **virtual card locked at $1**. User was asking how the card is safe.

**Last thing discussed:** why Oracle needs a card and how to make it risk-free
with a virtual card. Awaiting user's pick between: (a) set up a virtual card +
do Oracle, or (b) go with a free app (no card) and I walk them through signup.

## Next action when user returns
Ask which path they chose. Then either:
- Free app → walk through Buffer/Metricool signup + connect accounts + schedule
  (need to know: does each business have Instagram, Facebook, or both?).
- Oracle → walk through virtual card, then GO_LIVE.md Phases 1–2.

## Key facts to remember
- Businesses: **HP Landscaping** (lawn care) + **Restore** (damage restoration).
- Instagram/Facebook posting needs a free IG Business account + Meta App Review
  (few-day wait); X/LinkedIn/Bluesky connect instantly.
- The 40 captions work in ANY tool (self-hosted or free SaaS) — copy/paste.
- Everything is free; only Oracle asks for a card (ID check, not payment).
