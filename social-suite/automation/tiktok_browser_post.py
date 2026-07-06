"""Fully-automatic TikTok posting WITH a real (searched-by-name) sound.

The "no device, no official API" path: it drives a real browser logged in with
your cookies (via the open-source ``tiktokautouploader`` package) to upload each
approved video, write the caption + clickable hashtags, **search a TikTok sound
by name and attach it**, and **schedule** the post on TikTok's own scheduler.

Everyday flow (run ~weekly on the laptop, inside social-suite/):
    python automation/tiktok_browser_post.py --brand hp --dry-run   # preview
    python automation/tiktok_browser_post.py --brand hp             # do it

It reads ``content/queue.json`` — every approved post (``status == "pending"``)
whose ``platforms`` include ``"tiktok"``:
  * gets the next song from ``content/tiktok_songs_<brand>.txt`` (cycled in order,
    unless the post already has a ``"sound"``), and
  * gets the next Mon/Wed/Fri 10:00 (local) slot within TikTok's 10-day scheduling
    window (unless it already has a ``"schedule"``),
then uploads+schedules it and flips it to ``status == "scheduled"`` so re-runs
never double-post. Posts that don't fit in the 10-day window are left for the
next run (and logged).

⚠️ Automates TikTok against its ToS; test one post first. Runs on the laptop —
TikTok blocks datacenter IPs. See TIKTOK_BROWSER_AUTOPOST.md.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(os.path.dirname(HERE), "content")
QUEUE_PATH = os.path.join(CONTENT, "queue.json")

ACCOUNT_NAMES = {
    "hp": os.getenv("TIKTOK_HP_ACCOUNT", "hp"),
    "restore": os.getenv("TIKTOK_RESTORE_ACCOUNT", "restore"),
}

# 'background' (song quiet under the clip's own audio), 'mix' (both even), or
# 'main' (song replaces audio). 'mix' is the tested-reliable default.
SOUND_VOLUME = os.getenv("TIKTOK_SOUND_VOLUME", "mix")

# Posting cadence for auto-scheduling: Mon/Wed/Fri at 10:00 local time.
POST_WEEKDAYS = (0, 2, 4)  # Mon, Wed, Fri
POST_HOUR = 12  # noon (local)
POST_MINUTE = 0
# TikTok's native scheduler only accepts times within ~10 days out.
SCHEDULE_HORIZON_DAYS = 10


def load_songs(brand: str) -> list[str]:
    """Load the brand's song rotation (one 'Artist - Title' per line)."""
    path = os.path.join(CONTENT, f"tiktok_songs_{brand}.txt")
    if not os.path.exists(path):
        return []
    songs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                songs.append(line)
    return songs


def split_caption(text: str) -> tuple[str, list[str]]:
    """Split a combined caption into (description, [#hashtags]) for the uploader."""
    tags = re.findall(r"#\w+", text)
    desc = re.sub(r"#\w+", "", text)
    desc = "\n".join(ln for ln in desc.splitlines() if ln.strip() not in ("", "•", "·"))
    return desc.strip(), tags


def next_post_slots(now: datetime, count: int) -> list[datetime]:
    """Next ``count`` Mon/Wed/Fri 10:00 local slots, strictly future, ≤ horizon.

    Naive local datetimes (TikTok schedules in the account's local time). Capped
    at ``SCHEDULE_HORIZON_DAYS`` — so this may return fewer than ``count`` if the
    window fills up; callers leave the rest for the next run.
    """
    out: list[datetime] = []
    for offset in range(SCHEDULE_HORIZON_DAYS + 1):
        day = (now + timedelta(days=offset)).date()
        if day.weekday() in POST_WEEKDAYS:
            slot = datetime(day.year, day.month, day.day, POST_HOUR, POST_MINUTE)
            if slot > now and len(out) < count:
                out.append(slot)
    return out


def _slot_parts(slot: datetime) -> tuple[str, int]:
    """(HH:MM, day-of-month) for the tool's schedule/day params."""
    return slot.strftime("%H:%M"), slot.day


def _explicit_slot(iso: str) -> datetime | None:
    """Parse a post's own ISO schedule to a naive local datetime, if future."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None
    return dt


def _download(url: str) -> str:
    import urllib.request

    fd, path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    urllib.request.urlretrieve(url, path)  # noqa: S310 — our own Dropbox link
    return path


def _targets(posts: list[dict], brand: str, once: str | None) -> list[dict]:
    out = []
    for p in posts:
        if once:
            if p.get("id") == once:
                out.append(p)
            continue
        if p.get("brand") != brand or p.get("status") != "pending":
            continue
        if "tiktok" not in (p.get("platforms") or []):
            continue
        out.append(p)
    return out


def plan(targets: list[dict], songs: list[str], now: datetime) -> list[dict]:
    """Assign a song + a schedule slot to each target. Pure (no I/O).

    Returns a list of ``{"post", "sound", "slot"}`` for posts that fit the 10-day
    window; posts beyond the window are dropped from the plan (left for next run).
    """
    need_slots = sum(1 for p in targets if not p.get("schedule"))
    auto_slots = next_post_slots(now, need_slots)
    plan_out: list[dict] = []
    si = 0  # song index
    ai = 0  # auto-slot index
    for p in targets:
        sound = p.get("sound") or (songs[si % len(songs)] if songs else None)
        if not p.get("sound"):
            si += 1
        if p.get("schedule"):
            slot = _explicit_slot(p["schedule"])
        elif ai < len(auto_slots):
            slot = auto_slots[ai]
            ai += 1
        else:
            continue  # no slot left in the window — leave it for next run
        plan_out.append({"post": p, "sound": sound, "slot": slot})
    return plan_out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Browser-auto-post approved TikToks (song + schedule).")
    ap.add_argument("--brand", default="hp")
    ap.add_argument("--once", default=None, help="Post just this queue id.")
    ap.add_argument("--sound", default=None, help="Force this sound for every post this run.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    with open(QUEUE_PATH, encoding="utf-8") as f:
        posts = json.load(f)

    targets = _targets(posts, args.brand, args.once)
    if not targets:
        print("Nothing to post (no approved 'pending' TikTok items for this brand).")
        return 0

    songs = [args.sound] if args.sound else load_songs(args.brand)
    account = ACCOUNT_NAMES.get(args.brand, args.brand)
    items = plan(targets, songs, datetime.now())

    left = len(targets) - len(items)
    if left:
        print(f"NOTE: {left} post(s) don't fit the 10-day window — they'll go next run.")

    if not args.dry_run:
        try:
            from tiktokautouploader import upload_tiktok  # type: ignore
        except ImportError:
            print("ERROR: run `pip install tiktokautouploader` (+ `python3 -m phantomwright_driver install chromium`).")
            return 1

    done = 0
    for it in items:
        p, sound, slot = it["post"], it["sound"], it["slot"]
        desc, tags = split_caption(p.get("text", ""))
        hh_mm, day = _slot_parts(slot) if slot else (None, None)
        when = f"{slot:%a %b %d} {hh_mm}" if slot else "immediately"
        print(f"\n[{p.get('id')}] {account} | sound={sound!r} | {when}")
        print(f"  {desc[:70]!r}  {' '.join(tags)}")
        if args.dry_run:
            continue
        if not sound:
            print("  SKIP: no song (add songs to content/tiktok_songs_%s.txt)." % args.brand)
            continue

        video_path = _download(p["media_url"])
        try:
            kwargs = dict(
                video=video_path, description=desc, accountname=account,
                hashtags=tags, sound_name=sound, sound_aud_vol=SOUND_VOLUME,
                copyrightcheck=True, suppressprint=False,
            )
            if hh_mm and day:
                kwargs.update(schedule=hh_mm, day=day)
            upload_tiktok(**kwargs)  # noqa
        finally:
            try:
                os.remove(video_path)
            except OSError:
                pass

        p["status"] = "scheduled"
        done += 1
        with open(QUEUE_PATH, "w", encoding="utf-8") as f:
            json.dump(posts, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print("  OK")

    print(f"\nDone: {done} post(s) {'planned' if args.dry_run else 'uploaded/scheduled'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
