"""Post the current rotation clip to MANY HP accounts — safely.

Every account gets the SAME rotation clip, but:
  * uniquify.py renders each account its own copy (different fingerprint)
  * each account has its own caption variant, song offset, and time offset
so it never looks like the same file spammed across accounts (the ban trigger).

Runs the shared rotation once (same clip everywhere), advances state once.

Venvs: Facebook + Instagram post from THIS process (hp-venv: meta + instagrapi).
TikTok posts via the tiktok-venv39 helper (tiktokautouploader) — scheduled at the
account's time_offset so the several TikToks don't all fire together. YouTube is
wired the same way once its browser uploader is set up.

Config: content/accounts.json (see accounts.example.json). DRY_RUN=1 previews.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

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
    subprocess.run(args, check=True)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    dry = "--dry-run" in argv or os.getenv("DRY_RUN", "").strip().lower() in ("1", "true", "yes")

    cfg = _load_accounts()
    s = ig.load()
    c = ig.pick(s)
    if not c:
        print("No new clips left to post.")
        return
    c["_hook_i"] = s["i"]
    print(f"Clip: [{c['folder']}] {os.path.basename(c['video'])} "
          f"({'talking' if c['talking'] else c['song']})")

    posted_any = False
    for acct in cfg.get("accounts", []):
        if not acct.get("enabled"):
            continue
        song = _song_for(acct, c)  # per-account song variant
        caption = _caption(cfg, acct, c)
        plat = acct["platform"]
        tag = f"{acct['id']} ({plat})"
        if dry:
            print(f"  [dry] {tag}: mirror={acct.get('mirror')} +{acct.get('time_offset_min',0)}m "
                  f"song={song!r}")
            continue
        try:
            # Unique copy for this account (skip re-render for a dry run).
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
                    print(f"  ⏭️  {tag}: youtube uploader not wired yet")
                    continue
                else:
                    print(f"  ❓ {tag}: unknown platform")
                    continue
            finally:
                try:
                    os.remove(video)
                except OSError:
                    pass
            posted_any = True
            print(f"  ✅ {tag}")
        except Exception as e:  # noqa: BLE001 — one account failing shouldn't stop the rest
            print(f"  ❌ {tag}: {e}")

    if posted_any and not dry:
        ig._apply(s, c)
        ig.save(s)
    elif not dry:
        print("Nothing posted — rotation left unchanged.")


if __name__ == "__main__":
    main()
