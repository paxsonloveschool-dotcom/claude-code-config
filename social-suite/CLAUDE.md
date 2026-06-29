# Social Suite — Project Rules (team memory)

## Edit = Replace (HARD RULE, every time)
When the user asks to edit / redo / fix / re-style a clip, the OLD version is
disposable. Always **delete the prior version and keep only the new one** — never
let old versions pile up in Dropbox.
- `save_styled` overwrites the same HP Posts filename → the saved clip is replaced in place.
- After any re-render cycle, run `purge_edited=go` so the `processed/` and
  `HP Processed` staging folders hold **nothing** but the latest work.
- End state is always: **HP Posts = only the current finished clips; processed folders = empty.**

## Storage discipline ($0, free tiers only)
- Dropbox account = `restoremarketingco@gmail.com` (Restore Marketing), free 2 GB target.
- Keep Dropbox lean: original footage in `HP Content` / `HP Talking Content`, finished
  clips in `HP Posts`, staging folders emptied. Archive bulk footage off Dropbox.
- Never buy storage. Nothing posts until the user approves (poster stays off).

## Finished-clip house style (work montages)
Build → finished arc, end on the finished reveal. Cumulative word/line build text
(Libre Baskerville serif + Nothing You Could Do script accent, brand green `0x20B040`),
logo top-right, brand outro appended. Text holds ~2s after the last line, then fades
out so the reveal is clean. Engine: `scratchpad/style_build.py` (rebuild if lost).
