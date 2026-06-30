"""Stamp spread-out posting times onto approved posts, per brand.

The flow:
  Dropbox video -> pipeline makes review clips (status "review", schedule null)
  -> you APPROVE the keepers (flip status -> "pending")
  -> THIS script stamps each pending-but-unscheduled post onto that brand's next
     weekly slot, so they drip out on a set cadence instead of all firing at once
  -> the cron poster (run_due) fires each one when its scheduled time arrives.

Edit ``BRAND_SCHEDULE`` to control "when and how often" each brand posts. Times
are UTC (TikTok/Meta schedule in UTC); the comments show the ~ET equivalent.

Idempotent: a post that already has a ``schedule`` (or isn't ``pending``) is left
untouched, so re-running never reshuffles or double-books anything. Pure stdlib.

Usage:
    python automation/schedule_queue.py            # stamp times, write queue
    python automation/schedule_queue.py --dry-run  # show what it would set
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE_PATH = os.path.join(os.path.dirname(HERE), "content", "queue.json")

# Per-brand weekly posting slots: (weekday, hour, minute) in UTC.
# weekday: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun.
# Default = 3x/week (NOT daily). 14:00 UTC ≈ 9am ET, 17:00 UTC ≈ 12pm ET (summer).
# >>> EDIT THESE to change when/how often each brand posts. <<<
BRAND_SCHEDULE: dict[str, list[tuple[int, int, int]]] = {
    "hp":      [(0, 14, 0), (2, 14, 0), (4, 14, 0)],   # Mon / Wed / Fri, ~9am ET
    "restore": [(1, 17, 0), (3, 17, 0)],               # Tue / Thu, ~12pm ET
}
# Brands with no entry above fall back to this (3x/week, late morning ET).
DEFAULT_SCHEDULE: list[tuple[int, int, int]] = [(0, 15, 0), (2, 15, 0), (4, 15, 0)]


def upcoming_slots(weekly: list[tuple[int, int, int]], start: datetime, count: int) -> list[datetime]:
    """Return the next ``count`` slot datetimes (UTC, strictly after ``start``).

    ``weekly`` is a list of (weekday, hour, minute). Walks forward day by day and
    collects each matching slot in chronological order. Pure function.
    """
    if not weekly or count <= 0:
        return []
    out: list[datetime] = []
    base = start.date()
    horizon = count * 7 + 14  # enough days to cover `count` slots comfortably
    for offset in range(horizon):
        day = base + timedelta(days=offset)
        for wd, hh, mm in sorted(weekly):
            if wd == day.weekday():
                dt = datetime(day.year, day.month, day.day, hh, mm, tzinfo=timezone.utc)
                if dt > start:
                    out.append(dt)
    out.sort()
    return out[:count]


def assign(posts: list[dict], now: datetime | None = None) -> int:
    """Stamp schedules onto pending, unscheduled posts in place. Returns # stamped.

    Per brand, finds posts that are ``status == "pending"`` with no ``schedule``,
    keeps their existing order, and drops them onto that brand's upcoming slots.
    """
    now = now or datetime.now(timezone.utc)
    # Group the posts that still need a time, by brand, preserving order.
    need: dict[str, list[dict]] = {}
    for p in posts:
        if p.get("status") == "pending" and not p.get("schedule"):
            need.setdefault((p.get("brand") or "default"), []).append(p)

    stamped = 0
    for brand, brand_posts in need.items():
        weekly = BRAND_SCHEDULE.get(brand, DEFAULT_SCHEDULE)
        slots = upcoming_slots(weekly, now, len(brand_posts))
        for post, slot in zip(brand_posts, slots):
            post["schedule"] = slot.isoformat().replace("+00:00", "Z")
            stamped += 1
    return stamped


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Stamp drip-schedule times on approved posts.")
    parser.add_argument("--dry-run", action="store_true", help="Print, don't write.")
    args = parser.parse_args(argv)

    if not os.path.exists(QUEUE_PATH):
        print(f"No queue at {QUEUE_PATH} — nothing to schedule.")
        return 0
    with open(QUEUE_PATH, encoding="utf-8") as f:
        posts = json.load(f)

    n = assign(posts)
    if args.dry_run:
        for p in posts:
            if p.get("status") == "pending":
                print(f"  {p.get('brand')}/{p.get('id')} -> {p.get('schedule')}")
        print(f"[dry-run] would stamp {n} post(s).")
        return 0

    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Stamped {n} approved post(s) onto their brand's drip schedule.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
