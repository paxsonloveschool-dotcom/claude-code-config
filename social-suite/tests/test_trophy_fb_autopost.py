"""Tests for the Trophy Facebook next-number poster (pure; no network)."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from automation.trophy_fb_autopost import (  # noqa: E402
    FOLDER,
    POST_WEEKDAYS,
    clip_number,
    next_clip,
)


@dataclass
class F:
    name: str


def test_posts_only_from_trophy_social_auto():
    assert FOLDER == "/TROPHY EXTERIOR/Trophy Social Auto"


def test_weekday_schedule_is_mon_to_fri():
    assert POST_WEEKDAYS == (0, 1, 2, 3, 4)


def test_clip_number_parses_leading_number():
    assert clip_number("1.mp4") == 1
    assert clip_number("10.mp4") == 10
    assert clip_number("4 talk.mp4") == 4
    assert clip_number("reel-resort.mp4") is None  # unnumbered clips are skipped


def test_next_clip_picks_smallest_number_above_last():
    files = [F("10.mp4"), F("2.mp4"), F("1.mp4"), F("4 talk.mp4")]
    num, f = next_clip(files, 0)
    assert (num, f.name) == (1, "1.mp4")
    num, f = next_clip(files, 2)
    assert (num, f.name) == (4, "4 talk.mp4")   # numeric: 4 before 10
    num, f = next_clip(files, 10)
    assert (num, f) == (None, None)             # nothing above 10 yet


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
