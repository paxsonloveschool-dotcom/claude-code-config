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
    "Restore Marketing/Apps/hp-restore-suite-8472/HP Tiktok",
)
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


def load():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    return {"posted": [], "i": 0}


def save(s):
    json.dump(s, open(STATE, "w"), indent=2)


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


def main():
    s = load()
    vids = sorted(sum([glob.glob(FOLDER + "/*" + e)
                       for e in (".mp4", ".mov", ".MP4", ".MOV")], []))
    new = [v for v in vids if os.path.basename(v) not in s["posted"]]
    if not new:
        print("No new clips to post to Instagram.")
        return

    video = new[0]  # one Reel per run (Instagram posts immediately)
    song = SONGS[s["i"] % len(SONGS)]
    hook = HOOKS[s["i"] % len(HOOKS)]
    caption = f"{hook}\n\n{CTA}\n\n{TAGS}"
    print(f"Instagram Reel: {os.path.basename(video)} | song: {song!r}")
    print(f"  from folder: {FOLDER}")

    dry = ("--dry-run" in sys.argv
           or os.getenv("DRY_RUN", "").strip().lower() in ("1", "true", "yes"))
    if dry:
        print("[dry-run] not posting — this is the clip + song that WOULD go out.")
        return

    cl = login()
    results = cl.search_music(song)
    if results:
        cl.clip_upload_as_reel_with_music(video, caption, results[0])
        print(f"POSTED to Instagram with '{song}' ✅")
    else:
        # Song not found in IG's library for this account — post without music
        # rather than skip, so the clip still goes out.
        cl.clip_upload(video, caption)
        print(f"POSTED to Instagram (no matching track for '{song}') ⚠️")

    s["posted"].append(os.path.basename(video))
    s["i"] += 1
    save(s)


if __name__ == "__main__":
    main()
