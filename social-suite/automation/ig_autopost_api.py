"""Internet-based Instagram Reels poster — pulls clips from Dropbox over the API.

Unlike the local-folder version (``ig_autopost.py``), this NEVER reads the
laptop's synced ``~/Library/CloudStorage`` Dropbox folder. A macOS background
timer (launchd) is blocked from that folder unless the Python binary is granted
Full Disk Access — the wall that kept the old timer silently posting nothing.
This version lists + downloads the next clip straight from Dropbox over HTTPS
(the same mechanism the Facebook cloud poster already uses), so the timer only
needs network access + credentials, never a protected local folder.

Flow each run:
  1. Resolve the brand's Dropbox folder (fixed path, or found by name at root).
  2. List it recursively over the API; pick the lowest-numbered clip whose
     leading number is greater than the last one posted (next-number, like fb).
  3. Download that one clip (and its optional ``<n>.txt`` caption) to a temp dir.
  4. Decide music: a clip whose name/folder contains "talk" (or that voice-
     activity detection hears speech in) posts with its own audio, no song.
  5. Post it as a Reel via instagrapi with a searched-by-name track (or plain).
  6. Advance rename-proof state ({"last_num": N, "i": M}).

Brand is ``IG_BRAND`` (hp|trophy); content comes from content/ig_brands.json.

Local creds (NEVER in the repo):
  * ``~/social-auto/<brand>_ig_sessionid.txt`` — instagrapi sessionid
  * ``~/social-auto/<brand>_ig_session.json``  — cached instagrapi settings
  * Dropbox ``DROPBOX_APP_KEY``/``_SECRET``/``_REFRESH_TOKEN`` in the env (e.g.
    sourced from ``~/social-auto/dropbox.env``). The team-namespace id for
    Trophy is read from the brand config and exported automatically.

``DRY_RUN=1`` lists + picks the next clip and downloads it to prove the Dropbox
pull works, then prints the plan and posts NOTHING. This module does not enable
any schedule — wiring the timer / go-live is a separate, deliberate step.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BRANDS_PATH = os.path.join(os.path.dirname(HERE), "content", "ig_brands.json")
VIDEO_EXTS = (".mp4", ".mov", ".m4v")


# ---- pure helpers (unit-tested; no network) -------------------------------

def clip_number(name: str) -> int | None:
    """Leading number of a clip filename ('12 talk.mp4' -> 12); None if unnumbered."""
    m = re.match(r"\s*(\d+)", name)
    return int(m.group(1)) if m else None


def next_clip(files, last_num: int):
    """The file with the smallest leading number greater than ``last_num``."""
    numbered = [(clip_number(f.name), f) for f in files]
    candidates = [(n, f) for n, f in numbered if n is not None and n > last_num]
    return min(candidates, key=lambda x: x[0]) if candidates else (None, None)


def is_video(name: str) -> bool:
    return name.lower().endswith(VIDEO_EXTS)


def caption_sidecar(files, num: int):
    """Find a ``<num>.txt`` caption file alongside the clip (same leading number)."""
    for f in files:
        if f.name.lower().endswith(".txt") and clip_number(f.name) == num:
            return f
    return None


def talk_override(name: str, path: str = "") -> bool | None:
    """Music decision from naming alone, before any audio analysis.

    Returns False (no music) when "talk" appears in the filename or any parent
    folder — the guaranteed, label-driven way to force voice-only. Returns True
    when the filename contains "song". Returns None when undecided, so the caller
    falls back to voice-activity detection on the downloaded file.
    """
    low = (path or name).lower()
    if "talk" in low:
        return False
    if "song" in os.path.basename(name).lower():
        return True
    return None


def build_caption(hook: str, tags: str, cta: str | None = None,
                  custom: str | None = None) -> str:
    """Compose the caption. A per-clip ``custom`` caption wins; tags appended
    only if it has no hashtags of its own. Otherwise hook (+ optional CTA) + tags."""
    if custom:
        return custom if "#" in custom else f"{custom}\n\n{tags}"
    parts = [hook] + ([cta] if cta else []) + [tags]
    return "\n\n".join(p for p in parts if p)


def load_brand(brand: str) -> dict:
    with open(BRANDS_PATH, encoding="utf-8") as f:
        brands = json.load(f)
    if brand not in brands:
        raise SystemExit(f"Unknown IG_BRAND {brand!r}; have {sorted(brands)}")
    return brands[brand]


def state_path(brand: str) -> str:
    return os.environ.get(
        "IG_STATE_FILE",
        os.path.expanduser(f"~/social-auto/{brand}_ig_state.json"),
    )


def load_state(path: str) -> dict:
    if os.path.exists(path):
        s = json.load(open(path, encoding="utf-8"))
        if "last_num" in s:
            s.setdefault("i", 0)
            return s
    return {"last_num": 0, "i": 0}


def save_state(path: str, s: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(s, open(path, "w", encoding="utf-8"), indent=2)


# ---- integration (Dropbox / audio / instagrapi) ---------------------------

def resolve_folder(dbx, cfg: dict) -> str | None:
    """Fixed ``folder`` path if given, else the first root folder matching every
    substring in ``folder_match`` (case-insensitive)."""
    if cfg.get("folder"):
        return cfg["folder"]
    match = [s.lower() for s in cfg.get("folder_match", [])]
    if not match:
        return None
    client = dbx._client()
    res = client.files_list_folder("")
    while True:
        for e in res.entries:
            if not hasattr(e, "rev"):  # folders (FolderMetadata) lack a rev; files have one
                name = (getattr(e, "path_display", None) or getattr(e, "name", "") or "").lower()
                if all(m in name for m in match):
                    return getattr(e, "path_lower", "") or getattr(e, "path_display", "")
        if not getattr(res, "has_more", False):
            return None
        res = client.files_list_folder_continue(res.cursor)


def has_speech(path: str) -> bool:
    """True if the clip has meaningful spoken audio (silero VAD). On any failure
    return True so an undetected talking clip is never given a song by mistake."""
    try:
        import subprocess
        import wave

        import imageio_ffmpeg
        import numpy as np
        import torch
        from silero_vad import get_speech_timestamps, load_silero_vad

        ff = imageio_ffmpeg.get_ffmpeg_exe()
        fd, wv = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        subprocess.run(
            [ff, "-y", "-i", path, "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", wv],
            capture_output=True,
        )
        with wave.open(wv, "rb") as w:
            frames = w.readframes(w.getnframes())
        os.remove(wv)
        audio = torch.from_numpy(
            np.frombuffer(frames, dtype=np.int16).astype("float32") / 32768.0
        )
        ts = get_speech_timestamps(audio, load_silero_vad(), sampling_rate=16000)
        spoken = sum((t["end"] - t["start"]) for t in ts) / 16000.0
        dur = len(audio) / 16000.0
        return spoken >= 2.5 or (dur > 0 and spoken / dur >= 0.20)
    except Exception as e:  # noqa: BLE001
        print("  (speech check failed -> treat as talking, no song):", e)
        return True


def wants_song(name: str, path: str, local_file: str) -> bool:
    decided = talk_override(name, path)
    if decided is not None:
        return decided
    return not has_speech(local_file)


def _patch_instagrapi():
    """instagrapi can crash parsing a null music track; make it degrade safely."""
    import instagrapi.extractors as ex
    import instagrapi.mixins.fbsearch as fb

    original = ex.extract_track

    def safe(d):
        try:
            return original(d) if d else None
        except Exception:  # noqa: BLE001
            return None

    ex.extract_track = safe
    fb.extract_track = safe


def login(brand: str):
    from instagrapi import Client

    session = os.path.expanduser(f"~/social-auto/{brand}_ig_session.json")
    sidfile = os.path.expanduser(f"~/social-auto/{brand}_ig_sessionid.txt")
    cl = Client()
    if os.path.exists(session):
        try:
            cl.load_settings(session)
            cl.account_info()
            return cl
        except Exception:  # noqa: BLE001 — stale cache, fall back to sessionid
            cl = Client()
    if not os.path.exists(sidfile):
        raise SystemExit(f"Missing {sidfile} — save the IG sessionid there first.")
    cl.login_by_sessionid(open(sidfile).read().strip())
    cl.dump_settings(session)
    return cl


def _pick_track(results):
    for t in results:
        title = (getattr(t, "title", "") or "").lower()
        if "instrumental" not in title and "cover" not in title:
            return t
    return results[0] if results else None


def main() -> int:
    brand = os.environ.get("IG_BRAND", "hp").strip().lower()
    cfg = load_brand(brand)
    if cfg.get("root_namespace_id"):
        os.environ["DROPBOX_ROOT_NAMESPACE_ID"] = str(cfg["root_namespace_id"])

    from services.ingest import dropbox_client as dbx

    folder = resolve_folder(dbx, cfg)
    if not folder:
        print(f"Could not resolve the Dropbox folder for brand {brand!r}.")
        return 1

    files = dbx.list_folder(folder, recursive=True)
    videos = [f for f in files if is_video(f.name)]
    sp = state_path(brand)
    s = load_state(sp)
    num, vid = next_clip(videos, s.get("last_num", 0))
    if not vid:
        print(f"No clip numbered above {s.get('last_num', 0)} in {folder} — nothing to post.")
        return 0

    tmp = tempfile.mkdtemp(prefix=f"{brand}_ig_")
    local = dbx.download(vid, dest_dir=tmp)

    custom = None
    side = caption_sidecar(files, num)
    if side:
        side_local = dbx.download(side, dest_dir=tmp)
        custom = open(side_local, encoding="utf-8").read().strip() or None

    hook = cfg["hooks"][s.get("i", 0) % len(cfg["hooks"])]
    caption = build_caption(hook, cfg["tags"], cfg.get("cta"), custom)
    song = cfg["songs"][s.get("i", 0) % len(cfg["songs"])]
    music = wants_song(vid.name, vid.path, local)

    plan = "SONG: " + song if music else "VOICE ONLY (talking)"
    print(f"Brand {brand} | #{num} {vid.name} | {plan}")
    print(f"Pulled from Dropbox -> {local} ({os.path.getsize(local)} bytes)")

    if os.environ.get("DRY_RUN", "").strip().lower() in ("1", "true", "yes"):
        print("[dry-run] Dropbox pull OK; posting nothing.")
        return 0

    cl = login(brand)
    _patch_instagrapi()
    if music:
        try:
            results = [t for t in cl.search_music(song) if t]
        except Exception:  # noqa: BLE001
            results = []
        track = _pick_track(results)
        if track:
            cl.clip_upload_as_reel_with_music(local, caption, track)
            print(f"#{num} POSTED with '{getattr(track, 'title', song)}' ✅")
        else:
            cl.clip_upload(local, caption)
            print(f"#{num} POSTED (no matching track) ⚠️")
    else:
        cl.clip_upload(local, caption)
        print(f"#{num} POSTED — talking, no song ✅")

    s["last_num"] = num
    s["i"] = s.get("i", 0) + 1
    save_state(sp, s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
