"""Auto-post HP's Dropbox videos to the HP Facebook Page — native video, own audio.

Cloud-friendly: runs on GitHub Actions (Dropbox + Meta secrets live there), needs
no Mac. Reuses the suite's Dropbox client and the Meta Graph poster. Uses
Facebook's server-side scheduling to queue each new video onto the next
Mon/Wed/Fri/Sat 11:00 (local) slot — Facebook then publishes it itself.

No added song: a Facebook Page can't use library music, so the video posts with
its OWN audio (outro/native sound). TikTok + Instagram carry the real songs.

Dedupe is by Dropbox ``rev`` (kept in content/fb_posted.json), so re-runs never
double-post and the file's name/order can change freely.

Usage (on a runner with the secrets, or locally):
    python automation/fb_autopost.py            # schedule new videos
    DRY_RUN=1 python automation/fb_autopost.py  # show the plan, post nothing
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(os.path.dirname(HERE), "content", "fb_posted.json")

VIDEO_EXTS = (".mp4", ".mov", ".m4v")
POST_WEEKDAYS = (0, 2, 4, 5)  # Mon, Wed, Fri, Sat
POST_HOUR_UTC = 16            # 11:00 America/Chicago (CDT); ~10:00 in winter (CST)
POST_MINUTE = 0
HORIZON_DAYS = 28             # Facebook allows scheduling up to 30 days ahead
CAPTION = "Higher Purpose Landscaping 🌿 Call (979) 777-8851 for a free quote!"


def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"posted": [], "last_slot": None}


def save_state(s: dict) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
        f.write("\n")


def next_slots(start: datetime, count: int) -> list[datetime]:
    """Next ``count`` Mon/Wed/Fri/Sat 11:00-local slots after ``start`` (UTC, ≤horizon)."""
    out: list[datetime] = []
    for off in range(HORIZON_DAYS + 1):
        d = start + timedelta(days=off)
        if d.weekday() in POST_WEEKDAYS:
            slot = d.replace(hour=POST_HOUR_UTC, minute=POST_MINUTE, second=0, microsecond=0)
            if slot > start and len(out) < count:
                out.append(slot)
    return out


def _hp_folder_path(dbx) -> str | None:
    """Find the HP Tiktok folder at the Dropbox app-folder root."""
    client = dbx._client()
    res = client.files_list_folder("")
    while True:
        for e in res.entries:
            if e.__class__.__name__ == "FolderMetadata":
                name = getattr(e, "path_display", e.name).lower()
                if "hp" in name and "tiktok" in name:
                    return getattr(e, "path_lower", "") or getattr(e, "path_display", "")
        if not getattr(res, "has_more", False):
            return None
        res = client.files_list_folder_continue(res.cursor)


def main() -> int:
    from services.ingest import dropbox_client as dbx
    from services.publish.direct import meta

    page_id = os.environ.get("BRAND_HP_FB_PAGE_ID", "").strip()
    token = os.environ.get("BRAND_HP_META_ACCESS_TOKEN", "").strip()
    if not page_id or not token:
        print("Missing BRAND_HP_FB_PAGE_ID / BRAND_HP_META_ACCESS_TOKEN.")
        return 1

    folder = _hp_folder_path(dbx)
    if not folder:
        print("Could not find the HP Tiktok folder in Dropbox.")
        return 1

    files = [f for f in dbx.list_folder(folder) if f.name.lower().endswith(VIDEO_EXTS)]
    files.sort(key=lambda f: f.name)

    s = load_state()
    already = set(s.get("posted", []))
    new = [f for f in files if f.rev not in already]
    if not new:
        print("No new HP videos for Facebook.")
        return 0

    now = datetime.now(timezone.utc)
    start = now
    if s.get("last_slot"):
        try:
            start = max(now, datetime.fromisoformat(s["last_slot"]) + timedelta(minutes=1))
        except ValueError:
            pass
    slots = next_slots(start, len(new))
    print(f"{len(new)} new video(s); {len(slots)} slot(s) open in the next {HORIZON_DAYS} days.")

    dry = os.environ.get("DRY_RUN", "").strip().lower() in ("1", "true", "yes")
    for i, f in enumerate(new):
        if i >= len(slots):
            print("Waiting for next run (window full):", f.name)
            continue
        slot = slots[i]
        print(f"{f.name} -> {slot:%a %b %d %H:%M}Z")
        if dry:
            continue
        url = dbx.shared_link(f.path, raw=True)
        meta.post_facebook_video(page_id, token, CAPTION, url, scheduled_time=int(slot.timestamp()))
        s.setdefault("posted", []).append(f.rev)
        s["last_slot"] = slot.isoformat()
        save_state(s)
        print("  scheduled ✅")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
