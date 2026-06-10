# Social AI Responder

Fully automated AI responder for **Facebook Pages** and **Instagram** — answers DMs
and comments from customers. Runs on **Cloudflare Workers**, powered by the **Claude API**.

```
Meta webhook ──▶ Cloudflare Worker ──▶ Claude (classify + draft) ──▶ reply
                       │
                       ├─ KV: dedup + escalation queue
                       └─ uncertain? ──▶ you (Slack/Discord/email + /escalations)
```

## How it decides (hybrid)

For every comment or DM, one Claude call classifies the message against that
business's knowledge base and returns a structured decision:

- **Auto-reply** — a general FAQ-type question it can answer accurately and safely.
  The reply is posted **instantly**, with no human in the loop.
- **Escalate** — pricing, quotes, complaints, specific scheduling, billing, anything
  ambiguous or emotional. The customer gets a friendly *"let me check and get right
  back to you!"* holding reply, and **you** get pinged to take over.

A confidence floor (`MIN_AUTOREPLY_CONFIDENCE`) escalates anything shaky even if the
model leaned toward auto-replying. On any error it fails safe to escalation — it will
never auto-send something it isn't sure about.

## What it handles

| Platform | DMs | Comments |
|----------|-----|----------|
| Facebook Page | ✅ Messenger | ✅ Page post comments |
| Instagram | ✅ IG Direct | ✅ Post comments |
| Phone (Twilio) | ✅ Voice calls (speech) | — |

> **Phone calls** are also supported via Twilio — the bot answers calls, speaks FAQ
> answers, and transfers or takes a voicemail on anything uncertain. See
> [Phase 2: voice calls](#phase-2-voice-calls-built-in) below.

---

## Setup

### 1. Install + Cloudflare login

```bash
cd tools/social-ai-responder
npm install
npx wrangler login
```

### 2. Create the KV namespace

```bash
npm run kv:create
```

Paste the returned `id` into `wrangler.toml` under `[[kv_namespaces]]`.

### 3. Set secrets

```bash
npm run secret:appsecret    # META_APP_SECRET    (Meta App > Settings > Basic)
npm run secret:verify       # META_VERIFY_TOKEN  (any string you invent)
npm run secret:pagetoken    # META_PAGE_TOKEN    (long-lived page token, see step 5)
npm run secret:anthropic    # ANTHROPIC_API_KEY
npm run secret:escalation   # ESCALATION_WEBHOOK_URL (optional — Slack/Discord/email)
```

For local testing, copy `.dev.vars.example` → `.dev.vars` and fill it in instead.

### 4. Add your business knowledge

Edit `src/knowledge.ts`: replace `REPLACE_WITH_PAGE_ID` with your real Facebook Page ID
and fill in `services`, `hours`, `faq`, and `escalateWhen`. Add one block per business
(HP Landscaping, Restore, etc.). The Page ID is in Meta Business Suite → Settings, or in
any webhook payload as `entry[].id`.

### 5. Create a Meta app + tokens

1. [developers.facebook.com](https://developers.facebook.com) → **Create App** → *Business*.
2. Add products: **Messenger**, **Instagram**, **Webhooks**.
3. Connect your Facebook Page (and the IG account linked to it).
4. Generate a **Page Access Token**, then exchange it for a **long-lived** token
   (the [Access Token Tool](https://developers.facebook.com/tools/accesstoken/) +
   `/oauth/access_token?grant_type=fb_exchange_token`). Required permissions:
   `pages_messaging`, `pages_manage_metadata`, `pages_read_engagement`,
   `instagram_manage_messages`, `instagram_manage_comments`.
   - Multiple pages? Set `META_PAGE_TOKENS` to a JSON map `{"<pageId>":"<token>"}` instead.

### 6. Deploy

```bash
npm run deploy
```

You'll get a URL like `https://social-ai-responder.<you>.workers.dev`.

### 7. Point Meta at the Worker

In the Meta App **Webhooks** product:

- **Callback URL:** `https://social-ai-responder.<you>.workers.dev/webhook`
- **Verify token:** the same `META_VERIFY_TOKEN` you set in step 3.
- **Subscribe** the Page to these fields:
  - Messenger: `messages`
  - Page: `feed`
  - Instagram: `messages`, `comments`

Meta will hit `/webhook` with a verification challenge; the Worker answers it
automatically. Send your page a test DM and comment to confirm.

---

## Operating it

- **Review escalations:** `GET /escalations?key=<META_VERIFY_TOKEN>` returns the queue
  (also pushed to your `ESCALATION_WEBHOOK_URL` in real time if set).
- **Watch logs:** `npm run tail`
- **Tune behavior:** `wrangler.toml` → `CLAUDE_MODEL`, `CLAUDE_EFFORT`,
  `MIN_AUTOREPLY_CONFIDENCE`.
- **Cost:** model is `claude-opus-4-8` at low effort by default. For high message
  volume you can switch `CLAUDE_MODEL` to `claude-haiku-4-5` in `wrangler.toml` to cut
  per-message cost.

## Safety notes

- The bot never quotes prices, commits to dates, or invents facts — those are hard
  escalation triggers in `knowledge.ts`.
- Signatures on every webhook are HMAC-verified against your app secret.
- Events are de-duplicated in KV so Meta retries don't double-post.

## Phase 2: voice calls (built in)

The same Worker also answers **phone calls** via Twilio, reusing `decide()` and the
per-business knowledge base. A caller talks; Twilio transcribes; the bot answers FAQs
out loud and keeps the conversation going, or — for pricing/complaints/scheduling —
warm-transfers to you (if you set a `transferNumber`) or takes a voicemail. Every
escalation and voicemail lands in the same `/escalations` queue.

```
Caller ──▶ Twilio (speech-to-text) ──▶ /voice/collect ──▶ decide() ──▶ <Say> answer
                                                              │
                                                              └─ escalate ─▶ <Dial> you  /  voicemail
```

**Routes:** `/voice` (incoming), `/voice/collect` (each speech turn), `/voice/voicemail`.

### Setup

1. **Configure voice in `src/knowledge.ts`:** add a `voice` block to the business
   (greeting + optional `transferNumber` in E.164), and map your Twilio number to the
   business in `VOICE_NUMBER_TO_PAGE` (e.g. `"+15551234567": "<your Page ID>"`).
2. **Set the Twilio secret:** `npm run secret:twilio` (your Twilio **Auth Token** from
   [console.twilio.com](https://console.twilio.com)). If a custom domain/proxy changes
   the public URL, also set `PUBLIC_BASE_URL`.
3. **Buy a number** in Twilio and, under its **Voice configuration → A call comes in**,
   set a **Webhook (HTTP POST)** to
   `https://social-ai-responder.<you>.workers.dev/voice`.
4. `npm run deploy` and call the number to test.

Every call webhook is validated against Twilio's `X-Twilio-Signature`. To disable voice,
just leave `TWILIO_AUTH_TOKEN` unset — the voice routes then reject all requests.
