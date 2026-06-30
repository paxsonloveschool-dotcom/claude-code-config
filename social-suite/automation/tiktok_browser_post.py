"""Fully-automatic TikTok posting WITH a real (searched-by-name) sound.

This is the "no device, no official API" path: it drives a real browser logged
in with your cookies (via the open-source ``tiktokautouploader`` package, which
uses Phantomwright for bot-detection evasion) to upload the video, write the
caption + clickable hashtags, **search a TikTok sound by name and attach it**,
and schedule the post with TikTok's own scheduler (so the laptop doesn't need to
stay on after queuing).

It reads the SAME queue the rest of the suite uses (``content/queue.json``):
every approved post (``status == "pending"``) whose ``platforms`` include
``"tiktok"`` gets uploaded+scheduled, then flipped to ``status == "scheduled"``
so re-running never double-posts.

Where it runs: on YOUR laptop (needs a browser + your residential IP + a one-time
TikTok login per account). It canNOT run from the CI sandbox — TikTok blocks
datacenter IPs and an un-cookied browser. See TIKTOK_BROWSER_AUTOPOST.md.

⚠️ This automates TikTok against its ToS, and mainstream music on a Business
account may be blocked by TikTok's copyright check. Test ONE post first.

Usage (on the laptop, inside social-suite/):
    python automation/tiktok_browser_post.py --brand hp --dry-run   # show plan
    python automation/tiktok_browser_post.py --brand hp             # do it
    python automation/tiktok_browser_post.py --brand hp --once <id>  # one post
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
QUEUE_PATH = os.path.join(os.path.dirname(HERE), "content", "queue.json")

# Brand key -> the ``accountname`` label tiktokautouploader uses for the cookie
# file (Tk_cookies_<accountname>.json). Override per brand via env if you like.
ACCOUNT_NAMES = {
    "hp": os.getenv("TIKTOK_HP_ACCOUNT", "hp"),
    "restore": os.getenv("TIKTOK_RESTORE_ACCOUNT", "restore"),
}

# How the chosen song sits under the clip: 'background' (song quiet under the
# video's own audio), 'mix' (both even), or 'main' (song replaces the audio).
SOUND_VOLUME = os.getenv("TIKTOK_SOUND_VOLUME", "background")


def split_caption(text: str) -> tuple[str, list[str]]:
    """Split our combined caption into (description, [#hashtags]).

    The queue stores caption + hashtags as one blob; the uploader wants the tags
    as a separate list to make them clickable. Pull every ``#tag`` out, keep the
    prose (minus the tag block) as the description.
    """
    tags = re.findall(r"#\w+", text)
    # Drop the hashtags (and any now-empty bullet/decoration lines) from prose.
    desc = re.sub(r"#\w+", "", text)
    desc = "\n".join(ln for ln in desc.splitlines() if ln.strip() not in ("", "•", "·"))
    return desc.strip(), tags


def _schedule_parts(iso: str | None) -> tuple[str | None, int | None]:
    """Map an ISO time (e.g. '2026-07-01T14:00:00Z') to (HH:MM, day-of-month).

    TikTok's native scheduler accepts a time + day up to ~10 days out. Returns
    (None, None) for an immediate post (no/empty/past schedule). The time is
    interpreted by TikTok in the ACCOUNT's local timezone — see the setup doc.
    """
    if not iso:
        return None, None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None, None
    if dt <= datetime.now(timezone.utc):
        return None, None
    return dt.strftime("%H:%M"), dt.day


def _download(url: str) -> str:
    """Download a (public Dropbox raw) URL to a temp .mp4; return the path."""
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
        if p.get("brand") != brand:
            continue
        if p.get("status") != "pending":
            continue
        if "tiktok" not in (p.get("platforms") or []):
            continue
        out.append(p)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Browser-auto-post approved TikToks with a named sound.")
    ap.add_argument("--brand", default="hp", help="Brand key (hp / restore).")
    ap.add_argument("--once", default=None, help="Post just this queue id (ignores status/brand filters).")
    ap.add_argument("--sound", default=None, help="Override the sound name to search for ALL posts this run.")
    ap.add_argument("--dry-run", action="store_true", help="Print the plan; upload nothing.")
    args = ap.parse_args(argv)

    with open(QUEUE_PATH, encoding="utf-8") as f:
        posts = json.load(f)

    targets = _targets(posts, args.brand, args.once)
    if not targets:
        print("Nothing to post (no approved 'pending' TikTok items for this brand).")
        return 0

    account = ACCOUNT_NAMES.get(args.brand, args.brand)

    if not args.dry_run:
        try:
            from tiktokautouploader import upload_tiktok  # type: ignore
        except ImportError:
            print("ERROR: package missing. Run: pip install tiktokautouploader")
            print("(then once: phantomwright_driver install chromium)")
            return 1

    done = 0
    for p in targets:
        desc, tags = split_caption(p.get("text", ""))
        sound = args.sound or p.get("sound")
        hh_mm, day = _schedule_parts(p.get("schedule"))
        when = f"scheduled {hh_mm} (day {day})" if hh_mm else "immediately"
        print(f"\n[{p.get('id')}] account={account} sound={sound!r} -> {when}")
        print(f"  desc: {desc[:80]!r}")
        print(f"  tags: {' '.join(tags)}")

        if args.dry_run:
            continue
        if not sound:
            print("  SKIP: no sound set (add a 'sound' field to the post or pass --sound).")
            continue

        video_path = _download(p["media_url"])
        try:
            kwargs = dict(
                video=video_path,
                description=desc,
                accountname=account,
                hashtags=tags,
                sound_name=sound,
                sound_aud_vol=SOUND_VOLUME,
                copyrightcheck=True,  # surface a blocked (uncleared) song early
                suppressprint=False,
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
