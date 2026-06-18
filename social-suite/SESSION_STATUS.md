# Social Suite — Session Status & Resume

> Saved end of session **2026-06-18**. Say **"continue the social suite"** next
> session and start here. Everything below is committed + pushed.

## ⏸️ PAUSED — nothing posts until the owner says "go" (set 2026-06-18)
Two safety layers are in place so **no post fires to any account**:
1. **Auto-scheduler OFF** — the `schedule:` cron in `.github/workflows/social-post.yml`
   is commented out. No automatic runs happen at all.
2. **Queue paused** — every post in `content/queue.json` is `status: "paused"`
   (the poster only ever fires `status: "pending"`), so even a manual
   "Run workflow" posts nothing.

### ▶️ To RESUME later (when the owner says go)
1. Uncomment the two `schedule:` lines in `social-post.yml` (re-enables cron).
2. Flip the posts you want live from `"paused"` → `"pending"` (or rerun
   `python automation/build_queue.py` after setting them pending, to re-stamp
   fresh future schedules so nothing back-fires).
3. `hp-001` is already `"sent"` (it really posted live) — leave it; never re-post it.

## ✅ 2026-06-18 progress
- **HP Landscaping posted LIVE to Facebook** via the GitHub Actions robot —
  full pipeline proven end-to-end (token check → publish). Log: `[sent] hp-001`.
- Merged the whole suite to **`main`** (PR #21) so the workflow can run.
- `BRANDS_JSON` GitHub Secret set with **HP**'s Meta creds (token validated:
  resolves to "Higher Purpose Landscaping", page id 103729542328773).
- Built `automation/build_queue.py` → merged HP+Restore content into a scheduled
  `content/queue.json` (per-brand separation enforced).
- **GBP API allowlist submitted** — case `5-2465000041539`, ~7–10 biz days.
- Then **paused everything** (above) at the owner's request.

## 🌙 Overnight autonomous build (2026-06-18, while owner away — NOTHING posted)
All additive, all tests green (25 test files), all on `main`. Posting stayed
OFF the entire time.
- **CI**: `.github/workflows/tests.yml` runs the full offline suite on every
  push/PR (no secrets, can't post). Green.
- **Portal calendar**: `GET /calendar` shows every queued post per brand with
  schedule + live color-coded status — reads `content/queue.json` read-only.
  (`python -m uvicorn portal.app:app` then open `/calendar` to see it.)
- **Image-card generator**: `services/media/card.py` turns a caption into a
  branded Instagram-ready PNG (themes, auto-fit text, brand footer). CLI:
  `python -m services.media.card "text" out.png --brand "HP Landscaping"`.
  This is the path to **unblock Instagram** for text-first posts.
- **`RESTORE_SETUP.md`**: dead-simple checklist to add Restore as brand #2.
- **Packaging**: `pyproject` now declares `portal` + `automation` packages and
  `portal`/`cards` extras (`pip install -e "social-suite[portal,cards]"`).

### Next session options (owner picks)
- **Add Restore**: follow `RESTORE_SETUP.md` (2nd Meta app + token) → extend
  `BRANDS_JSON` to `{"hp":{...},"restore":{...}}`.
- **Add Instagram for HP**: use the new card generator to make images, commit
  them so they have a public `raw.githubusercontent.com` URL, set `media_url`
  + add `"instagram"` to those posts' platforms.
- **Resume HP** auto-posting (uncomment cron + flip posts paused→pending).
- **Other platforms**: start X / TikTok / YouTube one-time approvals.
- **See the dashboard**: run the portal locally and open `/calendar`.

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

## Platform approval tracker
| Platform | Status | Detail |
|---|---|---|
| Facebook/IG | ✅ proven live | dev-mode token path; needs BRANDS_JSON secret set to automate |
| Google Business Profile | 🟡 in review | **Case `5-2465000041539`**, submitted 2026-06-18, ~7–10 biz days. Project `social-suite-499821` (num `289827224158`), unlocked via verified **HP Landscaping** profile. All profiles unlock once project is approved. |
| X / TikTok / YouTube | ⬜ not started | one-time per-app approvals |

### GBP notes
- Cloud project created under a **personal Gmail** (to bypass the Workspace org's
  forced-billing wall). Access form must be submitted from an account that
  **manages a verified Business Profile** — used HP Landscaping (verified).
- **Restore Marketing** profile is **"Verification required"** → verify it later so
  it can post via the API too (separate task, doesn't block the allowlist).
- Allowlist is **project-level**: once approved, every brand connects via its own
  OAuth regardless of which Google account owns the listing.

## How to resume tomorrow
1. "continue the social suite" → I merge the clipper, confirm all tests green.
2. If verification is done: pick a host, deploy Postiz, set redirect URLs.
3. Otherwise: finish the license upload, then proceed to hosting.
4. GBP: wait for case `5-2465000041539` email (~7–10 biz days), then enable the
   Google My Business API + wire OAuth per brand.
