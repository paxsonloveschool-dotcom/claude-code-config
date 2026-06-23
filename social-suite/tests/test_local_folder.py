"""Tests for the local-folder ingest (no network, no deps)."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.ingest import local_folder  # noqa: E402


def _make(folder, name, data=b"x"):
    p = Path(folder) / name
    p.write_bytes(data)
    return p


def test_lists_only_videos():
    with tempfile.TemporaryDirectory() as d:
        _make(d, "a.mp4"); _make(d, "b.mov"); _make(d, "notes.txt"); _make(d, "c.MP4")
        files, cursor = local_folder.list_new_files(folder=d)
        names = sorted(f.name for f in files)
        assert names == ["a.mp4", "b.mov", "c.MP4"]  # .txt excluded, case-insensitive
        assert cursor  # non-empty JSON cursor


def test_cursor_dedupes_already_seen():
    with tempfile.TemporaryDirectory() as d:
        _make(d, "a.mp4")
        files1, cursor1 = local_folder.list_new_files(folder=d)
        assert len(files1) == 1
        # Second pass with the returned cursor: nothing new.
        files2, _ = local_folder.list_new_files(cursor=cursor1, folder=d)
        assert files2 == []
        # A new file shows up; old one stays suppressed.
        _make(d, "b.mp4")
        files3, _ = local_folder.list_new_files(cursor=cursor1, folder=d)
        assert [f.name for f in files3] == ["b.mp4"]


def test_bad_cursor_is_ignored():
    with tempfile.TemporaryDirectory() as d:
        _make(d, "a.mp4")
        files, _ = local_folder.list_new_files(cursor="not-json", folder=d)
        assert [f.name for f in files] == ["a.mp4"]


def test_download_in_place_returns_path():
    with tempfile.TemporaryDirectory() as d:
        p = _make(d, "a.mp4")
        files, _ = local_folder.list_new_files(folder=d)
        out = local_folder.download(files[0])  # no dest_dir -> in place
        assert os.path.abspath(out) == os.path.abspath(str(p))


def test_download_copies_to_dest_dir():
    with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as dest:
        _make(d, "a.mp4", b"hello")
        files, _ = local_folder.list_new_files(folder=d)
        out = local_folder.download(files[0], dest_dir=dest)
        assert os.path.dirname(os.path.abspath(out)) == os.path.abspath(dest)
        assert Path(out).read_bytes() == b"hello"


def _run():
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  PASS {name}")
            passed += 1
    print(f"\n{passed} tests passed.")


if __name__ == "__main__":
    _run()
