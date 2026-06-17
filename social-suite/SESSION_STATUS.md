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
- `clip/` auto-clipper + full orchestrator wiring — **finishing in background
  tonight** (branch `claude/social-suite-clipper`); merge + retest on resume
- Docs: `RESEARCH.md` (verified stack/licenses), `ARCHITECTURE.md`,
  `PLATFORM_SETUP.md` (per-platform dev-app guide), `REVIEW_SUBMISSIONS.md`,
  `legal/PRIVACY_POLICY.md`, `legal/TERMS.md`

## ✅ Done — user actions this session
- HP + Restore Instagram → **Business accounts**, linked to Facebook Pages
- HP **Meta developer app** created ("HP Restore Publisher"), connected to the
  **Higher Purpose Landscaping** business portfolio
- **App ID + App Secret saved** (in user's own notes — never shared)
- Meta **Business Verification** started; was uploading the **business license**

## 🔲 Remaining — ON ME (no user action)
1. Merge the clipper + orchestrator branch, re-run all tests, push (auto tonight)
2. Write a `QUICKSTART.md` for running the suite locally once keys exist
3. Final pass: ensure `pyproject.toml` deps are complete for a real install

## 🟡 Remaining — NEEDS USER (can't be done without you)
1. **Finish Meta Business Verification** — upload the clear license photo (guide
   given: flat, well-lit, all corners, text readable, name/address match form)
2. **Second Meta app for Restore** — same steps, under "Restore Marketing Co"
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
