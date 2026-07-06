"""Tests for the browser-autopost helpers (pure functions; no network/browser)."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from automation.tiktok_browser_post import (  # noqa: E402
    split_caption, next_post_slots, plan, _targets,
)

WED_9AM = datetime(2026, 7, 1, 9, 0)  # a Wednesday, before 10am


def test_split_caption_pulls_hashtags_out():
    text = "This is what happens. ✨\n\nCall (979) 777-8851!!\n•\n•\n#fyp #LandscapingTok #Bryan"
    desc, tags = split_caption(text)
    assert tags == ["#fyp", "#LandscapingTok", "#Bryan"]
    assert "#" not in desc and "•" not in desc
    assert "This is what happens" in desc and "979" in desc


def test_next_post_slots_are_mwf_noon_future_within_window():
    slots = next_post_slots(WED_9AM, 4)
    # Today is Wed 9am -> today's 12:00 still counts, then Fri, Mon, Wed.
    assert [d.weekday() for d in slots] == [2, 4, 0, 2]
    assert all(d > WED_9AM for d in slots)
    assert all(d.hour == 12 and d.minute == 0 for d in slots)
    # 10-day horizon caps the count even if more are requested.
    assert len(next_post_slots(WED_9AM, 99)) <= 5


def test_plan_cycles_songs_and_assigns_slots():
    posts = [
        {"id": "a", "brand": "hp", "status": "pending", "platforms": ["tiktok"], "text": "x"},
        {"id": "b", "brand": "hp", "status": "pending", "platforms": ["tiktok"], "text": "y"},
    ]
    songs = ["Song One", "Song Two", "Song Three"]
    out = plan(posts, songs, WED_9AM)
    assert [i["sound"] for i in out] == ["Song One", "Song Two"]  # cycled in order
    assert out[0]["slot"] < out[1]["slot"]                        # different, ordered slots
    assert out[0]["slot"].hour == 12


def test_plan_respects_explicit_sound_and_schedule():
    posts = [
        {"id": "a", "status": "pending", "platforms": ["tiktok"], "text": "x",
         "sound": "My Own Song", "schedule": "2026-07-03T10:00:00Z"},
    ]
    out = plan(posts, ["Rotation Song"], WED_9AM)
    assert out[0]["sound"] == "My Own Song"          # explicit sound kept
    assert out[0]["slot"] == datetime(2026, 7, 3, 10, 0)  # explicit schedule kept


def test_targets_filters_pending_tiktok_for_brand():
    posts = [
        {"id": "a", "brand": "hp", "status": "pending", "platforms": ["tiktok"]},
        {"id": "b", "brand": "hp", "status": "review", "platforms": ["tiktok"]},
        {"id": "c", "brand": "hp", "status": "pending", "platforms": ["instagram"]},
        {"id": "d", "brand": "restore", "status": "pending", "platforms": ["tiktok"]},
    ]
    assert [p["id"] for p in _targets(posts, "hp", None)] == ["a"]
    assert [p["id"] for p in _targets(posts, "hp", "d")] == ["d"]  # --once bypasses filters


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
