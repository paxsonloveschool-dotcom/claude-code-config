# Social Suite — Session Status & Resume

> Saved end of session 2026-06-17. Say **"continue the social suite"** next
> session and start here. Everything below is committed + pushed.

## What this project is
An **in-house, self-owned automated social media content suite** (no SaaS).
Pipeline: Dropbox raw video → auto-clip to 9:16 shorts → transcribe + burn
animated captions → Claude writes hooks/captions → schedule/post to all
platforms via Postiz → FastAPI orchestrator runs it automatically.

All code lives in `social-suite/`. Main PR: **#21** (branch `claude/social-suite`).

## ✅ Done — code (PR #21, 39 passing tests)
- Scaffold + FastAPI orchestrator (`/health`, `/run`)
- `ingest/` Dropbox client (refresh-token auth, longpoll watch, download)
- `caption/transcribe.py` faster-whisper (word-level timestamps)
- `caption/ass_builder.py` + `burn.py` — TikTok-style word-by-word animated
  captions (ASS karaoke → ffmpeg), hardened for bad timings
- `write/copywriter.py` — Claude (`claude-opus-4-8`) hooks/captions/hashtags,
  prompt-cached, defensive JSON parsing
- `publish/poster.py` — Postiz public API (`POST /public/v1/posts`, all channels
  in one call), HTTP error handling, dry-run
- `clip/clipper.py` — auto-clipper: transcript highlight selection +
  ffmpeg 9:16 reframe (optional Claude re-ranking via `CLIP_USE_LLM`)
- `orchestrator/pipeline.py` — **full end-to-end chain wired**: ingest → clip →
  transcribe → caption → write → publish, with a no-keys `dry_run` mode
- Docs: `RESEARCH.md`, `ARCHITECTURE.md`, `QUICKSTART.md` (run it locally),
  `PLATFORM_SETUP.md`, `REVIEW_SUBMISSIONS.md`, `legal/PRIVACY_POLICY.md`,
  `legal/TERMS.md`

**Code is feature-complete. 48 tests pass. Pipeline dry-run runs all 5 stages
end-to-end (1 video → 2 clips → captioned → written → scheduled).**

## ✅ Done — user actions this session
- HP + Restore Instagram → **Business accounts**, linked to Facebook Pages
- HP **Meta developer app** created ("HP Restore Publisher"), connected to the
  **Higher Purpose Landscaping** business portfolio
- **App ID + App Secret saved** (in user's own notes — never shared)
- Meta **Business Verification** started; was uploading the **business license**

## ✅ Remaining — ON ME — DONE overnight
1. ✅ Merged clipper + orchestrator, all 48 tests green, pushed
2. ✅ `QUICKSTART.md` written
3. Codebase feature-complete — nothing else needed from me until hosting/keys

## 🟢 KEY FINDING — Meta needs NO verification for own-account posting
Posting to **our own** IG Professional account + **our own** FB Page via the
Graph API only needs **Development Mode + Standard Access** — **NO App Review and
NO Business Verification**. Those only gate **Advanced Access** (serving *other*
people's accounts), which we never request. So Meta is **not** the long pole and
there is nothing to wait on. The only remaining human step is **generating the
dev-mode token** (short-lived user token → long-lived exchange → Page token from
`/me/accounts`), fully documented in **`META_SETUP.md`**. Direct posting
(`services/publish/direct/meta.py` + `run_due.py` + the GitHub Actions cron)
bypasses Postiz entirely for IG/FB.

## 🟡 Remaining — NEEDS USER (can't be done without you)
1. **Generate the Meta dev-mode Page token** — follow `META_SETUP.md` (no
   verification, ~10 min), then set the `META_ACCESS_TOKEN`, `IG_USER_ID`,
   `FB_PAGE_ID` GitHub Secrets. (Replaces the old "finish Business Verification"
   item — verification is NOT required for this path.)
2. **Second Meta app for Restore** — same `META_SETUP.md` steps, under "Restore
   Marketing Co"
3. **Decide where Postiz/the suite is hosted** — needs a public HTTPS URL for the
   social OAuth + Meta App Review. (Local Mac alone can't do OAuth without a
   tunnel; a small always-on host is cleaner.)
4. **Finish each platform's dev-app + review** (`PLATFORM_SETUP.md`) — the long
   pole; only completable once the app is running at a public URL
5. **Provide keys when ready:** Dropbox (app key/secret/refresh token),
   `ANTHROPIC_API_KEY`, Postiz API key + channel IDs

## Open PRs / branches
- **#21** `claude/social-suite` — the suite (main, draft)
- #17 `claude/postiz-channel-labels` — Postiz per-account label safety (draft)
- Merged: #16 (Postiz core), #18 (Mac local), #19 (pin v2.11.2)

## How to resume tomorrow
1. "continue the social suite" → I merge the clipper, confirm all tests green.
2. If verification is done: pick a host, deploy Postiz, set redirect URLs.
3. Otherwise: finish the license upload, then proceed to hosting.
