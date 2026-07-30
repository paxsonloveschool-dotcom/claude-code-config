"""Post ONE (already-uniquified) clip to a TikTok account, with a sound.

Runs in the tiktok-venv39 (where tiktokautouploader lives). Called by
post_multi.py as a subprocess so the main poster (hp-venv) doesn't need the heavy
TikTok deps. Schedules at now+offset when given, so several TikToks stagger.
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--account", required=True)      # tiktokautouploader cookie/account name
    ap.add_argument("--caption", default="")
    ap.add_argument("--sound", default=None)         # None -> talking clip, own audio
    ap.add_argument("--schedule-offset-min", type=int, default=0)
    ap.add_argument("--mirror-already-applied", action="store_true")
    a = ap.parse_args()

    from tiktokautouploader import upload_tiktok  # heavy import, lazy

    tags = re.findall(r"#\w+", a.caption)
    desc = re.sub(r"#\w+", "", a.caption).strip()
    kwargs = dict(video=a.video, description=desc, accountname=a.account,
                  hashtags=tags, copyrightcheck=True, suppressprint=False)
    if a.sound:
        kwargs.update(sound_name=a.sound, sound_aud_vol="mix")
    if a.schedule_offset_min > 0:
        when = datetime.now() + timedelta(minutes=a.schedule_offset_min)
        kwargs.update(schedule=when.strftime("%H:%M"), day=when.day)

    upload_tiktok(**kwargs)
    print(f"tiktok ok: {a.account}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
