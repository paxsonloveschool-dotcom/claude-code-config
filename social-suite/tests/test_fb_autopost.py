"""Tests for the Facebook auto-poster slot logic (pure; no network)."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from automation.fb_autopost import next_slots  # noqa: E402

MON = datetime(2026, 7, 6, 18, 0, tzinfo=timezone.utc)  # a Monday, 18:00 UTC


def test_slots_are_mon_wed_fri_sat_at_post_hour():
    slots = next_slots(MON, 6)
    # Mon 16:00 already passed (it's 18:00), so: Wed, Fri, Sat, Mon, Wed, Fri.
    assert [d.weekday() for d in slots] == [2, 4, 5, 0, 2, 4]
    assert all(d.hour == 16 and d.minute == 0 for d in slots)
    assert all(d > MON for d in slots)
    assert slots == sorted(slots)


def test_slots_capped_by_horizon_and_count():
    assert len(next_slots(MON, 3)) == 3
    # Even asking for a huge count, the ~4-week horizon caps it.
    assert len(next_slots(MON, 999)) <= 18


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
