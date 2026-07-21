"""Post the next rotation clip to all enabled HP platforms — same clip, in sync.

One shared rotation (from ig_autopost): pick the next clip, post that SAME clip to
Facebook, Instagram, and (once set up) TikTok, then advance the shared state once.
- Talking clips post with their own audio (unmuted) on every platform.
- Work clips get the chosen song on Instagram + TikTok.
- Facebook never adds a song (a Page can't) — it posts the clip's own audio.

Config:
  HP_PLATFORMS           comma list, default "facebook,instagram" (+ "tiktok" later)
  HP_FB_TALKING_ONLY     "1" -> Facebook posts only talking clips (skip silent montages)
  BRAND_HP_FB_PAGE_ID / BRAND_HP_META_ACCESS_TOKEN   Facebook Page creds
  IG_SESSIONID           Instagram browser session
  DRY_RUN=1 / --dry-run  print the plan, post nothing
  --preview N            show the upcoming sequence (no posting)
"""

from __future__ import annotations

import os
import sys

# Make sibling packages (automation, services) importable however this is run.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation import ig_autopost as ig  # noqa: E402


def _platforms():
    return [p.strip().lower() for p in
            os.getenv("HP_PLATFORMS", "facebook,instagram").split(",") if p.strip()]


def _post_facebook(choice, caption):
    from services.publish.direct import meta
    page_id = os.environ.get("BRAND_HP_FB_PAGE_ID", "").strip()
    token = os.environ.get("BRAND_HP_META_ACCESS_TOKEN", "").strip()
    if not page_id or not token:
        raise RuntimeError("missing BRAND_HP_FB_PAGE_ID / BRAND_HP_META_ACCESS_TOKEN")
    meta.post_facebook_video_file(page_id, token, caption, choice["video"])
    return "own audio (no song)"


def _post_tiktok(choice, caption):
    raise RuntimeError("TikTok not set up yet")


_POSTERS = {"facebook": _post_facebook, "instagram": ig.post, "tiktok": _post_tiktok}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--preview" in argv:
        return ig.main(argv)  # identical rotation preview

    s = ig.load()
    c = ig.pick(s)
    if not c:
        print("No new clips left to post.")
        return
    c["_hook_i"] = s["i"]
    caption = ig._caption(c)
    label = "TALKING (no music)" if c["talking"] else f"song: {c['song']!r}"
    print(f"Next: [{c['folder']}] {os.path.basename(c['video'])} | {label}")

    if ("--dry-run" in argv
            or os.getenv("DRY_RUN", "").strip().lower() in ("1", "true", "yes")):
        print(f"[dry-run] would post to: {', '.join(_platforms())}")
        return

    fb_talking_only = os.getenv("HP_FB_TALKING_ONLY", "").strip().lower() in (
        "1", "true", "yes")

    posted_any = False
    for p in _platforms():
        poster = _POSTERS.get(p)
        if poster is None:
            print(f"  ❓ {p}: unknown platform, skipped")
            continue
        if p == "facebook" and fb_talking_only and not c["talking"]:
            print(f"  ⏭️  facebook: skipped (montage; FB set to talking-only)")
            continue
        try:
            status = poster(c, caption)
            posted_any = True
            print(f"  ✅ {p}: {status}")
        except Exception as e:  # noqa: BLE001 — one platform failing shouldn't kill others
            print(f"  ❌ {p}: {e}")

    # Advance the shared rotation once if anything went out (avoids double-posting
    # the same clip; a platform that failed simply misses this one).
    if posted_any:
        ig._apply(s, c)
        ig.save(s)
    else:
        print("Nothing posted — rotation left unchanged.")


if __name__ == "__main__":
    main()
