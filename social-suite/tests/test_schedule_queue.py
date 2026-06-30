"""Tests for the drip-schedule stamper (no network/Dropbox needed)."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from automation.schedule_queue import assign, upcoming_slots  # noqa: E402

MON_NOON = datetime(2026, 6, 29, 12, 0, tzinfo=timezone.utc)  # a Monday
MWF = [(0, 14, 0), (2, 14, 0), (4, 14, 0)]  # Mon/Wed/Fri 14:00 UTC


def test_upcoming_slots_are_in_order_and_future():
    slots = upcoming_slots(MWF, MON_NOON, 4)
    assert [d.weekday() for d in slots] == [0, 2, 4, 0]  # Mon, Wed, Fri, Mon
    assert all(d > MON_NOON for d in slots)
    assert slots == sorted(slots)


def test_assign_spreads_pending_posts():
    posts = [
        {"id": "a", "brand": "hp", "status": "pending", "schedule": None},
        {"id": "b", "brand": "hp", "status": "pending", "schedule": None},
    ]
    n = assign(posts, now=MON_NOON)
    assert n == 2
    assert posts[0]["schedule"] != posts[1]["schedule"]  # different days
    assert posts[0]["schedule"].endswith("Z")


def test_assign_skips_unapproved_and_already_scheduled():
    posts = [
        {"id": "review", "brand": "hp", "status": "review", "schedule": None},
        {"id": "set", "brand": "hp", "status": "pending", "schedule": "2026-07-01T00:00:00Z"},
    ]
    n = assign(posts, now=MON_NOON)
    assert n == 0
    assert posts[0]["schedule"] is None          # review item untouched
    assert posts[1]["schedule"] == "2026-07-01T00:00:00Z"  # existing time kept


def test_brands_scheduled_independently():
    posts = [
        {"id": "h", "brand": "hp", "status": "pending", "schedule": None},
        {"id": "r", "brand": "restore", "status": "pending", "schedule": None},
    ]
    assign(posts, now=MON_NOON)
    assert posts[0]["schedule"] and posts[1]["schedule"]
