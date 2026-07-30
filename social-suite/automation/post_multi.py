"""Post to MANY HP accounts — grouped by company, each pulling its OWN folder.

Accounts are grouped by ``brand`` (Landscaping / Pools / Design). Each company:
  * pulls clips ONLY from its own folder (content_root/brand_folders[brand])
  * keeps its OWN rotation memory (~/hp-auto/rotation_<brand>.json) — its own
    no-repeat history, its own talking-every-3, its own song cycle
Within a company, every account posts that company's picked clip, but:
  * uniquify.py renders each account its own copy (different fingerprint)
  * each account has its own caption variant, song offset, and mirror flag
so it never looks like the same file spammed across accounts (the ban trigger).

Venvs: Facebook + Instagram + YouTube post from THIS process (hp-venv). TikTok
posts via the tiktok-venv39 helper (tiktokautouploader), scheduled at the
account's time_offset so several TikToks don't all fire together.

Config: content/accounts.json (see accounts.example.json). DRY_RUN=1 previews.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ig_autopost reads IG_STATE at import time. Default the shared rotation state to
# ~/hp-auto (launchd-readable; ~/Downloads is TCC-blocked for background jobs) so
# the multi-account poster never silently writes to the wrong file.
os.environ.setdefault("IG_STATE", os.path.expanduser("~/hp-auto/ig_autopost_state.json"))

from automation import ig_autopost as ig  # noqa: E402
from automation import uniquify as uq      # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS_PATH = os.path.join(os.path.dirname(HERE), "content", "accounts.json")
TIKTOK_PY = os.path.expanduser(os.getenv("TIKTOK_VENV_PY", "~/tiktok-venv39/bin/python"))
# TikTok cookie files (TK_cookies_<account>.json) are read relative to cwd, so the
# poster must run from the SAME folder the logins saved them in.
TIKTOK_COOKIE_DIR = os.path.expanduser(os.getenv("TIKTOK_COOKIE_DIR", "~/hp-auto/tiktok"))
# Seconds to space consecutive Instagram posts apart. Several IG posts in the same
# instant from one connection is a bot/ban signal — spread them out (Rule #1).
IG_STAGGER_SEC = int(os.getenv("IG_STAGGER_SEC", "120"))


def _load_accounts() -> dict:
    path = ACCOUNTS_PATH if os.path.exists(ACCOUNTS_PATH) else os.path.join(
        os.path.dirname(HERE), "content", "accounts.example.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _caption(cfg: dict, acct: dict, choice: dict) -> str:
    variants = cfg.get("caption_variants") or ["{hook}"]
    tmpl = variants[acct.get("caption_variant", 0) % len(variants)]
    hook = ig.HOOKS[choice.get("_hook_i", 0) % len(ig.HOOKS)]
    body = tmpl.format(brand=acct.get("brand", "Landscaping"), hook=hook)
    return f"{body}\n\n{ig.TAGS}"


def _song_for(acct: dict, choice: dict) -> str | None:
    if choice["talking"] or not choice.get("song"):
        return None
    base = ig.SONGS.index(choice["song"]) if choice["song"] in ig.SONGS else 0
    return ig.SONGS[(base + acct.get("song_offset", 0)) % len(ig.SONGS)]


def _post_facebook(acct, video, caption):
    from services.publish.direct import meta
    token = open(os.path.expanduser(acct["token_file"])).read().strip()
    meta.post_facebook_video_file(acct["page_id"], token, caption, video)


def _post_instagram(acct, video, caption, song):
    # Reuse ig_autopost.post via a per-account session, but on a UNIQUE file.
    # Each IG account MUST get its own device-fingerprint session file — reusing
    # one "phone" across several IG accounts is a ban trigger (Rule #1).
    os.environ["IG_SESSIONID"] = open(os.path.expanduser(acct["sessionid_file"])).read().strip()
    os.environ["IG_SESSION"] = os.path.expanduser(f"~/hp-auto/ig_session_{acct['id']}.json")
    choice = {"video": video, "talking": song is None, "song": song}
    ig.post(choice, caption)


def _post_tiktok(acct, video, caption, song, minute_offset):
    # TikTok tool lives in its own venv; call it as a subprocess and let it
    # SCHEDULE at now+offset so the several TikToks spread out.
    args = [TIKTOK_PY, os.path.join(HERE, "tiktok_post_one.py"),
            "--video", video, "--account", acct["tiktok_account"],
            "--caption", caption, "--schedule-offset-min", str(minute_offset)]
    if song:
        args += ["--sound", song]
    if acct.get("mirror"):
        args += ["--mirror-already-applied"]  # informational
    # Run from the cookie dir so tiktokautouploader finds TK_cookies_<account>.json.
    os.makedirs(TIKTOK_COOKIE_DIR, exist_ok=True)
    subprocess.run(args, check=True, cwd=TIKTOK_COOKIE_DIR)


def _post_youtube(acct, video, caption):
    # Official YouTube API upload (hp-venv has the google libs). Same interpreter.
    title = caption.split("\n", 1)[0][:90]
    args = [sys.executable, os.path.join(HERE, "youtube_upload_one.py"),
            "--channel", acct["yt_channel"], "--video", video,
            "--title", title, "--description", caption,
            "--tags", "landscaping,pools,outdoorliving,CollegeStation",
            "--privacy", "public"]
    subprocess.run(args, check=True)


def _brand_folder(cfg: dict, brand: str) -> str:
    """The Dropbox folder a company pulls from: content_root / brand_folders[brand]."""
    content_root = os.path.expanduser(cfg.get("content_root") or ig.FOLDER_DEFAULT)
    folders = cfg.get("brand_folders") or {}
    return os.path.join(content_root, folders.get(brand, brand))


def _brand_state(brand: str) -> str:
    """Per-company rotation memory file (its own no-repeat / talking / song state)."""
    safe = brand.replace(" ", "_").replace("/", "_")
    return os.path.expanduser(f"~/hp-auto/rotation_{safe}.json")


def _post_account(cfg, acct, c, ig_posted, dry):
    """Post the company's picked clip ``c`` to one account. Returns (posted, ig_posted)."""
    song = _song_for(acct, c)          # per-account song variant
    caption = _caption(cfg, acct, c)
    plat = acct["platform"]
    tag = f"{acct['id']} ({plat})"
    if dry:
        print(f"  [dry] {tag}: mirror={acct.get('mirror')} song={song!r}")
        return False, ig_posted
    # Space out Instagram posts so several accounts don't post the same instant
    # from one IP (ban signal). First IG of the run goes immediately.
    if plat == "instagram" and ig_posted > 0:
        delay = IG_STAGGER_SEC + random.randint(0, 45)
        print(f"  ⏳ spacing Instagram {delay}s before {tag} (anti-spam)")
        time.sleep(delay)
    try:
        video = uq.uniquify(c["video"], seed=f"{acct['id']}:{os.path.basename(c['video'])}",
                            mirror=bool(acct.get("mirror")))
        try:
            if plat == "facebook":
                _post_facebook(acct, video, caption)
            elif plat == "instagram":
                _post_instagram(acct, video, caption, song)
            elif plat == "tiktok":
                _post_tiktok(acct, video, caption, song, acct.get("time_offset_min", 0))
            elif plat == "youtube":
                _post_youtube(acct, video, caption)
            else:
                print(f"  ❓ {tag}: unknown platform")
                return False, ig_posted
        finally:
            try:
                os.remove(video)
            except OSError:
                pass
        if plat == "instagram":
            ig_posted += 1
        print(f"  ✅ {tag}")
        return True, ig_posted
    except Exception as e:  # noqa: BLE001 — one account failing shouldn't stop the rest
        print(f"  ❌ {tag}: {e}")
        return False, ig_posted


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    dry = "--dry-run" in argv or os.getenv("DRY_RUN", "").strip().lower() in ("1", "true", "yes")

    cfg = _load_accounts()
    accounts = [a for a in cfg.get("accounts", []) if a.get("enabled")]
    if not accounts:
        print("No enabled accounts.")
        return

    # Group accounts by company so each pulls from its OWN folder + rotation memory.
    brands: dict[str, list] = {}
    for a in accounts:
        brands.setdefault(a.get("brand", "Landscaping"), []).append(a)

    ig_posted = 0  # Instagram spacing counter across the WHOLE run (all companies)
    for brand, accts in brands.items():
        folder = _brand_folder(cfg, brand)
        os.environ["IG_FOLDER"] = folder
        os.environ["IG_STATE"] = _brand_state(brand)
        s = ig.load()
        c = ig.pick(s)
        if not c:
            print(f"[{brand}] no new clips in {folder} — skipping (add clips to that folder).")
            continue
        c["_hook_i"] = s["i"]
        kind = "talking" if c["talking"] else c["song"]
        print(f"[{brand}] {os.path.basename(c['video'])} ({kind})")

        posted_any = False
        for acct in accts:
            posted, ig_posted = _post_account(cfg, acct, c, ig_posted, dry)
            posted_any = posted_any or posted

        if posted_any and not dry:
            ig._apply(s, c)
            ig.save(s)
        elif not dry and not posted_any:
            print(f"[{brand}] nothing posted — rotation left unchanged.")


if __name__ == "__main__":
    main()
