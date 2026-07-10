"""Auto-post Trophy Exteriors' videos to the Trophy Facebook Page — next-number mode.

Mirror of ``fb_autopost.py`` (HP) for the Trophy Exteriors client. Each POST DAY
(Mon–Fri) the cron looks FRESH at the Trophy posting queue in Dropbox and
schedules exactly ONE video — the lowest-numbered clip whose leading number is
greater than the last number posted — onto TODAY's 2:00 PM (US Central) slot via
Facebook's server-side scheduler.

Trophy specifics vs. HP:
  * Posting source is ONE folder only: ``/TROPHY EXTERIOR/Trophy Social Auto``
    (never Drop Content Here / Trophy Finished / processed). Subfolders inside
    it are walked recursively.
  * Dropbox is a **Business/Team** account, so the queue lives in the team-root
    namespace — the cloud run must set ``DROPBOX_ROOT_NAMESPACE_ID`` (see the
    workflow) so ``dropbox_client`` scopes to it; otherwise the path won't list.
  * Captions rotate (never the same twice in a row); no added music (a Page
    can't) — the video posts with its own audio.

Cloud-only (GitHub Actions): DROPBOX_* + DROPBOX_ROOT_NAMESPACE_ID +
BRAND_TROPHY_FB_PAGE_ID + BRAND_TROPHY_META_ACCESS_TOKEN. DRY_RUN=1 prints the
plan, posts nothing.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(os.path.dirname(HERE), "content", "trophy_fb_posted.json")

VIDEO_EXTS = (".mp4", ".mov", ".m4v")
POST_WEEKDAYS = (0, 1, 2, 3, 4)  # Mon–Fri
POST_HOUR_UTC = 19               # 2:00 PM America/Chicago (CDT); 20:00 for CST
FOLDER = "/TROPHY EXTERIOR/Trophy Social Auto"

CTA = "📍 6 Texas locations — DM for a free roof inspection!"
TAGS = "#roofing #roofingcontractor #texasroofing #stormdamage #roofrepair #newroof #texas"
HOOKS = [
    "Trophy Exteriors — Texas' trusted name in roofing. Built to weather anything. 🏆",
    "Hail don't stand a chance. New roof, total peace of mind. 🌩️🏆",
    "From tear-off to finished in a day. That's the Trophy standard. 🔨",
    "Curb appeal that turns heads — starts at the top. 🏡🏆",
    "Storm rolled through? We've got you covered — literally. ⛈️",
    "A roof you can trust for decades. Texas built, Texas proud. 🤠",
    "Insurance claim? We handle the headache for you. 📋✅",
    "Old roof out, brand-new roof in. Watch the transformation. 🔨🏆",
    "Your home deserves a Trophy finish. 🏆",
    "Quality you can see from the street. 🏆",
    "Leaks, missing shingles, storm damage — we fix it right. 💪",
    "Protecting Texas families, one roof at a time. ☀️🏠",
    "Premium materials. Master craftsmanship. Zero shortcuts. 🔨",
    "When only the best will do — Trophy Exteriors. 🏆",
    "Free inspection today, peace of mind tomorrow. ✅",
    "This is what a Trophy roof looks like. 🏆🏡",
]


def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            s = json.load(f)
            if "last_num" in s:
                s.setdefault("i", 0)
                return s
    return {"last_num": 0, "i": 0}


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

    page_id = os.environ.get("BRAND_TROPHY_FB_PAGE_ID", "").strip()
    token = os.environ.get("BRAND_TROPHY_META_ACCESS_TOKEN", "").strip()
    if not page_id or not token:
        # Not yet connected (client hasn't provided FB Page + token). Skip cleanly
        # so the daily run is a no-op success, not a red failure, until it's set.
        print("Trophy FB not connected yet (no Page id / token) — skipping.")
        return 0

    files = [
        f for f in dbx.list_folder(FOLDER, recursive=True)
        if f.name.lower().endswith(VIDEO_EXTS)
    ]
    s = load_state()
    num, f = next_clip(files, s.get("last_num", 0))
    if not f:
        print(f"No clip numbered above {s.get('last_num', 0)} — nothing to post.")
        return 0

    hook = HOOKS[s.get("i", 0) % len(HOOKS)]
    caption = f"{hook}\n\n{CTA}\n\n{TAGS}"
    print(f"Next up: #{num} ({f.name}) -> today {slot:%a %b %d %H:%M}Z")
    if os.environ.get("DRY_RUN", "").strip().lower() in ("1", "true", "yes"):
        print("[dry-run] posting nothing.")
        return 0

    url = dbx.shared_link(f.path, raw=True)
    meta.post_facebook_video(page_id, token, caption, url, scheduled_time=int(slot.timestamp()))
    s["last_num"] = num
    s["i"] = s.get("i", 0) + 1
    save_state(s)
    print("scheduled ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
