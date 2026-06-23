"""Tests for Dropbox path -> brand routing. No network."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.ingest.routing import brand_for_path  # noqa: E402


def test_top_folder_is_the_brand_lowercased():
    assert brand_for_path("/HP/clip.mp4") == "hp"
    assert brand_for_path("/Restore/promo.mov") == "restore"


def test_nested_paths_use_the_top_folder():
    assert brand_for_path("/HP/2026/june/x.mp4") == "hp"
    assert brand_for_path("Restore/sub/y.mov") == "restore"  # no leading slash


def test_bare_filename_is_default():
    assert brand_for_path("clip.mp4") == "default"
    assert brand_for_path("") == "default"


def test_separators_and_whitespace_normalised():
    assert brand_for_path("\\HP\\clip.mp4") == "hp"  # backslashes
    assert brand_for_path("/  HP  /clip.mp4") == "hp"  # stray spaces trimmed


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
