# Go-Live Runbook — HP Landscaping

The exact, in-order steps to take this from code to live. Reflects the chosen setup:
**Facebook + Instagram only, no Twilio, alerts by email (Resend) + free phone push (ntfy).**

Most of this is one ~1-hour session together. Steps marked **(you)** need your login;
**(me)** I do or walk you through live.

---

## 0. Accounts to create first (all free)

- [ ] **Cloudflare** account — https://dash.cloudflare.com/sign-up (hosting)
- [ ] **Facebook Developer** access — https://developers.facebook.com (your FB login)
- [ ] **Resend** account — https://resend.com (email alerts)
- [ ] **ntfy** app installed + subscribed to your alert channel (phone push)

You already have the ntfy channel: `hp-landscaping-alerts-0952f31e13`
(URL: `https://ntfy.sh/hp-landscaping-alerts-0952f31e13`)

---

## 1. Fill in the brain (no accounts needed) — **(you give me the info, me to wire)**

In `src/knowledge.ts`, under the HP Landscaping profile:
- [ ] **services**, **hours**, **service area**
- [ ] **faq** — common questions + your answers (5–10 is plenty)
- [ ] **escalateWhen** — defaults already cover pricing/quotes/complaints/scheduling
- [ ] **styleExamples** — 3–6 real message→reply pairs in your voice (optional, ideal)
- [ ] **crossSell** — sister companies + trigger phrases (Restore is pre-filled)
- [ ] Replace the `REPLACE_WITH_PAGE_ID` key with your real Facebook Page ID (step 3)

> Public FAQ/hours/services are fine to commit. **Personal contact info (cell, email)
> and tokens are NOT** — those go in Cloudflare secrets (step 4), never in the code.

---

## 2. Deploy to Cloudflare — **(me, with your approval)**

Click-based path (no terminal):
- [ ] Connect this GitHub repo to Cloudflare Workers
- [ ] Create a KV namespace named `STATE`; put its id in `wrangler.toml`
- [ ] First deploy → you get a URL like `https://social-ai-responder.<you>.workers.dev`

---

## 3. Connect Facebook + Instagram — **(you log in, me to configure)**

- [ ] Create a Facebook app (Business type) at developers.facebook.com
- [ ] Add products: **Messenger**, **Instagram**, **Webhooks**
- [ ] Connect your Page; link the Instagram **professional/business** account
- [ ] Generate a long-lived **Page Access Token** (permissions below)
- [ ] Copy your **Page ID** into `knowledge.ts` (step 1)
- [ ] In Webhooks, set callback `https://<your-worker-url>/webhook` + your verify token
- [ ] Subscribe fields: Messenger `messages`; Page `feed`; Instagram `messages`, `comments`

**Permissions needed:** `pages_messaging`, `pages_manage_metadata`,
`pages_read_engagement`, `instagram_manage_messages`, `instagram_manage_comments`.

---

## 4. Set the secrets in Cloudflare — **(me)**

These are private — set as Worker secrets, never committed:
- [ ] `META_APP_SECRET` — from the FB app
- [ ] `META_VERIFY_TOKEN` — any string we pick (also guards `/escalations` & `/leads`)
- [ ] `META_PAGE_TOKEN` — the long-lived page token
- [ ] `ANTHROPIC_API_KEY` — for the AI
- [ ] `RESEND_API_KEY` + `ALERT_EMAIL_FROM` — email alerts
- [ ] `PUSH_URL` — `https://ntfy.sh/hp-landscaping-alerts-0952f31e13`
- [ ] (Skipped: all `TWILIO_*` — no texts/calls for now)

And in `knowledge.ts` `notify`: your **alert email(s)** (and optionally cells later).

---

## 5. Test before relying on it — **(me + you)**

- [ ] Send your Page a **test DM** with a basic question → bot replies in your voice
- [ ] Comment a **basic question** on a post → bot replies publicly
- [ ] Comment/DM a **pricing question** → bot sends the handoff + you get **email + ntfy ping**
- [ ] Mention **water/storm damage** → you get a **Restore lead** alert
- [ ] Check `/escalations?key=...` and `/leads?key=...` show the items

Works for you and anyone added as an app tester immediately.

---

## 6. Open it to the public — **(you submit, me to prep)**

To reply to the **general public** (not just testers), Meta requires:
- [ ] **App Review** for the messaging permissions (submit use case + short screencast)
- [ ] **Business verification**
- [ ] A **privacy policy URL**

This is Meta's process — typically **2–7 days**. I'll prep the submission text so it's
as fast as possible. Until approved, the bot works fully for you/testers.

---

## After go-live (Phase 2+)

- Add **Restore** as its own profile (same steps, its own Page)
- Add **WhatsApp** (runs through Meta — no Twilio)
- Apply for **LinkedIn** company-page comment access (Marketing Developer Platform)
- Build the **LinkedIn outreach drafting queue** (compliant: AI drafts, human sends)
- Unified **dashboard** + reporting agent
