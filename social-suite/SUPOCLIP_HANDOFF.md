# Handoff: "SupoClip" Bulk Clip Pipeline ↔ Postiz Posting System

_From the clip-building session → to the Postiz/posting session. Please confirm no conflict._

## 0. TL;DR
A new clip-making system was built that turns raw videos into short, captioned,
on-brand clips and drops them in a REVIEW list. It does **NOT** post anything. The
Postiz system is untouched and remains the only thing that uploads. The two only
meet at a **manual handoff** (owner approves a clip → it gets fed to Postiz).
Nothing was merged to `main`; it all lives on draft-PR branches.

## 1. The goal (what the owner wants)
Drop a bunch of videos (talking-head, plus b-roll work footage) into Dropbox →
the system intelligently picks the best moments → cuts them into short clips
(~10–20s) → talking clips get word-by-word subtitles, b-roll gets a montage in the
locked HP style → everything lands in a review feed, best-first → owner approves the
good ones → those get posted by the existing **Postiz** system. Free / no paid APIs.
Nothing posts without approval.

## 2. What was built + where it lives
- Repo: `paxsonloveschool-dotcom/claude-code-config`, folder `social-suite/`
- Branch `claude/bulk-pipeline` (draft PR #26) = the clip brain (shots, scoring,
  montage, talking-clips + subtitles, review feed)
- Branch `claude/blissful-cray-hymyhw` (draft PR #25) = branded 3s end-card "outro"
  videos (HP + Restore)
- **NOT merged to `main`.** The live system is unaffected until merge.

## 3. What it does (capabilities)
Each step runs on demand via the existing **"Video pipeline"** GitHub Action inputs:
- `detect_shots` → split each video into camera shots
- `score_shots` → rate each shot (sharpness/motion/exposure/color) → best-first
- `auto_montage` → b-roll → a 10–20s montage in the locked style (logo + end-card)
- `auto_clips` → TALKING video → transcribe → pick the best complete "sayings"
  (drops filler / dead air / half-sentences) → vertical 1080×1920 clip WITH audio +
  animated word-by-word subtitles
- `review_feed` → a single best-first web page of everything awaiting approval

Output of every step: the finished clip is uploaded to Dropbox `<Brand>/processed/`
**and** a row is added to `social-suite/content/queue.json` with `status:"review"`.

## 4. Hard guardrails (built in)
- **NOTHING auto-posts.** The pipeline only ever writes `status:"review"`.
- **Per-brand isolation** (an HP clip can never go to Restore and vice-versa).
- **$0** — no paid APIs/keys (local Whisper, ffmpeg, Pillow). Heavy work runs on
  GitHub Actions, not locally.

## 5. How it works WITH the Postiz system (the boundary — please verify)
Two **separate** data stores, no automatic connection:
- Clip pipeline writes → `social-suite/content/queue.json` (status `review`) +
  Dropbox `<Brand>/processed/`.
- Postiz reads → `postiz/automation/content/*.json` (format: `{text, channels,
  schedule, image}`) and is what actually schedules/uploads to the accounts.

These files are different. The clip pipeline does **NOT** write to Postiz's content
files, so a new clip does **NOT** reach Postiz on its own.

Also note (so nothing is ambiguous): there is a *second*, idle poster in
`social-suite/services/publish/run_due.py` that posts `status:"pending"` rows from
`queue.json` — but its schedule is **commented off** (manual only) and the clip
pipeline never sets `pending`, so it stays dormant. Postiz remains the live poster.

**The handoff (today = manual):** owner reviews the clips → approves the good ones →
their caption + media get added into a Postiz content file → Postiz schedules &
uploads as usual. (Optionally, a small bridge could later auto-copy approved clips
into a Postiz content file — not built; Postiz logic would not change.)

## 6. Please confirm from the Postiz side
1. Postiz pulls content **only** from `postiz/automation/content/*.json` (or wherever
   it is configured) and does **not** read `social-suite/content/queue.json`. ✅/❌
2. Nothing in the clip-pipeline branches changes Postiz, its workflow
   (`postiz-schedule.yml`), the Oracle server, or any uploader. (Verified on the clip
   side — those branches touch none of those files.) ✅/❌
3. Decision for later: do we want an automated "approved clip → Postiz content"
   bridge, or keep the handoff manual? (Either way, Postiz behavior is unchanged.)
