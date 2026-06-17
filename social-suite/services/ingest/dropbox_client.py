"""Dropbox watch + download.

Watches a Dropbox folder for newly uploaded raw videos and pulls them to local
disk so downstream stages (clip, caption) can operate on a file path.

TODO(impl): fill in with the Dropbox SDK (`dropbox`).
    - Auth: prefer the refresh-token flow (DROPBOX_APP_KEY/SECRET/REFRESH_TOKEN)
      so an always-on watcher never expires; DROPBOX_ACCESS_TOKEN works for dev.
    - list_new_files(): use `files_list_folder` + a persisted cursor, then
      `files_list_folder_continue` for cheap delta polling.
    - download(): `files_download_to_file` into INGEST_DOWNLOAD_DIR.
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


def list_new_files(cursor: str | None = None) -> tuple[list[DropboxFile], str | None]:
    """List raw videos added to the watch folder since ``cursor``.

    Args:
        cursor: Opaque Dropbox delta cursor from a previous call, or None for a
            full initial listing.

    Returns:
        (files, next_cursor): newly seen files and the cursor to pass next time.

    TODO(impl): Dropbox SDK — files_list_folder / files_list_folder_continue.
    """
    _ = os.getenv("DROPBOX_WATCH_FOLDER", "/raw-video")
    raise NotImplementedError("Wire to Dropbox SDK: files_list_folder + cursor delta.")


def download(file: DropboxFile, dest_dir: str | None = None) -> str:
    """Download a Dropbox file to local disk.

    Args:
        file: The file to fetch (from ``list_new_files``).
        dest_dir: Local directory; defaults to INGEST_DOWNLOAD_DIR.

    Returns:
        Absolute local path to the downloaded video.

    TODO(impl): Dropbox SDK — files_download_to_file.
    """
    _ = dest_dir or os.getenv("INGEST_DOWNLOAD_DIR", "./media/ingest")
    raise NotImplementedError("Wire to Dropbox SDK: files_download_to_file.")
