# Restore — Dropbox ingest folder

The Restore brand's top-level Dropbox folder is named **`Restore Marketing
Content`**. Drop videos there and the pipeline routes them to Restore's own
accounts; nothing from this folder can post to HP.

## How routing works

`services/ingest/routing.brand_for_path` turns a Dropbox path into a brand
name by looking at the top-level folder:

- `/HP/clip.mp4` → `"hp"`
- `/Restore/clip.mp4` → `"restore"` (legacy name, still works)
- `/Restore Marketing Content/clip.mp4` → `"restore"`
- `/Restore Marketing Content/2026/jun/y.mp4` → `"restore"`

Any top-level folder whose lowercased name **starts with** a known brand
prefix (listed in `BRAND_PREFIXES` in `routing.py`) routes to that brand. That
is why the folder can be renamed from `Restore` to `Restore Marketing Content`
without a code change — both lowercase to a string that starts with
`restore`.

Folders that don't match a known prefix fall back to the lowercased folder
name verbatim (so HP's `/HP/…` keeps routing to `"hp"`); a bare filename with
no folder falls back to `"default"`.

## Why keep the long name

The folder is the client-facing drop target. `Restore Marketing Content` is
unambiguous to anyone browsing Dropbox; `Restore` on its own gets confused
with the client's other folders. The routing table absorbs the longer name so
the human-friendly label and the brand key stay decoupled.

## Adding another brand later

Add the brand's lowercase prefix to `BRAND_PREFIXES` in
`services/ingest/routing.py`, add credentials under that key in `BRANDS_JSON`
or `content/brands.json` (see `RESTORE_SETUP.md` for the Meta secret shape),
and drop videos in a top folder whose name starts with that prefix.
