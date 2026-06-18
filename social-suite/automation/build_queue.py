"""Merge each brand's content file into one scheduled ``content/queue.json``.

The per-brand files (``content/hp-content.json``, ``content/restore-content.json``,
…) are the human-edited source of truth — each post already tagged with its
``brand`` so content can only ever go to that brand's own accounts. This script
fans them into the single ``queue.json`` the cron poster reads, stamping a
spread-out ``schedule`` so posts trickle out instead of firing all at once.

Scheduling scheme (simple, predictable):
  * The FIRST pending post of each brand is left ``schedule = null`` → it posts on
    the very next run (instant proof the pipeline works).
  * Every following post is stamped one-per-day at that brand's daily time slot,
    starting tomorrow (UTC). Brands use staggered slots so two posts never land
    on the exact same minute.

Re-running is safe: it rebuilds the queue from the brand files, preserving the
``status``/``error`` of any post id already present in the existing queue (so a
post already ``sent`` is never re-posted). Pure stdlib, no network.

Usage:
    python automation/build_queue.py            # build content/queue.json
    python automation/build_queue.py --dry-run  # print what it would write
"""

from __future__ import annotations

import glob
import json
import os
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(os.path.dirname(HERE), "content")
QUEUE_PATH = os.path.join(CONTENT_DIR, "queue.json")

# Per-brand daily UTC time slot (HH, MM). Staggered so posts don't collide.
# 13:00 UTC ≈ 9am ET, 16:00 UTC ≈ 12pm ET (summer). Unknown brands get a
# deterministic fallback slot derived from their name.
BRAND_SLOTS = {
    "hp": (13, 0),
    "restore": (16, 0),
}
FIELDS = ("id", "text", "media_url", "platforms", "schedule", "brand", "status", "error")


def _content_files() -> list[str]:
    """Every ``*-content.json`` in the content dir, sorted for stable order."""
    return sorted(glob.glob(os.path.join(CONTENT_DIR, "*-content.json")))


def _load_existing_status() -> dict[str, dict]:
    """Map post id -> {status, error} from the current queue, if any."""
    if not os.path.exists(QUEUE_PATH):
        return {}
    with open(QUEUE_PATH, encoding="utf-8") as f:
        raw = f.read().strip()
    if not raw:
        return {}
    out: dict[str, dict] = {}
    for p in json.loads(raw):
        if "id" in p:
            out[p["id"]] = {"status": p.get("status", "pending"), "error": p.get("error")}
    return out


def _slot_for(brand: str) -> tuple[int, int]:
    if brand in BRAND_SLOTS:
        return BRAND_SLOTS[brand]
    # Deterministic fallback: spread unknown brands across the workday (10–18 UTC).
    h = 10 + (sum(ord(c) for c in brand) % 9)
    return (h, 0)


def build(now: datetime | None = None) -> list[dict]:
    """Return the merged, scheduled queue as a list of post dicts."""
    now = now or datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).date()
    existing = _load_existing_status()

    # Group posts by brand, preserving file order.
    by_brand: dict[str, list[dict]] = {}
    for path in _content_files():
        with open(path, encoding="utf-8") as f:
            for post in json.load(f):
                by_brand.setdefault(post.get("brand", "default"), []).append(post)

    queue: list[dict] = []
    for brand in sorted(by_brand):
        hh, mm = _slot_for(brand)
        day_index = 0
        for i, post in enumerate(by_brand[brand]):
            pid = post["id"]
            prior = existing.get(pid, {})
            status = prior.get("status", "pending")

            # Don't reschedule posts that already went out (or hard-failed).
            if status in ("sent", "failed"):
                schedule = post.get("schedule")
            elif i == 0:
                schedule = None  # first pending post of the brand → post now
            else:
                when = datetime(
                    tomorrow.year, tomorrow.month, tomorrow.day, hh, mm,
                    tzinfo=timezone.utc,
                ) + timedelta(days=day_index)
                schedule = when.isoformat().replace("+00:00", "Z")
                day_index += 1

            queue.append({
                "id": pid,
                "text": post["text"],
                "media_url": post.get("media_url"),
                "platforms": post.get("platforms", ["facebook"]),
                "schedule": schedule,
                "brand": brand,
                "status": status,
                "error": prior.get("error"),
            })
    return queue


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Build content/queue.json from per-brand files.")
    parser.add_argument("--dry-run", action="store_true", help="Print, don't write.")
    args = parser.parse_args(argv)

    queue = build()
    text = json.dumps(queue, indent=2, ensure_ascii=False) + "\n"
    if args.dry_run:
        print(text)
        print(f"[dry-run] {len(queue)} posts across "
              f"{len({p['brand'] for p in queue})} brands (not written).")
        return 0

    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        f.write(text)
    immediate = sum(1 for p in queue if p["schedule"] is None and p["status"] == "pending")
    print(f"Wrote {QUEUE_PATH}: {len(queue)} posts, {immediate} post now, rest scheduled daily.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
