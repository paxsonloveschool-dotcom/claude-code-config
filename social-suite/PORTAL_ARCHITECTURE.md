# Portal Architecture — Self-Hosted Multi-Brand Content Distribution

The "build-your-own Blotato": one agency dashboard → many client brands → 6
platforms (Google Business Profile, YouTube, TikTok, Instagram, Facebook, X).
Built on top of the existing `social-suite/` pipeline (which becomes the
content-generation *engine* feeding the distribution queue).

## Data model (multi-tenant)
```
Agency ──< Brand ──< Channel ──< PostTarget >── Post >── MediaAsset
                       │
                   OAuthToken (1:1 per channel, encrypted at rest)
```
- **Agency** — tenant root; holds app-level platform credentials (~6 secrets).
- **Brand/Client** — `timezone`, `default_schedule`, `brand_voice` (feeds the
  copywriter), `default_hashtags`, `gbp_cta_default`, `status`.
- **Channel** — one row per platform per brand. `platform`, `external_account_id`
  (ig_user_id / page_id / yt channel / tiktok open_id / x user id / gbp location),
  `health_status`, `enabled`. UNIQUE(brand_id, platform).
- **OAuthToken** — 1:1 with Channel; `access_token_enc`/`refresh_token_enc`
  (Fernet/AES-GCM, key from secret store `TOKEN_ENC_KEY`), expiries, scopes.
- **Post** — shared content: `base_text`, `base_hashtags`, `media_asset_ids`,
  `status`, `scheduled_for`, `source` (manual|pipeline).
- **PostTarget** — the fan-out join (Post → N channels). Per-platform overrides:
  `override_text`, `platform_options` (YT title/desc, GBP CTA, TikTok privacy…),
  `status`, `external_post_id`, `error`, `attempts`.
- **MediaAsset** — `kind`, `storage_path`, **`public_url`** (IG/FB/GBP/TikTok-pull
  fetch server-side from a URL), dims, `variants[]` (9:16, 1:1/4:5, 16:9).

## Credentials (two layers)
- **App-level** (per agency, ~6 secrets) — in host secret store, not the DB.
- **Channel-level** (per client token) — in `OAuthToken`, **encrypted at rest**;
  decrypted only in the poster at send time; nightly refresh job flips
  `Channel.health_status` before a post can fail.

## Distribution engine
Adapter/strategy pattern under `services/publish/direct/`: `meta.py` (built),
`x.py`, `tiktok.py`, `youtube.py`, `gbp.py`. Uniform interface:
`adapt(post, target, channel) -> payload` then `publish(payload, token)`.
Generalize `run_due.py`'s platform `if`-ladder into an adapter registry.
`adapt()` resolves base text → per-platform constraints (X 280-char, IG 2200,
YT description+title, GBP summary+CTA), honoring `PostTarget` overrides.

## Stack (solo-dev maintainable)
**FastAPI + HTMX + Jinja2 + Tailwind, Postgres, SQLAlchemy + Alembic.** Reuses
the repo's existing FastAPI; no second language/SPA build. Postgres replaces the
flat `content/queue.json` (doesn't scale to 20 brands × 6 channels). Views:
Clients grid (channel-health dots) · Brand detail (connect/OAuth + settings) ·
Content calendar · Compose/Distribute (per-platform override tabs + live preview)
· Post status (per-target retry; partial-failure safe).

## Runner
GitHub-Actions cron (current, free) is fine for IG/FB MVP, but at 20 brands with
YouTube resumable uploads + TikTok/IG status polling, move to a **small always-on
worker** (APScheduler or rq/Celery on Redis) on the deploy host: a minute tick
enqueues one job per due `PostTarget`; jobs handle upload/poll/retry and write
status back to the DB the dashboard reflects live.

## Platform approval + cost matrix
**Every approval is ONE-TIME per agency app/project — never per client.** After
it, each brand connects via standard OAuth.

| # | Platform | One-time approval | Difficulty | Cost | Key constraint |
|---|---|---|---|---|---|
| 1 | Facebook | Meta App Review + Business Verification | Low (built) | Free | public media URL |
| 2 | Instagram | (same Meta review) | Low (built) | Free | public URL, async Reels poll, ~100/24h |
| 3 | X | none (signup + use-case) | Low–Med | **pay-per-use $0.015/post, $0.20/link-post** | upload bytes; metered |
| 4 | TikTok | Content Posting API audit | Medium | Free | mandatory disclosure UI, domain verify |
| 5 | YouTube | OAuth verification + Compliance Audit | Med–High | Free | uploads force-private until audit; ~6 uploads/day quota |
| 6 | Google Business Profile | API allowlisting form + OAuth verification | High (slow queue) | Free | v4-only API; longest wait — submit day 1 |

Integration order: **FB → IG → X** (MVP) → **TikTok → YouTube** (audits in
parallel) → **GBP** (start its form day 1, integrate last).

## Phased build plan
- **Phase 0** — Postgres/SQLAlchemy model + Alembic, FastAPI+HTMX shell, login,
  Clients + Brand-detail views; migrate `queue.json` → `Post`/`PostTarget`.
- **Phase 1 (MVP)** — distribute to **IG + FB + X**: OAuth connect + encrypted
  token storage, adapter registry, Compose/fan-out, status/retry, always-on
  worker. Usable product. (Submit Meta App Review + register X now.)
- **Phase 2** — YouTube + TikTok adapters (submit audits at Phase-1 kickoff).
- **Phase 3** — Google Business Profile (allowlisting submitted day 1).
- **Phase 4** — calendar drag-reschedule, brand-voice pipeline auto-drafts,
  analytics, token-health alerting.

## Verdict
All 6 platforms are achievable for 20+ brands from one self-hosted dashboard.
Friction = a handful of **one-time app-level approvals** (Meta, TikTok, YouTube,
GBP) + X's per-post metering — never per-client bureaucracy. MVP (IG+FB+X) is
~2–3 weeks of build, gated only by Meta review.

> Source caveat: some platform doc pages 403 automated fetchers; verify live
> numbers (esp. X per-post pricing, IG 100/24h) in each platform console before
> committing.
