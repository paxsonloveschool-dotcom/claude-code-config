# Bulk Intelligent Clip Pipeline — build plan ($0, free-first)

Goal: owner drops **thousands** of raw videos in Dropbox → system **auto-finds the
good moments** and cuts them into **15s clips in the locked HP style** → everything
lands in a **bulk review feed** (sorted best-first). **Nothing posts until approved.**

## Decisions (locked by owner 2026-06-23)
- **$0 / no credit card / no API keys.** Free models only (Whisper, CLIP, scene
  detection, OpenCV). Structured so a **paid AI-judge can bolt on later** (pluggable
  scorer) — but not now.
- **Bulk review, owner approves.** Poster only fires `status=="pending"`; cron stays
  off. Auto-clipping writes `status=="review"` only.
- Runs on **GitHub Actions** (Dropbox + Meta Graph are blocked from the sandbox).
- Heavy/slow is fine — **overnight batches**. Speed is the cost, not money.

## What ALREADY exists — EXTEND, don't rebuild (`automation/video_pipeline.py`)
- `auto_highlights(n, match)` — the SupoClip port: transcribe ONE narrated video,
  score speech (`_score_segment_text`, `_pick_highlights`), cut best talking moments.
- `cut_montage(spec)` — assemble b-roll into montages; supports `orient:"cols"`
  (side-by-side) + rows + single; `_stackN`/`_hstackN`/`_edit_tile`/`_concat_v`.
- `cut_windows`, `ingest_clip`, `fetch_previews`, `prune_clips`, `dump_thumbs`,
  `dump_transcript`, `fetch_ig_reference`. Workflow: `.github/workflows/pipeline.yml`
  (workflow_dispatch inputs drive each mode).
- Brand routing `services/publish/brands.py`; poster `services/publish/run_due.py`
  (TikTok/Meta). Queue at `content/queue.json` (status review|pending|sent|paused).
- **Locked montage recipe + style: see `STYLE_PROFILE.md` ("LOCKED MONTAGE RECIPE").**
  Reference keeper: `content/approved/hp-yardwork-hype-final.mp4`.
- Brand assets: `content/brand/hp-logo.png` (watermark), `content/brand/outro.mp4`
  (end-card). **Styling (serif text beats + logo + outro) is currently applied by
  hand locally — it is NOT yet in the pipeline. Productionizing it is Phase 3.**

## The gap this build fills
1. **Visual brain for silent b-roll** (the big one). SupoClip/our port only work off
   the transcript; work footage has no speech, so today a human hand-picks the shots.
   Need: scene-split + visual scoring (sharpness/motion/CLIP) to auto-pick good shots.
2. **Smarter talking-clip judging** — current scorer is keyword-counting; catch
   rambling / flubs / dead air better.
3. **Bulk automation** over thousands + a **fast review feed**.

## Phases
**Phase 1 — Bulk ingest + shot-split**
- Scan all brand folders; for each new video (dedupe via `processed.json`),
  scene-detect into shots (PySceneDetect or ffmpeg `select='gt(scene,0.3)'`).
- Output: per-video shot list (start/end). New module e.g. `services/score/shots.py`.

**Phase 2 — Scoring brain (free)**
- Talking: Whisper transcript → improved segment scoring (hooks/payoff up; filler,
  hesitation, dead air, repetition down). Extend `_score_segment_text`.
- B-roll: per shot — OpenCV sharpness (Laplacian var), motion, exposure + **OpenCLIP**
  score vs prompts ("clean finished landscaping, satisfying work, dramatic reveal"
  vs "blurry, boring, people standing around, messy"). Combine → `fire_score`.
- New module e.g. `services/score/visual.py`. Cache scores; CPU-batched.

**Phase 3 — Auto-assemble in locked style (productionize the styling)**
- Bake the locked recipe into the pipeline (so it runs on the runner, not by hand):
  serif text beats (drawtext — runner apt ffmpeg has libfreetype; **imageio-ffmpeg
  does NOT**), crossfade + every-other word-by-word; logo top-right (`hp-logo.png`);
  append `outro.mp4` (crossfade). **COMMIT A SERIF TTF** to the repo (e.g.
  LibreBaskerville) — the runner needs the font file; `/mnt/skills/...canvas-fonts`
  is sandbox-only. Montages **silent** (`-an`); talking clips **keep audio**, get
  logo+outro, **no text**.
- Talking → `auto_highlights`-style best 15s + logo+outro+sound. B-roll → montage
  recipe (shifting layouts, silent) from the top-scored shots.

**Phase 4 — Bulk review feed**
- Every clip → `status:"review"` with its `fire_score`, sorted best-first. Build a
  fast review surface (a generated contact-sheet/grid page, or a tiny static review
  app) so the owner swipes keep/kill. Approve → `status:"pending"` (poster handles).

**Phase 5 — Upgrade hook**
- Pluggable `Scorer` interface so a paid vision/LLM judge can re-rank later. No rebuild.

## Hard constraints / gotchas
- **NOTHING auto-posts.** Keep the cron in `social-post.yml` commented; only write `review`.
- $0 — no paid APIs/keys. Free Dropbox is 2 GB; at true scale, storage is the only
  real future cost (flag to owner, don't solve now).
- Per-brand only (a clip never crosses brands). Model id never in commits/PRs/code.
- Commit trailers used in this repo; pushes go to `main`. **Coordinate:** the owner is
  ALSO doing manual montage edits in another chat that push to `main`. To avoid
  collisions, **do the build on a branch (e.g. `claude/bulk-pipeline`) and open a
  draft PR**; keep edits to NEW modules where possible; don't break the manual flow
  (`cut_montage`, `cut_windows`, `auto_highlights`, the workflow inputs).
- Verify everything offline-testable (tests run via `__main__`); heavy deps lazy.
