"""Route a Dropbox file to its brand by the top-level folder it lives in.

The Dropbox app folder holds one subfolder per brand (``/HP``, ``/Restore``,
…). A video's brand is simply the name of its top folder, lowercased — so a
clip in ``/HP`` posts only to HP's accounts and one in ``/Restore`` only to
Restore's. This is what keeps each client's content locked to its own channels.
Pure stdlib, no network.
"""

from __future__ import annotations

DEFAULT_BRAND = "default"


def brand_for_path(path: str) -> str:
    """Return the brand name for a Dropbox path by its top-level folder.

    ``/HP/clip.mp4`` -> ``"hp"``; ``Restore/sub/x.mov`` -> ``"restore"``; a path
    with no folder (just a filename) -> ``"default"``.
    """
    parts = [p for p in (path or "").replace("\\", "/").split("/") if p]
    if len(parts) < 2:
        # Just a filename (no folder) -> no brand folder to route by.
        return DEFAULT_BRAND
    return parts[0].strip().lower()
