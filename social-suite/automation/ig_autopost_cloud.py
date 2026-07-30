"""Auto-post HP's next Dropbox clip to Instagram as a Reel — cloud, next-number mode.

The official-API sibling of ``fb_autopost``. Instagram's Graph API has no
server-side scheduling, so the GitHub Actions cron runs this **at** the post time
(Mon/Wed/Fri 11:00 CT) and publishes the next-numbered clip immediately as a Reel.
It reuses the exact same Dropbox folder + next-number logic as Facebook, so both
platforms march through the same numbered clip library.

State is {"last_num": N} in content/ig_posted.json (separate from Facebook's, so
the two advance independently). The Reel plays the video's own audio.

Cloud-only (GitHub Actions): DROPBOX_* + BRAND_HP_IG_USER_ID +
BRAND_HP_META_ACCESS_TOKEN secrets. DRY_RUN=1 prints the plan, posts nothing.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from automation.fb_autopost import (
    POST_WEEKDAYS,
    VIDEO_EXTS,
    _hp_folder_path,
    next_clip,
)

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_PATH = os.path.join(os.path.dirname(HERE), "content", "ig_posted.json")

# Rotated caption hooks (mirrors the on-device poster, for brand consistency).
HOOKS = [
    "Higher Purpose Landscaping — built to stand out. 🌿",
    "Quality that speaks for itself. 🌿",
    "This is what happens when vision meets execution. ✨",
    "From overgrown to outdoor escape. 🔥🌿",
    "Backyard goals, done right. 💯🌿",
]
TAGS = ("#fyp #LandscapingTok #CollegeStation #Bryan #Navasota #Houston "
        "#OutdoorLiving #backyardgoals")
CTA = "Call (979) 777-8851 for a free quote!"


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


def caption_for(num: int) -> str:
    """Caption for clip #num: a rotated hook + CTA + hashtags."""
    hook = HOOKS[num % len(HOOKS)]
    return f"{hook}\n\n{CTA}\n\n{TAGS}"


def main() -> int:
    from services.ingest import dropbox_client as dbx
    from services.publish.direct import meta

    now = datetime.now(timezone.utc)
    dry = os.environ.get("DRY_RUN", "").strip().lower() in ("1", "true", "yes")
    if not dry and now.weekday() not in POST_WEEKDAYS:
        print(f"Not a post day ({now:%A}) — nothing to do.")
        return 0

    ig_user_id = os.environ.get("BRAND_HP_IG_USER_ID", "").strip()
    token = os.environ.get("BRAND_HP_META_ACCESS_TOKEN", "").strip()
    if not ig_user_id or not token:
        print("Missing BRAND_HP_IG_USER_ID / BRAND_HP_META_ACCESS_TOKEN.")
        return 1

    folder = _hp_folder_path(dbx)
    if not folder:
        print("Could not find the HP Auto Post folder in Dropbox.")
        return 1

    files = [
        f for f in dbx.list_folder(folder, recursive=True)
        if f.name.lower().endswith(VIDEO_EXTS)
    ]
    s = load_state()
    num, f = next_clip(files, s.get("last_num", 0))
    if not f:
        print(f"No clip numbered above {s.get('last_num', 0)} — nothing to post.")
        return 0

    print(f"Next up: #{num} ({f.name}) -> Instagram Reel now")
    if os.environ.get("DRY_RUN", "").strip().lower() in ("1", "true", "yes"):
        print("[dry-run] posting nothing.")
        return 0

    url = dbx.shared_link(f.path, raw=True)
    meta.post_instagram_reel(ig_user_id, token, caption_for(num), url)
    s["last_num"] = num
    save_state(s)
    print("posted ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
