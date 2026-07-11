# Social Suite — Project Rules (team memory)

## Edit = Replace (HARD RULE, every time)
When the user asks to edit / redo / fix / re-style a clip, the OLD version is
disposable. Always **delete the prior version and keep only the new one** — never
let old versions pile up in Dropbox.
- `save_styled` overwrites the same HP Posts filename → the saved clip is replaced in place.
- After any re-render cycle, run `purge_edited=go` so the `processed/` and
  `HP Processed` staging folders hold **nothing** but the latest work.
- End state is always: **HP Posts = only the current finished clips; processed folders = empty.**

## HARD content rules
- **NO pricing on videos, ever.** Never put dollar amounts, build cost, or "$X" price
  callouts (or price-guessing formats) on any clip. No exceptions.
- Never fabricate specifics (gallons, sq ft, weeks, cost). Only use real numbers the
  owner provides — and never a price.

## Folder organization (keep it clean)
- **HP Auto Post** is organized BY PROJECT/property subfolder (Alice, Barry Pool,
  Waterfall Pool, Modern Pool, …). Save every finished clip into its project
  subfolder — never loose at the HP Auto Post root, and never a format-type folder
  (no "Reels"/"POV" folders — organize by PROJECT, not by video style).
- The geometric checkerboard-deck pool ("bulk pool" raw footage) = project **"Modern Pool"**.
- **HP Tiktok** stays FLAT (clips at its root) — mirror of the posted set.
- Saving = `copy_styled dir:"HP Auto Post/<Project>|HP Tiktok"` (pipe = both folders).

## Storage discipline ($0, free tiers only)
- Dropbox account = `restoremarketingco@gmail.com` (Restore Marketing), free 2 GB target.
- Keep Dropbox lean: original footage in `HP Content` / `HP Talking Content`, finished
  clips in `HP Posts`, staging folders emptied. Archive bulk footage off Dropbox.
- Never buy storage. Nothing posts until the user approves (poster stays off).

## Pipeline gotchas (learned the hard way)
- `montage_spec_file` input is relative to `social-suite/` (the ROOT), e.g. `content/specs/x.json` — NOT repo-root `social-suite/content/...` (that doubles the prefix and 404s).
- Montage renders + uploads to Dropbox `processed/`; it does NOT populate `content/preview/`. To view/fetch a rendered clip you must run `fetch_previews` after.
- Montage segment windows must fit inside the source clip length, or that montage silently fails (batch skips it) and the old Dropbox version is kept. Keep windows conservative or verify after.
- `delete_ids` deletes then FALLS THROUGH to the full transcription pipeline (hangs for hours on CPU). For a pure delete use `delete_paths` (absolute paths, returns cleanly, idempotent — `deleted:false` means already gone).
- Don't run multiple `copy_styled` saves concurrently: they all append `copy_log.json` and race/conflict on the rebase (audit entries lost — uploads still succeed). Run saves sequentially.
- Repo is bloated with committed preview mp4s → runner checkout takes ~3-4 min. Purge old previews from git periodically.

## Finished-clip house style (work montages)
Build → finished arc, end on the finished reveal. Cumulative word/line build text
(Libre Baskerville serif + Nothing You Could Do script accent, brand green `0x20B040`),
logo top-right, brand outro appended. Text holds ~2s after the last line, then fades
out so the reveal is clean. Engine: `scratchpad/style_build.py` (rebuild if lost).
