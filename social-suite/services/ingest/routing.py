"""Route a Dropbox file to its brand by the top-level folder it lives in.

The Dropbox app folder holds one subfolder per brand (``/HP``,
``/Restore Marketing Content``, …). A video's brand is the name of its top
folder, lowercased — so a clip in ``/HP`` posts only to HP's accounts and one
in ``/Restore Marketing Content`` only to Restore's. A folder whose lowercased
name *starts with* a known brand prefix is matched to that brand, so renaming
``/Restore`` to ``/Restore Marketing Content`` keeps routing working without a
code change. This is what keeps each client's content locked to its own
channels. Pure stdlib, no network.
"""

from __future__ import annotations

DEFAULT_BRAND = "default"

# Known-brand prefixes: a top folder whose lowercased name starts with one of
# these routes to that brand. Order matters only if prefixes overlap.
BRAND_PREFIXES: tuple[str, ...] = ("restore",)


def brand_for_path(path: str) -> str:
    """Return the brand name for a Dropbox path by its top-level folder.

    ``/HP/clip.mp4`` -> ``"hp"``; ``Restore/sub/x.mov`` -> ``"restore"``;
    ``/Restore Marketing Content/clip.mp4`` -> ``"restore"``; a path with no
    folder (just a filename) -> ``"default"``.
    """
    parts = [p for p in (path or "").replace("\\", "/").split("/") if p]
    if len(parts) < 2:
        # Just a filename (no folder) -> no brand folder to route by.
        return DEFAULT_BRAND
    folder = parts[0].strip().lower()
    for prefix in BRAND_PREFIXES:
        if folder.startswith(prefix):
            return prefix
    return folder
