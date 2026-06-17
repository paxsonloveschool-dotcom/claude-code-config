#!/usr/bin/env python3
"""Turn a flat content file into a scheduled posting calendar.

Reads a content JSON (the format used by schedule_posts.py) and stamps each
post with a `schedule` datetime spread across the weekdays/time you choose, so
posts drip out instead of firing all at once. Optionally fills in channel ids
so you don't hand-edit the file. Stdlib only.

Example — schedule every Mon/Wed/Fri at 9am, starting next Monday, to one
channel, writing a ready-to-send file:

  python3 plan_calendar.py content/hp-landscaping.json \\
      --days mon,wed,fri --time 09:00 --channels abc123 \\
      --out planned-hp.json

Then send it:
  python3 schedule_posts.py planned-hp.json
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3,
            "fri": 4, "sat": 5, "sun": 6}


def parse_days(s):
    days = []
    for part in s.split(","):
        key = part.strip().lower()[:3]
        if key not in WEEKDAYS:
            sys.exit(f"Error: unknown day '{part}'. Use mon,tue,wed,thu,fri,sat,sun.")
        days.append(WEEKDAYS[key])
    return sorted(set(days))


def slot_generator(start_date, weekdays, hour, minute, tz):
    """Yield successive datetimes on the chosen weekdays at the given time."""
    day = start_date
    while True:
        if day.weekday() in weekdays:
            yield datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
        day += timedelta(days=1)


def main():
    p = argparse.ArgumentParser(description="Build a posting calendar from a content file.")
    p.add_argument("content_file", help="Input content JSON.")
    p.add_argument("--days", default="mon,wed,fri", help="Posting weekdays, e.g. mon,wed,fri.")
    p.add_argument("--time", default="09:00", help="Local time of day HH:MM (24h).")
    p.add_argument("--start", default=None, help="Start date YYYY-MM-DD (default: tomorrow).")
    p.add_argument("--utc-offset", type=int, default=0,
                   help="Hours offset from UTC for --time (e.g. -4 for EDT). Default 0 (UTC).")
    p.add_argument("--channels", default=None,
                   help="Comma-separated integration ids; overrides each post's channels.")
    p.add_argument("--out", default=None, help="Output file (default: stdout).")
    args = p.parse_args()

    try:
        hour, minute = (int(x) for x in args.time.split(":"))
    except ValueError:
        sys.exit("Error: --time must be HH:MM, e.g. 09:00")

    tz = timezone(timedelta(hours=args.utc_offset))
    if args.start:
        try:
            d = datetime.strptime(args.start, "%Y-%m-%d")
            start = datetime(d.year, d.month, d.day)
        except ValueError:
            sys.exit("Error: --start must be YYYY-MM-DD")
    else:
        start = datetime.utcnow() + timedelta(days=1)
    start = datetime(start.year, start.month, start.day)

    weekdays = parse_days(args.days)
    channels = [c.strip() for c in args.channels.split(",")] if args.channels else None

    with open(args.content_file, encoding="utf-8") as fh:
        posts = json.load(fh)
    if not isinstance(posts, list):
        sys.exit("Error: content file must be a JSON array of posts.")

    slots = slot_generator(start, weekdays, hour, minute, tz)
    for post in posts:
        when = next(slots)
        post["schedule"] = when.strftime("%Y-%m-%dT%H:%M:%S%z")
        # normalise +0000 -> Z style is optional; Postiz accepts offset form.
        if channels:
            post["channels"] = list(channels)

    out_json = json.dumps(posts, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out_json + "\n")
        first = posts[0]["schedule"] if posts else "n/a"
        last = posts[-1]["schedule"] if posts else "n/a"
        print(f"Wrote {len(posts)} scheduled posts to {args.out}")
        print(f"  first: {first}\n  last:  {last}")
    else:
        print(out_json)


if __name__ == "__main__":
    main()
