"""Dropbox watch + download.

Watches a Dropbox folder for newly uploaded raw videos and pulls them to local
disk so downstream stages (clip, caption) can operate on a file path.

Auth uses the refresh-token flow so an always-on watcher never expires:
``DROPBOX_APP_KEY`` + ``DROPBOX_APP_SECRET`` + ``DROPBOX_REFRESH_TOKEN``
(falls back to a short-lived ``DROPBOX_ACCESS_TOKEN`` for dev).

Listing uses ``files_list_folder`` for the initial pass and
``files_list_folder_continue`` for cheap cursor-based deltas afterward. To watch
without polling tightly, pass the cursor to ``files_list_folder_longpoll`` and
only call ``_continue`` when it reports changes (see ``longpoll``).

The ``dropbox`` SDK is imported lazily inside each function so this module
imports cleanly without the SDK installed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class DropboxFile:
    """A file discovered in the watched Dropbox folder.

    Attributes:
        path: Full Dropbox path (e.g. "/raw-video/clip.mov").
        name: Base filename.
        size_bytes: File size in bytes (0 if unknown).
        rev: Dropbox revision id — use to dedupe already-processed files.
    """

    path: str
    name: str
    size_bytes: int = 0
    rev: str = ""


def _client():
    """Construct an authenticated Dropbox client (refresh-token preferred)."""
    import dropbox  # lazy: keep module import dep-free

    app_key = os.getenv("DROPBOX_APP_KEY")
    app_secret = os.getenv("DROPBOX_APP_SECRET")
    refresh_token = os.getenv("DROPBOX_REFRESH_TOKEN")
    access_token = os.getenv("DROPBOX_ACCESS_TOKEN")

    if refresh_token and app_key and app_secret:
        return dropbox.Dropbox(
            oauth2_refresh_token=refresh_token,
            app_key=app_key,
            app_secret=app_secret,
        )
    if access_token:
        return dropbox.Dropbox(oauth2_access_token=access_token)
    raise RuntimeError(
        "Set DROPBOX_APP_KEY/DROPBOX_APP_SECRET/DROPBOX_REFRESH_TOKEN "
        "(or DROPBOX_ACCESS_TOKEN) to authenticate Dropbox."
    )


def _retry_after_seconds(exc: Exception) -> float | None:
    """Extract a Dropbox rate-limit backoff (seconds) from an exception, if any.

    Dropbox raises ``dropbox.exceptions.RateLimitError`` (HTTP 429) carrying
    ``backoff`` / ``retry_after``. We detect it duck-typed so the SDK never has
    to be imported at module level. Returns None when ``exc`` is not a rate limit.
    """
    if type(exc).__name__ != "RateLimitError":
        return None
    for attr in ("backoff", "retry_after"):
        val = getattr(exc, attr, None)
        if val is not None:
            try:
                return max(0.0, float(val))
            except (TypeError, ValueError):
                pass
    return 0.0  # rate-limited but no hint — caller applies a default


def _call_with_retry(fn, *args, _max_retries: int = 5, **kwargs):
    """Call ``fn``; on a Dropbox 429 sleep for Retry-After and retry."""
    import time  # lazy, stdlib

    attempt = 0
    while True:
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            wait = _retry_after_seconds(exc)
            if wait is None or attempt >= _max_retries:
                raise
            time.sleep(wait if wait > 0 else 1.0)
            attempt += 1


def _to_files(entries) -> list[DropboxFile]:
    """Map raw SDK entries to ``DropboxFile``, keeping only actual files."""
    files: list[DropboxFile] = []
    for entry in entries:
        # FileMetadata has size/rev; FolderMetadata/DeletedMetadata do not.
        if not hasattr(entry, "rev"):
            continue
        files.append(
            DropboxFile(
                path=getattr(entry, "path_display", "") or getattr(entry, "path_lower", ""),
                name=getattr(entry, "name", ""),
                size_bytes=int(getattr(entry, "size", 0) or 0),
                rev=getattr(entry, "rev", "") or "",
            )
        )
    return files


def list_new_files(cursor: str | None = None) -> tuple[list[DropboxFile], str | None]:
    """List raw videos added to the watch folder since ``cursor``.

    Args:
        cursor: Opaque Dropbox delta cursor from a previous call, or None for a
            full initial listing.

    Returns:
        (files, next_cursor): newly seen files and the cursor to pass next time.
    """
    dbx = _client()

    if cursor:
        result = _call_with_retry(dbx.files_list_folder_continue, cursor)
    else:
        folder = os.getenv("DROPBOX_WATCH_FOLDER", "/raw-video")
        result = _call_with_retry(dbx.files_list_folder, folder)

    files = _to_files(result.entries)

    # Drain pagination so the returned cursor reflects everything seen.
    while getattr(result, "has_more", False):
        result = _call_with_retry(dbx.files_list_folder_continue, result.cursor)
        files.extend(_to_files(result.entries))

    return files, getattr(result, "cursor", None)


def longpoll(cursor: str, timeout: int = 30) -> bool:
    """Block up to ``timeout`` seconds; return True if the folder has changes.

    Wraps ``files_list_folder_longpoll`` so a watcher can sleep cheaply and only
    call ``list_new_files(cursor)`` when this returns True. No inbound port.
    """
    dbx = _client()
    result = dbx.files_list_folder_longpoll(cursor, timeout=timeout)
    return bool(getattr(result, "changes", False))


def download(file: DropboxFile, dest_dir: str | None = None) -> str:
    """Download a Dropbox file to local disk.

    Args:
        file: The file to fetch (from ``list_new_files``).
        dest_dir: Local directory; defaults to INGEST_DOWNLOAD_DIR.

    Returns:
        Absolute local path to the downloaded video.
    """
    dest_dir = dest_dir or os.getenv("INGEST_DOWNLOAD_DIR", "./media/ingest")
    os.makedirs(dest_dir, exist_ok=True)
    local_path = os.path.join(dest_dir, file.name)

    dbx = _client()
    _call_with_retry(dbx.files_download_to_file, local_path, file.path)
    return os.path.abspath(local_path)
