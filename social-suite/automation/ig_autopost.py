"""Fully-automatic Instagram Reels posting WITH a real (searched-by-name) song.

Mirror of the TikTok browser-autopost, for Instagram — via the open-source
``instagrapi`` (Instagram private mobile API). It logs in with a saved session,
searches Instagram's music library for the song by name, and posts the clip as a
Reel with that track attached:

    track = cl.search_music("Aerosmith Sweet Emotion")[0]
    cl.clip_upload_as_reel_with_music(video, caption, track)

Because it mimics the phone app, it reaches the same music library the app does
(trending songs included) — the Instagram equivalent of the TikTok trick.

Posts ONE clip per run (Instagram's private API publishes immediately — there's
no native future-scheduling), so a launchd timer fires it Mon/Wed/Fri at noon.
It pulls new clips from the shared HP Dropbox folder, rotates the same song list,
and tracks what it's posted so it never repeats.

⚠️ Private-API automation is against Instagram's ToS (same account-risk class as
the TikTok tool). A Business IG account may be limited to cleared songs; a
Creator/personal account gets the full trending library — test one to see.

Setup (on the laptop):
    pip3 install instagrapi
    # create ~/Downloads/ig_creds.json  ->  {"username": "...", "password": "..."}
    python3 automation/ig_autopost.py        # posts the next clip as a Reel w/ song
"""

import glob
import json
import os
import sys

FOLDER = os.getenv(
    "IG_FOLDER",
    "/Users/calebpittman/Library/CloudStorage/Dropbox-Restoremarketingco/"
    "Restore Marketing/Apps/hp-restore-suite-8472/HP Auto Post",
)
# The one subfolder of talking clips (no music); every other subfolder is "work".
TALKING_SUBFOLDER = os.getenv("IG_TALKING_SUBFOLDER", "Talking Videos")
# After this many work clips in a row, post one talking clip.
WORK_PER_TALKING = int(os.getenv("IG_WORK_PER_TALKING", "3"))
VIDEO_EXTS = (".mp4", ".mov", ".m4v", ".MP4", ".MOV", ".M4V")
STATE = os.path.expanduser(os.getenv("IG_STATE", "~/Downloads/ig_autopost_state.json"))
SESSION = os.path.expanduser(os.getenv("IG_SESSION", "~/Downloads/ig_session.json"))
CREDS = os.path.expanduser(os.getenv("IG_CREDS", "~/Downloads/ig_creds.json"))  # {"username":..,"password":..}

SONGS = [
    "Luke Combs - Ain't No Love in Oklahoma", "Luke Combs - Lovin' On You",
    "Luke Combs - When It Rains It Pours", "Jon Pardi - Night Shift",
    "Jon Pardi - Heartache on the Dance Floor", "Jon Pardi - Your Heart or Mine",
    "Brooks & Dunn - Boot Scootin' Boogie", "Brooks & Dunn - Hard Workin' Man",
    "Alan Jackson - Good Time", "Alan Jackson - Chattahoochee",
    "Alan Jackson - Little Bitty", "Alan Jackson - Don't Rock the Jukebox",
    "Tim McGraw - Something Like That", "Tim McGraw - I Like It, I Love It",
    "Tim McGraw - Down on the Farm", "Cody Johnson - Me and My Kind",
    "Cody Johnson - Dance Her Home", "Cody Johnson - Honky Tonk Mood",
    "Turnpike Troubadours - 7 & 7", "Merle Haggard - Workin' Man Blues",
    "Hank Williams Jr. - A Country Boy Can Survive", "Dolly Parton - 9 to 5",
    "Nitty Gritty Dirt Band - Fishin' in the Dark",
    "John Denver - Thank God I'm a Country Boy", "The Osborne Brothers - Rocky Top",
    "Kenny Chesney - American Kids", "Tracy Lawrence - Time Marches On",
    "Joe Diffie - Pickup Man", "Joe Diffie - John Deere Green",
    "Toby Keith - Should've Been a Cowboy", "Chris Stapleton - Loving You On My Mind",
    "AC/DC - Thunderstruck", "Aerosmith - Sweet Emotion", "Aerosmith - Walk This Way",
    "Alice In Chains - Rooster", "Creedence Clearwater Revival - Fortunate Son",
    "Foghat - Slow Ride",
]
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


_DEFAULT_STATE = {
    "posted": [],            # relative paths ("Subfolder/clip.mp4") already posted
    "i": 0,                  # song rotation index (work clips only)
    "nt_count": 0,           # work clips posted since the last talking clip
    "folder_used_at": {},    # work subfolder -> seq when last used (round-robin)
    "last_work_folder": "",  # to avoid the same subfolder back-to-back
    "talking_i": 0,          # talking-clip rotation index
    "seq": 0,                # monotonic post counter
}


def load():
    if os.path.exists(STATE):
        s = json.load(open(STATE))
        for k, v in _DEFAULT_STATE.items():
            s.setdefault(k, v.copy() if isinstance(v, (list, dict)) else v)
        return s
    return {k: (v.copy() if isinstance(v, (list, dict)) else v)
            for k, v in _DEFAULT_STATE.items()}


def save(s):
    json.dump(s, open(STATE, "w"), indent=2)


def _rel(path):
    return os.path.relpath(path, FOLDER)


def _subfolders():
    """Immediate subfolders of FOLDER, sorted by name."""
    return sorted(e.name for e in os.scandir(FOLDER) if e.is_dir())


def _videos_in(subfolder):
    """All video files under one subfolder (recursive), sorted, as full paths."""
    root = os.path.join(FOLDER, subfolder)
    out = []
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if f.endswith(VIDEO_EXTS):
                out.append(os.path.join(dirpath, f))
    return sorted(out)


def pick(s):
    """Choose the next clip to post given state ``s`` (no side effects).

    Returns dict {video, talking, folder, song} or None if nothing is left.
    - Every WORK_PER_TALKING work clips, return a talking clip (no song).
    - Work clips rotate the subfolders round-robin: never the same subfolder
      twice in a row; the least-recently-used eligible subfolder is next; a clip
      is never repeated.
    """
    subs = _subfolders()
    work_subs = [x for x in subs if x != TALKING_SUBFOLDER]
    posted = set(s["posted"])

    # Talking slot?
    if s["nt_count"] >= WORK_PER_TALKING and TALKING_SUBFOLDER in subs:
        tvids = _videos_in(TALKING_SUBFOLDER)
        if tvids:
            video = tvids[s["talking_i"] % len(tvids)]  # cycle the talking clips
            return {"video": video, "talking": True,
                    "folder": TALKING_SUBFOLDER, "song": None}

    # Work slot: round-robin the work subfolders.
    def unposted(sub):
        return [v for v in _videos_in(sub) if _rel(v) not in posted]

    eligible = [sub for sub in work_subs if unposted(sub)
                and sub != s["last_work_folder"]]
    if not eligible:  # only the last-used folder has clips left (or all others empty)
        eligible = [sub for sub in work_subs if unposted(sub)]
    if not eligible:
        return None  # every work clip has been posted

    # Least-recently-used first (never used = -1 sorts first), tiebreak by name.
    eligible.sort(key=lambda sub: (s["folder_used_at"].get(sub, -1), sub))
    chosen = eligible[0]
    return {"video": unposted(chosen)[0], "talking": False,
            "folder": chosen, "song": SONGS[s["i"] % len(SONGS)]}


def _apply(s, choice):
    """Advance state ``s`` as if ``choice`` was just posted (used live + in preview)."""
    s["posted"].append(_rel(choice["video"]))
    if choice["talking"]:
        s["talking_i"] += 1
        s["nt_count"] = 0
    else:
        s["folder_used_at"][choice["folder"]] = s["seq"]
        s["last_work_folder"] = choice["folder"]
        s["nt_count"] += 1
        s["i"] += 1
    s["seq"] += 1


def login():
    """Return a logged-in instagrapi Client, preferring a saved browser session.

    Instagram rate-limits / blacklists the private password-login endpoint, so we
    avoid it whenever possible:
      1. IG_SESSIONID env (a live browser ``sessionid`` cookie) — most reliable.
      2. The saved session file, validated with a cheap authenticated call (NOT a
         password login).
      3. Only as a last resort, username/password from CREDS.
    """
    from instagrapi import Client  # lazy import so the file loads without the dep

    cl = Client()
    # Reuse saved device/UUIDs so Instagram sees a consistent "phone" each run.
    if os.path.exists(SESSION):
        try:
            cl.load_settings(SESSION)
        except Exception:  # noqa: BLE001 — corrupt file, ignore and continue
            pass

    # Authenticate ONLY via a browser session — never the password endpoint
    # (Instagram blacklists it, and a failed password attempt kills live sessions).
    sid = os.getenv("IG_SESSIONID", "").strip()
    if sid:
        cl.login_by_sessionid(sid)
        cl.dump_settings(SESSION)
        return cl

    # No fresh sessionid given — try the saved session with a cheap probe.
    try:
        cl.get_timeline_feed()  # authenticated call, no password
        return cl
    except Exception as e:  # noqa: BLE001
        print(
            "Instagram session missing or expired. We never use the password "
            "(Instagram blocks it). Grab a fresh `sessionid` from instagram.com "
            f"and re-run with IG_SESSIONID set.\n  (detail: {type(e).__name__})"
        )
        sys.exit(1)


def _caption(choice):
    hook = HOOKS[choice.get("_hook_i", 0) % len(HOOKS)]
    return f"{hook}\n\n{CTA}\n\n{TAGS}"


def preview(n):
    """Print the next ``n`` posts (folder / clip / song / talking) — posts nothing."""
    import copy
    s = copy.deepcopy(load())
    print(f"Preview of the next {n} posts from:\n  {FOLDER}\n")
    for k in range(1, n + 1):
        c = pick(s)
        if not c:
            print(f"{k:>2}. (nothing left to post)")
            break
        kind = "🗣️ TALKING (no music)" if c["talking"] else f"🎵 {c['song']}"
        print(f"{k:>2}. [{c['folder']}]  {os.path.basename(c['video'])}\n"
              f"     {kind}")
        _apply(s, c)


def _install_music_patch():
    """instagrapi crashes on a null track in music-search results — make it None-safe."""
    try:
        from instagrapi.mixins import fbsearch as _fb
        if getattr(_fb.extract_track, "_hp_safe", False):
            return
        _orig = _fb.extract_track

        def _safe(data, _orig=_orig):
            if not data:
                return None
            try:
                return _orig(data)
            except Exception:  # noqa: BLE001 — skip a malformed track
                return None

        _safe._hp_safe = True
        _fb.extract_track = _safe
    except Exception:  # noqa: BLE001 — best effort
        pass


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--preview" in argv:
        i = argv.index("--preview")
        n = int(argv[i + 1]) if i + 1 < len(argv) and argv[i + 1].isdigit() else 8
        preview(n)
        return

    s = load()
    c = pick(s)
    if not c:
        print("No new clips left to post.")
        return

    video, talking, folder, song = c["video"], c["talking"], c["folder"], c["song"]
    c["_hook_i"] = s["i"]
    caption = _caption(c)
    kind = "TALKING (no music)" if talking else f"song: {song!r}"
    print(f"Next: [{folder}] {os.path.basename(video)} | {kind}")

    dry = ("--dry-run" in argv
           or os.getenv("DRY_RUN", "").strip().lower() in ("1", "true", "yes"))
    if dry:
        print("[dry-run] not posting — this is what WOULD go out next.")
        return

    cl = login()
    if talking:
        cl.clip_upload(video, caption)  # talking clip: own audio, no song
        print("POSTED talking clip (own audio, no music) ✅")
    else:
        _install_music_patch()
        results = [t for t in cl.search_music(song) if t]
        if not results:
            print(f"Song '{song}' isn't available for this account — NOT posting. "
                  "Pick a different song from the list (or add it in-app) and rerun.")
            return
        cl.clip_upload_as_reel_with_music(video, caption, results[0])
        print(f"POSTED to Instagram with '{song}' ✅")

    _apply(s, c)
    save(s)


if __name__ == "__main__":
    main()
