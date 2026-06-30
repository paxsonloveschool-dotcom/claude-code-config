"""Tests for the browser-autopost helpers (pure functions; no network/browser)."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from automation.tiktok_browser_post import split_caption, _schedule_parts, _targets  # noqa: E402


def test_split_caption_pulls_hashtags_out():
    text = "This is what happens. ✨\n\nCall (979) 777-8851!!\n•\n•\n#fyp #LandscapingTok #Bryan"
    desc, tags = split_caption(text)
    assert tags == ["#fyp", "#LandscapingTok", "#Bryan"]
    assert "#" not in desc
    assert "This is what happens" in desc
    assert "979" in desc
    # The bullet-only decoration lines are dropped.
    assert "•" not in desc


def test_schedule_parts_future_and_immediate():
    future = (datetime.now(timezone.utc) + timedelta(days=2)).replace(microsecond=0)
    iso = future.isoformat().replace("+00:00", "Z")
    hh_mm, day = _schedule_parts(iso)
    assert hh_mm == future.strftime("%H:%M")
    assert day == future.day
    # None / empty / past -> immediate (None, None).
    assert _schedule_parts(None) == (None, None)
    assert _schedule_parts("") == (None, None)
    assert _schedule_parts("2000-01-01T00:00:00Z") == (None, None)


def test_targets_filters_pending_tiktok_for_brand():
    posts = [
        {"id": "a", "brand": "hp", "status": "pending", "platforms": ["tiktok"]},
        {"id": "b", "brand": "hp", "status": "review", "platforms": ["tiktok"]},
        {"id": "c", "brand": "hp", "status": "pending", "platforms": ["instagram"]},
        {"id": "d", "brand": "restore", "status": "pending", "platforms": ["tiktok"]},
    ]
    ids = [p["id"] for p in _targets(posts, "hp", None)]
    assert ids == ["a"]  # only approved + tiktok + right brand
    # --once bypasses status/brand/platform filters.
    assert [p["id"] for p in _targets(posts, "hp", "d")] == ["d"]


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
