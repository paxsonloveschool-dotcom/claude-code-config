# Resume notes (2026-06-22 → next session)

## Where we are
- **10 clips sit in review, nothing posts** (queue.json: all `status:"review"`, 0 `pending`).
  - 6 b-roll montages from the 4 ACAM cleanup videos: `hp-grind-trim`,
    `hp-cleanup-crew`, `hp-trim-satisfy`, `hp-dust-hook`, `hp-haul-out`, `hp-day-on-job`.
  - 4 auto-picked from the narrated reveal: `hp-auto-1..4`.
- All 10 were sent to the owner to watch. Owner said "okay for now."
- **HP house style decoded** from 30 of their own IG posts → see `STYLE_PROFILE.md`
  ("HP HOUSE STYLE"). Reference thumbnails + captions in `content/reference/hp/`.
- **Logo asset** saved (rough, color-keyed from their IG watermark) at
  `content/brand/hp-logo.png`. **Owner is bringing a CLEAN transparent PNG tomorrow**
  — swap it in at the same path when it arrives.

## Next steps (the "make every clip match HP" pass)
STATUS: items 2 (HP caption voice), 3 (0.8 dissolve), and 4 (3-panel stack via
`"stack": true`, helpers `_edit_panel`/`_stackN`, demo `hp-stack-demo`) are DONE
and pushed. All clips re-rendered in HP voice. ONLY item 1 (logo) remains — code
is ready, just drop the clean PNG at `content/brand/hp-logo.png` and re-render.

Waiting on owner: (a) keepers vs kills on the 11 review clips; (b) single-shot vs
3-panel stack as the default for horizontal b-roll; (c) the clean logo PNG; (d)
more luxury/finished-project footage (cleanup b-roll ≠ HP's polished reveals).

1. **Logo watermark, top-right, on every clip.** Add a `logo` param to
   `_edit_short` (ffmpeg: extra `-i logo`, `filter_complex`
   `[0:v]<vchain>[bg];[L:v]scale=200:-1[lg];[bg][lg]overlay=W-w-28:28[v]`).
   Add `_brand_logo(brand_key)` → `content/brand/<key>-logo.png` if it exists.
   Pass it automatically from `cut_windows` (and `auto_highlights` via cut_windows).
2. **HP caption voice**, baked in. For `brand_key=="hp"`, set caption to:
   hook (rotating, e.g. "Turned this backyard into a place you actually want to be.")
   → `Call (979) 777-8851!!` → `•`/`•` →
   `#TXOutdoorLiving #DreamBackyard #OutdoorLiving #backyardgoals`.
   (Also fixes the garbage Whisper-hallucinated b-roll captions, and skips
   transcription for HP captions entirely.)
3. **Smooth dissolve**: bump `_concat` default `xfade` 0.4 → ~0.8.
4. **(Optional) 3-panel vertical stack** for horizontal b-roll (HP do this) —
   tile 3 horizontal shots to fill 9:16 instead of center-cropping.
5. **Re-render** the kept clips (same b-roll `recut_specs` + `auto_highlights` on
   the reveal), then `fetch_previews=all` and send them.

## Pipeline modes (workflow_dispatch inputs on `.github/workflows/pipeline.yml`)
`recut_specs` (JSON cuts) · `auto_highlights` (N) · `dump_transcript` · `dump_thumbs`
· `keep_ids` (prune) · `fetch_previews` (all|ids) · `ig_reference` (hp|hp:30) · `video`.
Everything runs on GitHub Actions (Dropbox + Graph API are blocked from the sandbox).

## Hard constraints (unchanged)
- $0, no credit card. Computer can be off. **NOTHING posts until owner approves.**
- Per-brand only; never cross brands. No burned subtitles (logo only).

## In parallel
- Owner is connecting **TikTok** in another Claude Code session — see `TIKTOK_SETUP.md`.
