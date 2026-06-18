"""Local-folder ingest — the no-Dropbox, no-token option.

Watches a folder ON THIS MACHINE for new raw videos. Just drop files in (or let
your phone sync them into the folder via iCloud/Finder) — no cloud app, no
OAuth, no refresh tokens. Mirrors ``dropbox_client`` so the pipeline can use
either source interchangeably:
    list_new_files(cursor) -> (files, next_cursor)
    download(file)         -> local path

Config (env):
  INGEST_LOCAL_FOLDER  directory to watch (default: ./media/ingest-in)
  INGEST_VIDEO_EXTS    comma-separated extensions (default below)
  INGEST_DOWNLOAD_DIR  optional: copy picked files here (else used in place)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

DEFAULT_EXTS = "mp4,mov,m4v,avi,mkv,webm"


@dataclass
class LocalFile:
    """A video found in the watched local folder."""

    path: str
    name: str
    size_bytes: int = 0


def _video_exts() -> set[str]:
    raw = os.getenv("INGEST_VIDEO_EXTS", DEFAULT_EXTS)
    return {"." + e.strip().lstrip(".").lower() for e in raw.split(",") if e.strip()}


def _key(name: str, size: int, mtime: float) -> str:
    """Identity for dedupe — name + size + mtime catches re-drops and edits."""
    return f"{name}|{size}|{int(mtime)}"


def list_new_files(cursor: str | None = None, folder: str | None = None):
    """Return ``(new_files, next_cursor)`` for videos not seen in ``cursor``.

    ``cursor`` is an opaque JSON list of file keys already processed; pass the
    returned cursor next time so the same file isn't picked twice.
    """
    folder = folder or os.getenv("INGEST_LOCAL_FOLDER", "./media/ingest-in")
    os.makedirs(folder, exist_ok=True)
    exts = _video_exts()

    try:
        seen = set(json.loads(cursor)) if cursor else set()
    except (ValueError, TypeError):
        seen = set()

    new_files: list[LocalFile] = []
    all_keys: set[str] = set(seen)
    with os.scandir(folder) as it:
        for entry in it:
            if not entry.is_file():
                continue
            if os.path.splitext(entry.name)[1].lower() not in exts:
                continue
            st = entry.stat()
            k = _key(entry.name, st.st_size, st.st_mtime)
            all_keys.add(k)
            if k not in seen:
                new_files.append(
                    LocalFile(
                        path=os.path.abspath(entry.path),
                        name=entry.name,
                        size_bytes=st.st_size,
                    )
                )

    new_files.sort(key=lambda f: f.name)
    return new_files, json.dumps(sorted(all_keys))


def download(file: "LocalFile", dest_dir: str | None = None) -> str:
    """The file is already local — return its path (or copy to ``dest_dir``).

    Parity with the Dropbox client: if INGEST_DOWNLOAD_DIR / ``dest_dir`` is set,
    copy there; otherwise process in place.
    """
    src = os.path.abspath(file.path)
    dest_dir = dest_dir or os.getenv("INGEST_DOWNLOAD_DIR")
    if not dest_dir:
        return src
    os.makedirs(dest_dir, exist_ok=True)
    dst = os.path.join(dest_dir, file.name)
    if os.path.abspath(dst) != src:
        import shutil  # lazy, stdlib

        shutil.copy2(src, dst)
    return os.path.abspath(dst)
