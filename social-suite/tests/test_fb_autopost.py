"""Tests for the Facebook next-number poster (pure; no network)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from automation.fb_autopost import clip_number, next_clip  # noqa: E402


@dataclass
class F:
    name: str


def test_clip_number_parses_leading_number():
    assert clip_number("1.mp4") == 1
    assert clip_number("10.mp4") == 10
    assert clip_number("4 talk.mp4") == 4
    assert clip_number("12 song.MOV") == 12
    assert clip_number("intro.mp4") is None  # unnumbered clips are skipped


def test_next_clip_picks_smallest_number_above_last():
    files = [F("10.mp4"), F("2.mp4"), F("1.mp4"), F("4 talk.mp4")]
    num, f = next_clip(files, 0)
    assert (num, f.name) == (1, "1.mp4")
    num, f = next_clip(files, 2)
    assert (num, f.name) == (4, "4 talk.mp4")   # numeric: 4 before 10
    num, f = next_clip(files, 10)
    assert (num, f) == (None, None)             # nothing above 10 yet


def test_next_clip_survives_renames_and_gaps():
    # Owner replaced/renamed files — only the leading numbers matter.
    files = [F("3 new version.mp4"), F("7.mp4")]
    num, f = next_clip(files, 2)
    assert (num, f.name) == (3, "3 new version.mp4")
    num, f = next_clip(files, 3)
    assert (num, f.name) == (7, "7.mp4")        # gaps are fine


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
