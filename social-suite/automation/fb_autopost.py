"""Auto-post HP's Dropbox videos to the HP Facebook Page — next-number mode.

Each POST DAY (Mon/Wed/Fri/Sat), the daily cron looks at the HP Dropbox folder
FRESH and schedules exactly ONE video — the lowest-numbered clip whose leading
number is greater than the last number posted — onto TODAY's 11:00 (US Central)
slot via Facebook's server-side scheduler. Nothing is queued days ahead, so the
owner can rename/replace/reorder clips any time before the morning they post and
every platform picks up the same change together.

Rules:
  * Clips must be numbered: ``1.mp4, 2.mp4, ... 10.mp4`` (leading number = order).
  * State is just {"last_num": N} in content/fb_posted.json — rename-proof.
  * No added music (a Page can't); the video posts with its own audio.

Cloud-only (GitHub Actions): DROPBOX_* + BRAND_HP_FB_PAGE_ID +
BRAND_HP_META_ACCESS_TOKEN secrets. DRY_RUN=1 prints the plan, posts nothing.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(os.path.dirname(HERE), "content", "fb_posted.json")

VIDEO_EXTS = (".mp4", ".mov", ".m4v")
POST_WEEKDAYS = (0, 2, 4, 5)  # Mon, Wed, Fri, Sat
POST_HOUR_UTC = 16            # 11:00 America/Chicago (CDT)
CAPTION = "Higher Purpose Landscaping 🌿 Call (979) 777-8851 for a free quote!"


def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            s = json.load(f)
            if "last_num" in s:
                return s
    return {"last_num": 0}


def save_state(s: dict) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)
        f.write("\n")


def clip_number(name: str) -> int | None:
    """Leading number of a clip filename ('12 talk.mp4' -> 12); None if unnumbered."""
    m = re.match(r"\s*(\d+)", name)
    return int(m.group(1)) if m else None


def next_clip(files, last_num: int):
    """The file with the smallest leading number greater than ``last_num``."""
    numbered = [(clip_number(f.name), f) for f in files]
    candidates = [(n, f) for n, f in numbered if n is not None and n > last_num]
    return min(candidates, key=lambda x: x[0]) if candidates else (None, None)


def _hp_folder_path(dbx) -> str | None:
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

    now = datetime.now(timezone.utc)
    if now.weekday() not in POST_WEEKDAYS:
        print(f"Not a post day ({now:%A}) — nothing to do.")
        return 0
    slot = now.replace(hour=POST_HOUR_UTC, minute=0, second=0, microsecond=0)
    if now >= slot:
        print("Today's slot already passed — nothing to do.")
        return 0

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
    s = load_state()
    num, f = next_clip(files, s.get("last_num", 0))
    if not f:
        print(f"No clip numbered above {s.get('last_num', 0)} — nothing to post.")
        return 0

    print(f"Next up: #{num} ({f.name}) -> today {slot:%a %b %d %H:%M}Z")
    if os.environ.get("DRY_RUN", "").strip().lower() in ("1", "true", "yes"):
        print("[dry-run] posting nothing.")
        return 0

    url = dbx.shared_link(f.path, raw=True)
    meta.post_facebook_video(page_id, token, CAPTION, url, scheduled_time=int(slot.timestamp()))
    s["last_num"] = num
    save_state(s)
    print("scheduled ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
