# SupoClip Ownership — Talking-Clip Pipeline (this branch owns it)

The two Claude sessions split the workload so they run in parallel:

| Session | Owns | Reads from | Saves to | Branch |
|---|---|---|---|---|
| **Work/Content** | b-roll montages (build→finished) | `HP Content` | `HP Posts` | `claude/happy-faraday-poh621` |
| **SupoClip (THIS branch)** | talking-head captioned clips | `HP Talking Content` | review queue | `claude/bulk-pipeline` |

Both write `status:"review"` to `social-suite/content/queue.json`, per-brand isolated.
**Nothing posts** — Postiz (`postiz/`) is the only uploader and is untouched.

## How to run SupoClip (talking clips)
Dispatch the **Video pipeline** workflow **from `claude/bulk-pipeline`** with:
- `auto_clips`: any number (e.g. `12`) — it picks up to that many GOOD sayings, quality-gated
- `content_folder`: `HP Talking Content`

It transcribes the first video in HP Talking Content, picks the strongest sayings,
cuts vertical 1080x1920 clips, and lands them in the review queue. Never posts.

## Talking-clip style (already built — tune here)
Set in `services/caption/ass_builder.py` (`build_style`) + `auto_clips` in `automation/video_pipeline.py`:
- **Captions:** Roboto **Bold**, ~60px, **lower-third** (`margin_v=320`), thick black **outline (4) + drop shadow (2)**. Font installed via `fonts-roboto` in the workflow; `CAPTION_FONT=Roboto`. Size via `CAPTION_FONT_SIZE` (default 60, target 48–60px).
- **Logo:** HP watermark in the corner of every clip (`_edit_short(..., logo=_brand_logo(brand_key))`).
- **Outro:** brand end-card appended to every clip (`append_outro`, asset `content/brand/outro.mp4`).
- **Length:** 6–45s (`_pick_highlights(..., min_len=6, max_len=45)`).
- **Count:** up to 12 good clips (`n=max(n,12)`); the scorer drops filler/dead air.

## Folder reads are scoped by `CONTENT_FOLDER`
`_first_video` now reads from `<brand>/<CONTENT_FOLDER>` (e.g. `HP Talking Content`).
Empty → falls back to brand root (back-compat).

## Heads-up
- The work session pushed several commits to this branch (CONTENT_FOLDER scoping, the
  style changes above, and a **commit-step fix** so runs finish green + save the queue).
  **`git pull` before your next push.**
- Going forward the work session will NOT touch this branch — SupoClip is yours.

## Still open to tune
- Caption exact size/position to taste; whether to brand-color the karaoke highlight.
- Auto-trigger (drop a video in HP Talking Content → run on a schedule) if you want it
  fully hands-off — currently manual `auto_clips` dispatch.

## 🔒 LOCKED clip spec (owner-approved 2026-06-25) — every new clip, always
Baked into `auto_clips` defaults so it's automatic. Tunable via env if ever needed.
- **Captions:** shown **~4 words at a time** (`CAPTION_MAX_WORDS=4`), word lights up
  as spoken. **Bold sans (Roboto), ~54px, WHITE, thin black outline (2) + soft shadow
  (1)**, lower-third (`margin_v=320`). `CAPTION_FONT`, `CAPTION_FONT_SIZE`.
- **Clean cuts:** every clip **starts and ends on a clear word** — leading/trailing
  stutters, filler ("um/uh/so/like/you know"), and stutter-repeats are trimmed
  (`_trim_to_clean`).
- **Stitching:** a clip can drop a weak/boring middle and **jump-cut** the strong
  parts together (e.g. first 5s + 13-20s, with 6-12s removed) — chronological, stays
  in sync (`_clip_pieces` + `_hardcat`, captions re-timed across the cut).
- **Only great clips:** quality floor `CLIP_MIN_SCORE=1.0` — weak/rambly stretches
  never become clips.
- **Length:** ideal **12-30s**, allowed **6-45s** if it's fire (scorer centers ~21s).
- **Per clip:** logo watermark + brand outro end-card appended. Vertical 1080x1920,
  audio kept. Nothing posts (status `review`).
