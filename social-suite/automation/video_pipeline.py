"""Video pipeline: Dropbox brand folders -> captioned clip -> REVIEW queue.

Scans the TOP-LEVEL folders of the Dropbox app folder, matches each to a brand
by keyword in its name (``…HP…`` -> hp, ``…Restore…`` -> restore), and for each
matched folder pulls new videos, transcribes them, writes a caption (free $0
writer), burns the captions on, uploads the finished clip to a ``processed/``
subfolder the owner can watch, and appends a ``status:"review"`` queue entry.

**Nothing is ever posted** — the poster only fires ``status:"pending"``. And only
TOP-LEVEL folders are scanned (never recursing into a nested folder), so one
brand's videos can never leak into another brand's posts.

Run on GitHub Actions (heavy ffmpeg/whisper deps + Dropbox secrets live there):
    python automation/video_pipeline.py        # process
    python automation/video_pipeline.py --ls    # just list what the app sees
Heavy imports (dropbox, faster-whisper, ffmpeg) are lazy.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
QUEUE_PATH = os.path.join(ROOT, "content", "queue.json")
PROCESSED_PATH = os.path.join(ROOT, "content", "processed.json")

VIDEO_EXTS = (".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv")
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".heic", ".webp")

# Brand classification by keyword in the folder name + that brand's look. Order
# matters: check "restore" before "hp" so "Restore" never falls through to hp.
BRAND_RULES = [
    ("restore", "restore", "Restore Marketing",
     ["RestoreMarketing", "marketingagency", "smallbusinessmarketing",
      "contentcreator", "socialmediamarketing", "digitalmarketing"]),
    ("hp", "hp", "HP Landscaping",
     ["HPLandscaping", "landscaping", "hardscape", "patiodesign", "backyardgoals",
      "outdoorliving", "stampedconcrete", "curbappeal"]),
]
# Kept for backward-compat/tests: folder-name -> (key, display, tags).
BRANDS = {
    "HP": ("hp", "HP Landscaping", ["HPLandscaping", "landscaping", "lawncare"]),
    "Restore": ("restore", "Restore Marketing", ["RestoreMarketing", "marketing"]),
}
REVIEW_PLATFORMS = [p.strip() for p in os.getenv("REVIEW_PLATFORMS", "instagram,facebook").split(",") if p.strip()]


def classify_brand(folder_name: str):
    """Return (key, display, hashtags) for a folder name, or None if unmatched."""
    low = (folder_name or "").lower()
    for needle, key, display, tags in BRAND_RULES:
        if needle in low:
            return (key, display, list(tags))
    return None


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
    return json.loads(text) if text else default


def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", os.path.splitext(name)[0]).strip("-").lower()[:40]


def _compose(copy) -> str:
    tags = " ".join("#" + t.lstrip("#") for t in copy.hashtags)
    return f"{copy.hook}\n\n{copy.caption}\n\n{tags}".strip()


def _transcript_text(segments) -> str:
    return " ".join(getattr(s, "text", "").strip() for s in segments).strip()


def display_folder(brand_key: str) -> str:
    """Map a brand key to its canonical Dropbox folder name (for tests/docs)."""
    for folder, (key, *_rest) in BRANDS.items():
        if key == brand_key:
            return folder
    return brand_key


def _top_level_folders(dbx):
    """Yield (path_lower, display_name) for each folder at the app-folder root."""
    client = dbx._client()
    res = client.files_list_folder("")
    out = []
    while True:
        for e in res.entries:
            if e.__class__.__name__ == "FolderMetadata":
                out.append((getattr(e, "path_lower", ""), getattr(e, "path_display", e.name)))
        if not getattr(res, "has_more", False):
            break
        res = client.files_list_folder_continue(res.cursor)
    return out


# Per-brand Dropbox layout the owner asked for:
#   <Brand>/Drop Content Here/  -> raw videos the owner drops in (the input)
#   <Brand>/Ready To Post/      -> approved keepers, ready to publish
# Input folder the pipeline pulls source videos from, under each brand folder.
# Override per-run with CONTENT_FOLDER (e.g. "HP Content" for work footage,
# "HP Talking Content" for talking-head clips). Default kept for back-compat.
DROP_FOLDER = os.getenv("CONTENT_FOLDER") or "Drop Content Here"
# Destination folder for approved/saved clips. Override per-run with POSTS_FOLDER
# (e.g. "HP Posts"). Default kept for back-compat.
READY_FOLDER = os.getenv("POSTS_FOLDER") or "Ready To Post"


def _list_videos_recursive(dbx, folder: str):
    """Every video file under ``folder`` at ANY depth (the owner drops whole
    subfolders of downloaded content). Returns dropbox_client.DropboxFile objects;
    empty list if the folder is missing."""
    client = dbx._client()
    out = []
    try:
        res = client.files_list_folder(folder, recursive=True)
    except Exception as ex:  # noqa: BLE001 — missing folder shouldn't crash
        if "not_found" in str(ex).lower():
            return []
        raise
    while True:
        for e in res.entries:
            if e.__class__.__name__ != "FileMetadata":
                continue
            if not e.name.lower().endswith(VIDEO_EXTS):
                continue
            out.append(dbx.DropboxFile(
                path=getattr(e, "path_display", "") or getattr(e, "path_lower", ""),
                name=getattr(e, "name", ""),
                size_bytes=int(getattr(e, "size", 0) or 0),
                rev=getattr(e, "rev", "") or "",
            ))
        if not getattr(res, "has_more", False):
            break
        res = client.files_list_folder_continue(res.cursor)
    return out


def _brand_videos(dbx, path_lower: str):
    """Videos to process for a brand: every video under '<Brand>/Drop Content
    Here' (recursively, since the owner drops whole subfolders), else the brand
    root (back-compat). Never returns clips in Ready To Post / processed."""
    drop = f"{path_lower.rstrip('/')}/{DROP_FOLDER.lower()}"
    vids = _list_videos_recursive(dbx, drop)
    if vids:
        return vids
    return [f for f in dbx.list_folder(path_lower) if f.name.lower().endswith(VIDEO_EXTS)]


def organize_dropbox(execute: bool = False) -> None:
    """Create the owner's clean per-brand layout and tidy existing files.

    Always prints the current tree. With ``execute`` True, for each brand folder:
      * create ``Ready To Post`` and ``Drop Content Here`` (idempotent),
      * move loose root-level raw videos into ``Drop Content Here``,
      * move saved keepers (queue items, from ``processed/``) into ``Ready To
        Post`` and refresh their queue ``media_path``/``media_url``.
    """
    from services.ingest import dropbox_client as dbx  # lazy

    client = dbx._client()
    print("== Dropbox BEFORE ==")
    debug_tree()
    if not execute:
        print("\n(dry run — set DROPBOX_ORGANIZE=go to create folders + move files)")
        return

    queue = _load_json(QUEUE_PATH, [])
    changed = False
    for path_lower, display in _top_level_folders(dbx):
        if not classify_brand(display):
            continue
        base = display.rstrip("/")
        ready, drop = f"{base}/{READY_FOLDER}", f"{base}/{DROP_FOLDER}"
        for folder in (ready, drop):
            try:
                client.files_create_folder_v2(folder)
                print(f"created  {folder}")
            except Exception as ex:  # noqa: BLE001 — already exists is fine
                print(("exists   " if "conflict" in str(ex).lower() else "FAILED   ") + folder)
        # Move loose root-level raw videos into Drop Content Here.
        for f in dbx.list_folder(path_lower):
            if not f.name.lower().endswith(VIDEO_EXTS):
                continue
            try:
                client.files_move_v2(f.path, f"{drop}/{f.name}", autorename=True)
                print(f"moved IN  {f.name} -> {DROP_FOLDER}")
            except Exception as ex:  # noqa: BLE001
                print(f"move-in failed {f.name}: {ex}")

    # Move saved keepers out of processed/ into their brand's Ready To Post.
    for e in queue:
        mp = e.get("media_path") or ""
        if "/processed/" not in mp:
            continue
        prefix, fname = mp.split("/processed/", 1)[0], mp.rsplit("/", 1)[-1]
        dest = f"{prefix}/{READY_FOLDER}/{fname}"
        try:
            client.files_move_v2(mp, dest, autorename=True)
            e["media_path"] = dest
            try:
                e["media_url"] = dbx.shared_link(dest, raw=True)
            except Exception:  # noqa: BLE001
                pass
            changed = True
            print(f"moved OUT {fname} -> {READY_FOLDER}")
        except Exception as ex:  # noqa: BLE001
            print(f"move-out failed {fname}: {ex}")

    if changed:
        _save_json(QUEUE_PATH, queue)
    print("\n== Dropbox AFTER ==")
    debug_tree()


# HP Posts organization: filename-substring -> subfolder INSIDE HP Posts.
# First match wins (ordered); anything unmatched sweeps into Misc.
POSTS_CATEGORIES: list[tuple[tuple[str, ...], str]] = [
    (("talking",), "Talking Videos"),
    (("premium-fw",), "Fire & Water Backyard"),
    (("premium-ap",), "Estate Sport Court"),
    (("premium-jn",), "Plunge Pool Backyard"),
    (("premium-wf",), "Waterfall Pool"),
    (("premium-sd",), "Sod & Irrigation"),
    (("bry",), "Bryan Pool"),
    (("premium-bd", "barry"), "Barry Pool"),
    (("bob",), "Bob Putting Green"),
    (("june",), "June Pergola"),
    (("alice",), "Alice"),
    (("richard",), "Richard"),
    (("william",), "William Adams"),
]


def _posts_category(name: str) -> str:
    """Map a clip filename (or queue id) to its HP Posts subfolder. First match
    wins; anything unrecognized -> Misc. Shared by save_styled + organize_posts."""
    low = name.lower()
    for keys, folder in POSTS_CATEGORIES:
        if any(k in low for k in keys):
            return folder
    return "Misc"


def organize_posts() -> None:
    """Sort every loose clip in HP Posts into per-project subfolders that live
    INSIDE HP Posts (never outside), plus Talking Videos and Misc. Repoints the
    queue's media_path/media_url for moved clips. Existing subfolders untouched."""
    from services.ingest import dropbox_client as dbx  # lazy

    client = dbx._client()
    cat_for = _posts_category
    queue = _load_json(QUEUE_PATH, [])
    changed = moved = 0
    for path_lower, display in _top_level_folders(dbx):
        if not classify_brand(display):
            continue
        posts_dir = f"{display.rstrip('/')}/{READY_FOLDER}"
        files = [f for f in dbx.list_folder(posts_dir)
                 if f.name.lower().endswith(VIDEO_EXTS)]
        made: set[str] = set()
        for f in files:
            folder = cat_for(f.name)
            dest_dir = f"{posts_dir}/{folder}"
            if folder not in made:
                try:
                    client.files_create_folder_v2(dest_dir)
                    print(f"created  {folder}/")
                except Exception:  # noqa: BLE001 — already exists is fine
                    pass
                made.add(folder)
            dest = f"{dest_dir}/{f.name}"
            try:
                client.files_move_v2(f.path, dest, autorename=True)
            except Exception as ex:  # noqa: BLE001
                print(f"move failed {f.name}: {ex}")
                continue
            moved += 1
            print(f"{f.name} -> {folder}/")
            for e in queue:
                mp = e.get("media_path") or ""
                if mp and mp.rsplit("/", 1)[-1].lower() == f.name.lower():
                    # Just repoint the path — a Dropbox move keeps the existing
                    # shared link, so skip the slow per-file shared_link() call.
                    e["media_path"] = dest
                    changed += 1
    _save_json(QUEUE_PATH, queue)
    print(f"\nOrganized {moved} clip(s) into subfolders inside {READY_FOLDER} "
          f"({changed} queue entr{'y' if changed == 1 else 'ies'} repointed). Nothing posted.")


def _merge_move(client, src_path: str, dest_path: str) -> tuple[int, int]:
    """Move ``src_path`` into ``dest_path`` preserving structure. If dest doesn't
    exist, rename the whole folder in one op; else merge each child (subfolders move
    wholesale) and delete the emptied src. Returns (renamed, merged) counts."""
    try:
        client.files_get_metadata(src_path)
    except Exception:  # noqa: BLE001 — no such src
        return 0, 0
    dest_exists = True
    try:
        client.files_get_metadata(dest_path)
    except Exception:  # noqa: BLE001
        dest_exists = False
    if not dest_exists:
        try:
            client.files_move_v2(src_path, dest_path)
            print(f"renamed  {src_path}  ->  {dest_path}")
            return 1, 0
        except Exception as ex:  # noqa: BLE001
            print(f"rename failed {src_path}: {ex}"); return 0, 0
    merged = 0
    res = client.files_list_folder(src_path)
    children = list(res.entries)
    while getattr(res, "has_more", False):
        res = client.files_list_folder_continue(res.cursor); children += res.entries
    for en in children:
        nm = getattr(en, "name", "")
        child_src = getattr(en, "path_display", f"{src_path}/{nm}")
        try:
            client.files_move_v2(child_src, f"{dest_path}/{nm}", autorename=False)
            merged += 1
            print(f"merged   {nm}  ->  {dest_path}/")
        except Exception as ex:  # noqa: BLE001 — already present in dest
            print(f"skip {nm} (in dest already / {ex})")
    try:
        if not client.files_list_folder(src_path).entries:
            client.files_delete_v2(src_path)
            print(f"removed empty {src_path}")
    except Exception:  # noqa: BLE001
        pass
    return 0, merged


def move_saved_folder(src: str, dest: str) -> None:
    """Move every saved clip from ``src`` into ``dest`` keeping the EXACT subfolder
    structure and filenames (Dropbox move preserves shared links). ``src``/``dest``
    may be BARE folder names (applied under each brand root, e.g. ``HP Posts`` ->
    ``HP Auto Post``) OR absolute Dropbox paths (start with ``/``) for a single
    explicit move. Repoints queue media_paths from the old prefix to the new one."""
    from services.ingest import dropbox_client as dbx  # lazy

    client = dbx._client()
    queue = _load_json(QUEUE_PATH, [])
    renamed = merged = 0
    prefixes: list[tuple[str, str]] = []
    if src.startswith("/"):
        r, m = _merge_move(client, src.rstrip("/"), dest.rstrip("/"))
        renamed += r; merged += m
        prefixes.append((src.rstrip("/") + "/", dest.rstrip("/") + "/"))
    else:
        for _pl, display in _top_level_folders(dbx):
            if not classify_brand(display):
                continue
            base = display.rstrip("/")
            sp, dp = f"{base}/{src}", f"{base}/{dest}"
            r, m = _merge_move(client, sp, dp)
            renamed += r; merged += m
            prefixes.append((sp + "/", dp + "/"))
    changed = 0
    for e in queue:
        mp = e.get("media_path") or ""
        for sp, dp in prefixes:
            if mp.startswith(sp):
                e["media_path"] = dp + mp[len(sp):]; changed += 1; break
    _save_json(QUEUE_PATH, queue)
    print(f"\nMove done: {renamed} folder-rename(s), {merged} merged child(ren); "
          f"repointed {changed} queue path(s). Nothing posted.")


def process_folder(folder_path: str, folder_display: str, brand, dbx, *, dry_run: bool = False) -> list[dict]:
    """Process the videos directly inside one matched brand folder."""
    brand_key, display, default_tags = brand
    processed = set(_load_json(PROCESSED_PATH, []))
    created: list[dict] = []

    for f in _brand_videos(dbx, folder_path):
        if f.rev in processed:
            continue
        print(f"[{brand_key}] processing {f.name} from {folder_display}")
        if dry_run:
            created.append({"id": f"{brand_key}-DRYRUN-{_slug(f.name)}", "brand": brand_key})
            continue
        try:
            entries = _process_one(f, folder_display, brand_key, display, default_tags, dbx)
            created.extend(entries)
            processed.add(f.rev)
        except Exception as e:  # noqa: BLE001 — one bad video never kills the run
            print(f"[{brand_key}] FAILED {f.name}: {e}")

    _save_json(PROCESSED_PATH, sorted(processed))
    return created


def _speech_bounds(segments) -> tuple[float, float]:
    """(start, end) seconds spanning the spoken content, with small padding."""
    starts = [getattr(s, "start_seconds", None) for s in segments]
    ends = [getattr(s, "end_seconds", None) for s in segments]
    starts = [x for x in starts if x is not None]
    ends = [x for x in ends if x is not None]
    s0 = max(0.0, (min(starts) if starts else 0.0) - 0.2)
    e0 = (max(ends) if ends else 0.0) + 0.3
    if e0 <= s0:
        e0 = s0 + 5.0
    return s0, e0


def _windows(s: float, e: float, target: float | None = None) -> list[tuple[float, float, str]]:
    """Split [s, e] into back-to-back ~``target``-second chunks (default 20s).

    Each chunk becomes its own post, so one minute of footage yields ~3-4 posts.
    Chunks are equal-length and non-overlapping; a clip already near target
    length stays whole. ``CLIP_TARGET_SECONDS`` overrides the default.
    """
    target = target or float(os.getenv("CLIP_TARGET_SECONDS", "20"))
    total = max(0.0, e - s)
    if total <= target * 1.5:
        return [(round(s, 2), round(e, 2), "clip-1")]
    n = max(1, round(total / target))
    step = total / n
    out = []
    for i in range(n):
        a = s + i * step
        b = e if i == n - 1 else s + (i + 1) * step
        out.append((round(a, 2), round(b, 2), f"clip-{i + 1}"))
    return out


def _write_srt(segments, a: float, b: float, path: str) -> str | None:
    """Write an SRT for the segments inside [a,b], shifted to start at 0.

    Returns the path, or None if no speech falls in the window.
    """
    def _ts(t: float) -> str:
        t = max(0.0, t)
        h, rem = divmod(t, 3600)
        m, s = divmod(rem, 60)
        return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")

    lines: list[str] = []
    idx = 1
    for seg in segments:
        ss = getattr(seg, "start_seconds", None)
        ee = getattr(seg, "end_seconds", None)
        tx = (getattr(seg, "text", "") or "").strip()
        if ss is None or ee is None or not tx or ee <= a or ss >= b:
            continue
        s = max(ss, a) - a
        e = min(ee, b) - a
        if e <= s:
            continue
        lines.append(f"{idx}\n{_ts(s)} --> {_ts(e)}\n{tx}\n")
        idx += 1
    if idx == 1:
        return None
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


# Bold, TikTok-style burned caption look (ASS force_style).
_CAPTION_STYLE = (
    "FontName=DejaVu Sans,Fontsize=22,Bold=1,PrimaryColour=&H00FFFFFF&,"
    "OutlineColour=&H00000000&,BorderStyle=1,Outline=3,Shadow=1,"
    "Alignment=2,MarginV=180"
)


def _brand_logo(brand_key: str) -> str | None:
    """Path to a brand's watermark PNG (``content/brand/<key>-logo.png``) or None."""
    p = os.path.join(ROOT, "content", "brand", f"{brand_key}-logo.png")
    return p if os.path.exists(p) else None


def _edit_short(src: str, a: float, b: float, out_path: str, srt: str | None = None,
                mute: bool = False, music: str | None = None, logo: str | None = None) -> str:
    """Cut [a,b], reframe vertical 1080x1920. Optional bold captions, mute audio,
    looped background ``music``, and a top-right ``logo`` watermark (HP house style)."""
    import subprocess  # lazy, stdlib

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    dur = max(0.1, b - a)
    vchain = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    if srt:
        vchain += f",subtitles={srt}:force_style='{_CAPTION_STYLE}'"
    cmd = ["ffmpeg", "-y", "-ss", f"{a:.2f}", "-i", src]
    if music:
        cmd += ["-stream_loop", "-1", "-i", music]   # loop the track to fill the clip
    if logo:
        cmd += ["-i", logo]
    cmd += ["-t", f"{dur:.2f}"]
    if logo:
        li = 2 if music else 1   # logo is the last input
        cmd += ["-filter_complex",
                f"[0:v]{vchain}[bg];[{li}:v]scale=200:-1[lg];[bg][lg]overlay=W-w-28:28[v]",
                "-map", "[v]"]
        if music:
            cmd += ["-map", "1:a:0"]
        elif not mute:
            cmd += ["-map", "0:a:0?"]
    else:
        cmd += ["-vf", vchain]
        if music:
            cmd += ["-map", "0:v:0", "-map", "1:a:0"]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23"]
    if music:
        cmd += ["-c:a", "aac", "-b:a", "160k"]
    elif mute:
        cmd += ["-an"]
    else:
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    cmd += ["-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


# HP house caption voice (matched to their posted IG). Rotates a hook per clip.
_HP_HOOKS = (
    "Turned this backyard into a place you actually want to be.",
    "Luxury landscaping, redefined. ✨\U0001F33F",
    "A yard done right just hits different. \U0001F338\U0001F33F",
    "This is what happens when vision meets execution. ✨",
    "From overgrown to outdoor escape. \U0001F525\U0001F33F",
    "Backyard goals, upgraded. \U0001F4AF\U0001F33F",
    "Built to stand out and thrive. \U0001F331",
    "Good landscaping starts below the surface. \U0001F331\U0001F4A7",
)
_HP_CTA = "Call (979) 777-8851!!"
_HP_TAGS = "#TXOutdoorLiving #DreamBackyard #OutdoorLiving #backyardgoals"


def _hp_caption(seed: str) -> str:
    """HP house-style post caption: rotating hook -> phone CTA -> hashtags."""
    import zlib
    hook = _HP_HOOKS[zlib.crc32(seed.encode()) % len(_HP_HOOKS)]
    return f"{hook}\n\n{_HP_CTA}\n•\n•\n{_HP_TAGS}"


def _concat(parts: list[str], out_path: str, xfade: float = 0.8) -> str:
    """Join clips with smooth crossfades (not choppy hard cuts). Falls back to a
    plain concat if the crossfade graph fails (e.g. a part has no audio)."""
    import shutil  # lazy
    import subprocess  # lazy

    if len(parts) == 1:
        shutil.copy(parts[0], out_path)
        return out_path

    durs = []
    for p in parts:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", p],
            capture_output=True, text=True,
        )
        try:
            durs.append(float(r.stdout.strip()))
        except ValueError:
            durs.append(3.0)

    cmd = ["ffmpeg", "-y"]
    for p in parts:
        cmd += ["-i", p]
    fc = []
    vlab, alab, off = "[0:v]", "[0:a]", durs[0] - xfade
    for i in range(1, len(parts)):
        nv, na = f"[v{i}]", f"[a{i}]"
        fc.append(f"{vlab}[{i}:v]xfade=transition=fade:duration={xfade}:offset={off:.3f}{nv}")
        fc.append(f"{alab}[{i}:a]acrossfade=d={xfade}{na}")
        vlab, alab = nv, na
        off += durs[i] - xfade
    cmd += ["-filter_complex", ";".join(fc), "-map", vlab, "-map", alab,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out_path]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return out_path
    except subprocess.CalledProcessError:
        pass
    # Fallback: plain (hard) concat.
    lst = out_path + ".txt"
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p)}'\n")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out_path],
                   check=True, capture_output=True)
    os.remove(lst)
    return out_path


def _append_outro(main_path: str, outro_path: str, out_path: str, xfade: float = 0.6) -> str:
    """Crossfade the brand outro end-card onto the tail of a talking clip (keeps
    audio). Normalizes both to 1080x1920@30 so xfade/acrossfade never stutter on
    mismatched fps/size. Falls back to video-only xfade if the outro has no audio."""
    import shutil  # lazy
    import subprocess  # lazy

    if not os.path.exists(outro_path):
        shutil.copy(main_path, out_path)
        return out_path

    def _dur(p: str) -> float:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", p], capture_output=True, text=True)
        try:
            return float(r.stdout.strip())
        except ValueError:
            return 3.0

    off = max(0.0, _dur(main_path) - xfade)
    norm = ("fps=30,scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,setsar=1,format=yuv420p")
    vfc = (f"[0:v]{norm}[v0];[1:v]{norm}[v1];"
           f"[v0][v1]xfade=transition=fade:duration={xfade}:offset={off:.3f}[v]")
    afc = ("[0:a]aformat=sample_rates=48000:channel_layouts=stereo[a0];"
           "[1:a]aformat=sample_rates=48000:channel_layouts=stereo[a1];"
           f"[a0][a1]acrossfade=d={xfade}[a]")
    base = ["ffmpeg", "-y", "-i", main_path, "-i", outro_path]
    full = base + ["-filter_complex", f"{vfc};{afc}", "-map", "[v]", "-map", "[a]",
                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                   "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out_path]
    try:
        subprocess.run(full, check=True, capture_output=True)
        return out_path
    except subprocess.CalledProcessError:
        pass
    # Fallback: outro has no audio track — fade video, carry the main clip's audio.
    vonly = base + ["-filter_complex", vfc, "-map", "[v]", "-map", "0:a:0?",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out_path]
    subprocess.run(vonly, check=True, capture_output=True)
    return out_path


def _edit_tile(src: str, a: float, b: float, out_path: str, w: int, h: int) -> str:
    """Cut [a,b] as a ``w``x``h`` tile (scaled to fill, cropped). Muted. Used for
    both row panels (1080xH) and side-by-side column panels (Wx1920)."""
    import subprocess  # lazy

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    dur = max(0.1, b - a)
    vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
    subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{a:.2f}", "-i", src, "-t", f"{dur:.2f}", "-vf", vf,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-an",
         "-movflags", "+faststart", out_path],
        check=True, capture_output=True)
    return out_path


def _edit_short_4k(src: str, a: float, b: float, out_path: str) -> str:
    """Premium single-shot cut: true 4K vertical (2160x3840), lanczos scaling, a
    subtle slow push (Ken Burns) for cinematic motion, high-quality encode. Muted.
    Used by montage segments so the footage stays ultra-sharp."""
    import subprocess  # lazy

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    dur = max(0.1, b - a)
    fr = max(2, int(round(dur * 30)))
    # MONTAGE_HD=1 -> fast 1080x1920 encode (much quicker to render/fetch/finish);
    # else true 4K vertical. Same gentle Ken-Burns push either way.
    hd = os.getenv("MONTAGE_HD", "").strip().lower() in ("1", "true", "yes")
    if hd:
        vf = (
            "scale=1200:2134:force_original_aspect_ratio=increase:flags=lanczos,"
            "crop=1200:2134,"
            f"zoompan=z='min(zoom+0.00045,1.06)':d=1:x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':s=1080x1920:fps=30,"
            "setsar=1,format=yuv420p"
        )
        enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-an",
               "-movflags", "+faststart"]
    else:
        # gentle continuous zoom (1.00 -> ~1.06) over the cut = premium, never static
        vf = (
            "scale=2400:4267:force_original_aspect_ratio=increase:flags=lanczos,"
            "crop=2400:4267,"
            f"zoompan=z='min(zoom+0.00045,1.06)':d=1:x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':s=2160x3840:fps=30,"
            "setsar=1,format=yuv420p"
        )
        enc = ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-an",
               "-movflags", "+faststart"]
    subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{a:.2f}", "-i", src, "-t", f"{dur:.2f}", "-vf", vf,
         *enc, out_path],
        check=True, capture_output=True)
    return out_path


def _hstackN(parts: list[str], out_path: str) -> str:
    """Side-by-side (column) stack of equal-height tiles into one 1080x1920 clip."""
    import shutil  # lazy
    import subprocess  # lazy

    if len(parts) == 1:
        shutil.copy(parts[0], out_path)
        return out_path
    cmd = ["ffmpeg", "-y"]
    for p in parts:
        cmd += ["-i", p]
    n = len(parts)
    fc = "".join(f"[{i}:v]" for i in range(n)) + f"hstack=inputs={n}[v]"
    cmd += ["-filter_complex", fc, "-map", "[v]", "-shortest",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def _edit_panel(src: str, a: float, b: float, out_path: str, height: int) -> str:
    """Cut [a,b] as a full-width 1080x``height`` PANEL (keeps the horizontal
    framing) for vertical multi-panel stacks — HP's split-screen look. Muted;
    the stack carries no audio (trending sound is added at post time)."""
    import subprocess  # lazy

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    dur = max(0.1, b - a)
    vf = (f"scale=1080:{height}:force_original_aspect_ratio=increase,"
          f"crop=1080:{height},setsar=1")
    subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{a:.2f}", "-i", src, "-t", f"{dur:.2f}", "-vf", vf,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-an",
         "-movflags", "+faststart", out_path],
        check=True, capture_output=True)
    return out_path


def _stackN(parts: list[str], out_path: str) -> str:
    """Vertically stack equal-width panels into one 1080x1920 clip (HP split-screen).

    Panels are trimmed to the shortest input so the stack stays in sync; the
    result is silent (add trending audio in-app at post time)."""
    import shutil  # lazy
    import subprocess  # lazy

    if len(parts) == 1:
        shutil.copy(parts[0], out_path)
        return out_path
    cmd = ["ffmpeg", "-y"]
    for p in parts:
        cmd += ["-i", p]
    n = len(parts)
    fc = "".join(f"[{i}:v]" for i in range(n)) + f"vstack=inputs={n}[v]"
    cmd += ["-filter_complex", fc, "-map", "[v]", "-shortest",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def _concat_v(parts: list[str], out_path: str, xfade: float = 0.4) -> str:
    """Crossfade-concat VIDEO only (silent output) — for mixed silent montage
    segments where an audio crossfade isn't possible. Normalizes every segment to
    1080x1920@30 so xfade never chokes on mismatched fps/size. Plain-concat fallback."""
    import shutil  # lazy
    import subprocess  # lazy

    if len(parts) == 1:
        shutil.copy(parts[0], out_path)
        return out_path
    durs = []
    for p in parts:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", p], capture_output=True, text=True)
        try:
            durs.append(float(r.stdout.strip()))
        except ValueError:
            durs.append(3.0)
    n = len(parts)
    hd = os.getenv("MONTAGE_HD", "").strip().lower() in ("1", "true", "yes")
    tgt = "1080:1920" if hd else "2160:3840"
    cenc = (["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"] if hd
            else ["-c:v", "libx264", "-preset", "medium", "-crf", "18"])
    cmd = ["ffmpeg", "-y"]
    for p in parts:
        cmd += ["-i", p]
    fc = [f"[{i}:v]fps=30,scale={tgt}:flags=lanczos,setsar=1,format=yuv420p[n{i}]"
          for i in range(n)]
    vlab, off = "[n0]", durs[0] - xfade
    for i in range(1, n):
        nv = f"[v{i}]"
        fc.append(f"{vlab}[n{i}]xfade=transition=fade:duration={xfade}:offset={off:.3f}{nv}")
        vlab, off = nv, off + durs[i] - xfade
    cmd += ["-filter_complex", ";".join(fc), "-map", vlab, "-an",
            *cenc, "-movflags", "+faststart", out_path]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return out_path
    except subprocess.CalledProcessError:
        pass
    lst = out_path + ".txt"
    with open(lst, "w") as fh:
        for p in parts:
            fh.write(f"file '{os.path.abspath(p)}'\n")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-an",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-movflags", "+faststart", out_path], check=True, capture_output=True)
    os.remove(lst)
    return out_path


def _find_music(dbx) -> str | None:
    """Download the first audio file from a Dropbox folder whose name has 'music'."""
    for path_lower, display in _top_level_folders(dbx):
        if "music" in display.lower():
            auds = [f for f in dbx.list_folder(path_lower)
                    if f.name.lower().endswith((".mp3", ".wav", ".m4a", ".aac"))]
            if auds:
                return dbx.download(auds[0])
    return None


def _process_one(f, folder_display, brand_key, display, default_tags, dbx) -> list[dict]:
    """Download -> transcribe -> make ~10 vertical cuts -> upload -> review entries."""
    import shutil  # lazy, stdlib

    from services.caption import transcribe  # lazy (whisper)
    from services.write.free_writer import generate_caption  # lazy

    raw = dbx.download(f)
    # Safe filename (no spaces/commas) so ffmpeg paths never break on phone names.
    ext = os.path.splitext(f.name)[1] or ".mp4"
    base = _slug(f.name) or "clip"
    local = os.path.join(os.path.dirname(raw), f"{base}{ext}")
    if os.path.abspath(local) != os.path.abspath(raw):
        shutil.copy(raw, local)

    segments = transcribe(local)
    transcript = _transcript_text(segments)
    copy = generate_caption(
        {"transcript": transcript, "brand_name": display},
        default_hashtags=default_tags,
    )
    caption = _compose(copy)

    s0, e0 = _speech_bounds(segments)
    queue = _load_json(QUEUE_PATH, [])
    entries: list[dict] = []
    stamp = _dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")

    # Vertical chunks, NO burned subtitles (owner's call). The strong post
    # caption goes in the text field instead, used when the post is published.
    for i, (a, b, label) in enumerate(_windows(s0, e0)):
        out_name = f"{base}-{label}.mp4"
        out_local = os.path.join(os.path.dirname(local), out_name)
        try:
            _edit_short(local, a, b, out_local, srt=None)
        except Exception as ex:  # noqa: BLE001 — skip a bad cut, keep the rest
            print(f"[{brand_key}] cut {label} failed: {ex}")
            continue
        out_path = f"{folder_display.rstrip('/')}/processed/{out_name}"
        dbx.upload(out_local, out_path)
        url = dbx.shared_link(out_path, raw=True)
        entry = {
            "id": f"{brand_key}-{stamp}-{label}",
            "brand": brand_key,
            "text": caption,
            "media_url": url,
            "media_path": out_path,   # Dropbox path, so old versions can be deleted
            "platforms": list(REVIEW_PLATFORMS),
            "schedule": None,
            "status": "review",   # NEVER posts (poster only fires "pending")
            "error": None,
        }
        queue.append(entry)
        entries.append(entry)
        print(f"[{brand_key}] cut {label}: {a:.0f}-{b:.0f}s ({b - a:.0f}s) -> {out_path}")

    _save_json(QUEUE_PATH, queue)
    print(f"[{brand_key}] {len(entries)} cuts ready for review. caption: {caption[:70]!r}")
    return entries


def debug_tree() -> None:
    """Print what the Dropbox app can see (root + one level deep) for diagnosis."""
    from services.ingest import dropbox_client as dbx  # lazy

    client = dbx._client()
    print("== Dropbox app-folder contents (root) ==")
    res = client.files_list_folder("")
    if not res.entries:
        print("  (root is empty — nothing visible to the app)")
    for e in res.entries:
        is_dir = e.__class__.__name__ == "FolderMetadata"
        tag = classify_brand(e.name)
        label = f" -> brand={tag[0]}" if (is_dir and tag) else (" -> (unmatched)" if is_dir else "")
        print(f"  {'DIR ' if is_dir else 'file'} {getattr(e, 'path_display', e.name)}{label}")
        if is_dir:
            try:
                sub = client.files_list_folder(getattr(e, "path_lower", ""))
                for se in sub.entries:
                    print(f"        - {getattr(se, 'name', '?')}")
                if not sub.entries:
                    print("        (empty)")
            except Exception as ex:  # noqa: BLE001
                print(f"        (could not list: {ex})")


def _find_phrase_end(segments, phrase: str) -> float | None:
    """End-time (seconds) of where ``phrase`` is spoken, or None if not found.

    Prefers word-level timing; falls back to the segment containing the phrase.
    """
    norm = lambda s: re.sub(r"[^a-z]", "", s.lower())
    target = [norm(w) for w in phrase.split() if norm(w)]
    if not target:
        return None
    words = []
    for seg in segments:
        for w in (getattr(seg, "words", None) or []):
            words.append((norm(getattr(w, "text", "")), getattr(w, "end_seconds", None)))
    n = len(target)
    for i in range(len(words) - n + 1):
        if [words[i + j][0] for j in range(n)] == target and words[i + n - 1][1] is not None:
            return float(words[i + n - 1][1])
    # fallback: a segment whose text contains the phrase
    flat = " ".join(target)
    for seg in segments:
        txt = " ".join(norm(w) for w in (getattr(seg, "text", "") or "").split())
        if flat in txt and getattr(seg, "end_seconds", None) is not None:
            return float(seg.end_seconds)
    return None


def _first_word_after(segments, t0: float) -> float:
    """Start time of the first spoken word at/after ``t0`` (else ``t0``)."""
    times = []
    for seg in segments:
        for w in (getattr(seg, "words", None) or []):
            st = getattr(w, "start_seconds", None)
            if st is not None and st >= t0:
                times.append(st)
        ss = getattr(seg, "start_seconds", None)
        if ss is not None and ss >= t0:
            times.append(ss)
    return min(times) if times else t0


def recut(end_phrase: str, clip_index: int = 2, end_buffer: float = 1.0,
          start_lead: float | None = None) -> list[dict]:
    """Recut one chunk: start ``start_lead`` sec before the first word (if set),
    end ``end_buffer`` sec after ``end_phrase``. Never burns subtitles.

    Operates on the first video in the first matched brand folder. Returns the
    review entries created (one).
    """
    import shutil

    from services.caption import transcribe
    from services.ingest import dropbox_client as dbx

    for path_lower, display in _top_level_folders(dbx):
        brand = classify_brand(display)
        if not brand:
            continue
        vids = _brand_videos(dbx, path_lower)
        if not vids:
            continue
        brand_key, dispname, _tags = brand
        f = vids[0]
        raw = dbx.download(f)
        base = _slug(f.name) or "clip"
        ext = os.path.splitext(f.name)[1] or ".mp4"
        local = os.path.join(os.path.dirname(raw), f"{base}{ext}")
        if os.path.abspath(local) != os.path.abspath(raw):
            shutil.copy(raw, local)

        segments = transcribe(local)
        s0, e0 = _speech_bounds(segments)
        wins = _windows(s0, e0)
        a_chunk, b, _label = wins[max(0, min(clip_index - 1, len(wins) - 1))]
        if start_lead is not None:
            a = max(0.0, _first_word_after(segments, a_chunk) - start_lead)
        else:
            a = a_chunk
        t = _find_phrase_end(segments, end_phrase)
        end = (t + end_buffer) if t is not None else b
        print(f"[{brand_key}] recut clip {clip_index}: start {a:.1f}s, "
              f"phrase {'found @ %.1fs' % t if t is not None else 'NOT found (kept chunk end)'}, "
              f"end {end:.1f}s")
        out_name = f"{base}-clip{clip_index}-recut.mp4"
        out_local = os.path.join(os.path.dirname(local), out_name)
        _edit_short(local, a, end, out_local, srt=None)
        out_path = f"{display.rstrip('/')}/processed/{out_name}"
        dbx.upload(out_local, out_path)
        url = dbx.shared_link(out_path, raw=True)
        from services.write.free_writer import generate_caption  # lazy
        caption = _compose(generate_caption(
            {"transcript": _transcript_text(segments), "brand_name": dispname},
            default_hashtags=_tags,
        ))
        entry = {
            "id": f"{brand_key}-{_dt.datetime.utcnow():%Y%m%d%H%M%S}-clip{clip_index}-recut",
            "brand": brand_key, "text": caption, "media_url": url,
            "media_path": out_path,
            "platforms": list(REVIEW_PLATFORMS), "schedule": None,
            "status": "review", "error": None,
        }
        # Delete the old version(s) of THIS clip (queue entry + Dropbox file) so
        # only the latest recut remains — no sifting through messed-up versions.
        queue = _load_json(QUEUE_PATH, [])
        keep = []
        for e in queue:
            same = e.get("brand") == brand_key and (
                e["id"].endswith(f"clip-{clip_index}")
                or e["id"].endswith(f"clip{clip_index}-recut")
            )
            if same:
                mp = e.get("media_path")
                if mp:
                    try:
                        dbx.delete(mp)
                        print(f"[{brand_key}] deleted old: {mp}")
                    except Exception as ex:  # noqa: BLE001
                        print(f"[{brand_key}] could not delete {mp}: {ex}")
            else:
                keep.append(e)
        keep.append(entry)
        _save_json(QUEUE_PATH, keep)
        print(f"[{brand_key}] recut -> {out_path} (replaced {len(queue) - len(keep) + 1} old)")
        return [entry]
    print("recut: no brand folder with a video found.")
    return []


def _first_video(dbx, match: str | None = None):
    """(file, local_path, base, brand, display) for the first video (optionally
    one whose filename contains ``match``), or None."""
    import shutil
    for path_lower, display in _top_level_folders(dbx):
        brand = classify_brand(display)
        if not brand:
            continue
        vids = _brand_videos(dbx, path_lower)
        if match:
            m = match.lower()
            vids = [f for f in vids
                    if m in f.name.lower() or m in (getattr(f, "path", "") or "").lower()]
        if not vids:
            continue
        f = vids[0]
        raw = dbx.download(f)
        base = _slug(f.name) or "clip"
        ext = os.path.splitext(f.name)[1] or ".mp4"
        local = os.path.join(os.path.dirname(raw), f"{base}{ext}")
        if os.path.abspath(local) != os.path.abspath(raw):
            shutil.copy(raw, local)
        return f, local, base, brand, display
    return None


def _first_image(dbx, match: str | None = None) -> str | None:
    """Download the first IMAGE (optionally whose name/path contains ``match``)
    under any brand's Drop Content Here. Returns a local path or None. Used to add
    a finished-project 'result' end-slide from a photo the owner dropped in."""
    client = dbx._client()
    m = (match or "").lower()
    for path_lower, display in _top_level_folders(dbx):
        if not classify_brand(display):
            continue
        drop = f"{path_lower.rstrip('/')}/{DROP_FOLDER.lower()}"
        try:
            res = client.files_list_folder(drop, recursive=True)
        except Exception:  # noqa: BLE001
            continue
        imgs = []
        while True:
            for e in res.entries:
                if e.__class__.__name__ != "FileMetadata":
                    continue
                if not e.name.lower().endswith(IMAGE_EXTS):
                    continue
                fp = getattr(e, "path_display", "") or getattr(e, "path_lower", "")
                if m and m not in e.name.lower() and m not in fp.lower():
                    continue
                imgs.append(dbx.DropboxFile(path=fp, name=e.name,
                            size_bytes=int(getattr(e, "size", 0) or 0),
                            rev=getattr(e, "rev", "") or ""))
            if not getattr(res, "has_more", False):
                break
            res = client.files_list_folder_continue(res.cursor)
        if imgs:
            return dbx.download(imgs[0])
    return None


def _still_clip(img_path: str, out_path: str, dur: float = 3.5) -> str:
    """Make a ``dur``-second 2160x3840@30 clip from a still image with a slow
    Ken-Burns zoom — used as a 4K finished-project end-slide. Muted."""
    import subprocess  # lazy
    frames = max(1, int(dur * 30))
    vf = (f"scale=2376:4224:force_original_aspect_ratio=increase:flags=lanczos,"
          f"crop=2376:4224,"
          f"zoompan=z='min(zoom+0.0006,1.10)':d={frames}:s=2160x3840:fps=30,"
          f"setsar=1,format=yuv420p")
    subprocess.run(
        ["ffmpeg", "-y", "-loop", "1", "-i", img_path, "-t", f"{dur:.2f}",
         "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-an", "-movflags", "+faststart", out_path],
        check=True, capture_output=True)
    return out_path


def dump_transcript() -> None:
    """Transcribe EVERY video in the brand folders and print/commit a timestamped
    transcript per video, so good clip windows can be chosen by time."""
    import shutil
    from services.caption import transcribe  # lazy
    from services.ingest import dropbox_client as dbx  # lazy

    out_dir = os.path.join(ROOT, "content", "transcripts")
    os.makedirs(out_dir, exist_ok=True)
    match = (os.getenv("PIPELINE_VIDEO") or "").strip().lower()
    count = 0
    for path_lower, display in _top_level_folders(dbx):
        if not classify_brand(display):
            continue
        for f in _brand_videos(dbx, path_lower):
            fp_path = getattr(f, "path", "") or f.name
            if match and match not in fp_path.lower():
                continue
            raw = dbx.download(f)
            parent = os.path.basename(os.path.dirname(fp_path)) if fp_path else ""
            base = _slug(f"{parent}-{f.name}") or "clip"
            ext = os.path.splitext(f.name)[1] or ".mp4"
            local = os.path.join(os.path.dirname(raw), f"{base}{ext}")
            if os.path.abspath(local) != os.path.abspath(raw):
                shutil.copy(raw, local)
            try:
                segs = transcribe(local)
            except Exception as ex:  # noqa: BLE001 — silent/no-audio clip: skip it
                print(f"=== SKIP base={base} ({display}/{f.name}): no/unreadable audio ({ex}) ===")
                continue
            lines = [f"[{getattr(s, 'start_seconds', 0.0) or 0.0:6.1f} - "
                     f"{getattr(s, 'end_seconds', 0.0) or 0.0:6.1f}] "
                     f"{(getattr(s, 'text', '') or '').strip()}" for s in segs]
            txt = "\n".join(lines)
            with open(os.path.join(out_dir, f"{base}.txt"), "w", encoding="utf-8") as fp:
                fp.write(f"# {display}/{f.name}  (base={base})\n{txt}\n")
            print(f"=== TRANSCRIPT base={base}  ({display}/{f.name}, {len(segs)} seg) ===")
            print(txt)
            print()
            count += 1
    print(f"\nTranscribed {count} video(s).")


def dump_thumbs() -> None:
    """For every video, make a 3x2 contact sheet of sample frames (committed) so
    the footage can be 'seen' to choose good shots."""
    import subprocess  # lazy
    from services.ingest import dropbox_client as dbx  # lazy

    out_dir = os.path.join(ROOT, "content", "thumbs")
    os.makedirs(out_dir, exist_ok=True)
    # PIPELINE_VIDEO filters to one project/folder (matched against the FULL path,
    # e.g. "Alice Carport") so we don't thumbnail every video in the drop folder.
    match = (os.getenv("PIPELINE_VIDEO") or "").strip().lower()
    for path_lower, display in _top_level_folders(dbx):
        if not classify_brand(display):
            continue
        for f in _brand_videos(dbx, path_lower):
            fp = getattr(f, "path", "") or f.name
            if match and match not in fp.lower():
                continue
            raw = dbx.download(f)
            # Base = filename FIRST (keeps the unique timestamp within _slug's 40-char
            # cap) + short parent tag, so bulk-folder clips never collide/overwrite.
            parent = os.path.basename(os.path.dirname(fp)) if fp else ""
            base = (_slug(f.name) + "-" + _slug(parent)[:8]).strip("-") or "clip"
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nw=1:nk=1", raw],
                capture_output=True, text=True)
            try:
                dur = max(1.0, float(r.stdout.strip()))
            except ValueError:
                dur = 10.0
            # THUMB_FRAMES lets us make a DENSE contact sheet (default 6) to spot a
            # brief segment (e.g. a sky-drone shot) buried in a long walkthrough clip.
            try:
                nfr = max(6, int(os.getenv("THUMB_FRAMES", "6")))
            except ValueError:
                nfr = 6
            cols = 6 if nfr > 6 else 3
            rows = -(-nfr // cols)  # ceil
            fps = max(0.02, nfr / dur)
            sheet = os.path.join(out_dir, f"{base}.jpg")
            subprocess.run(
                ["ffmpeg", "-y", "-i", raw, "-vf",
                 f"fps={fps:.4f},scale=240:-1,tile={cols}x{rows}:padding=4:margin=4",
                 "-frames:v", "1", "-q:v", "4", sheet],
                check=False, capture_output=True)
            print(f"contact sheet {base}.jpg (dur={dur:.1f}s, {nfr} frames)")
        # IMAGES under Drop Content Here -> single thumbnail each (finished-project photos)
        client = dbx._client()
        drop = f"{path_lower.rstrip('/')}/{DROP_FOLDER.lower()}"
        try:
            ir = client.files_list_folder(drop, recursive=True)
        except Exception:  # noqa: BLE001
            ir = None
        imgs = []
        while ir is not None:
            for e in ir.entries:
                if e.__class__.__name__ == "FileMetadata" and e.name.lower().endswith(IMAGE_EXTS):
                    fp = getattr(e, "path_display", "") or getattr(e, "path_lower", "")
                    if not match or match in fp.lower():
                        imgs.append(dbx.DropboxFile(path=fp, name=e.name,
                                    size_bytes=int(getattr(e, "size", 0) or 0),
                                    rev=getattr(e, "rev", "") or ""))
            if not getattr(ir, "has_more", False):
                break
            ir = client.files_list_folder_continue(ir.cursor)
        for f in imgs:
            fp = getattr(f, "path", "") or f.name
            raw = dbx.download(f)
            parent = os.path.basename(os.path.dirname(fp)) if fp else ""
            base = _slug(f"img-{parent}-{f.name}") or "img"
            thumb = os.path.join(out_dir, f"{base}.jpg")
            subprocess.run(["ffmpeg", "-y", "-i", raw, "-vf", "scale=360:-1",
                            "-frames:v", "1", "-q:v", "4", thumb], check=False, capture_output=True)
            print(f"image thumb {base}.jpg  <- {fp}")


def fetch_ig_reference(brand_key: str = "hp", limit: int = 24) -> int:
    """Pull a brand's already-posted Instagram media (thumbnails + captions) so
    its established house style can be studied and matched on every new clip.
    Read-only Graph API call — never posts. Stdlib only (urllib)."""
    import json as _json  # lazy
    import urllib.request
    import urllib.parse
    from services.publish.brands import get_brand  # lazy

    creds = get_brand(brand_key)
    token, ig = creds.meta_access_token, creds.ig_user_id
    if not token or not ig:
        print(f"ig_reference: missing creds for {brand_key} (need token + ig_user_id).")
        return 0
    fields = ("id,caption,media_type,media_product_type,thumbnail_url,media_url,"
              "permalink,timestamp,like_count,comments_count")
    url = (f"https://graph.facebook.com/v21.0/{ig}/media?fields={fields}"
           f"&limit={int(limit)}&access_token={urllib.parse.quote(token)}")
    out_dir = os.path.join(ROOT, "content", "reference", brand_key)
    os.makedirs(out_dir, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            data = _json.loads(r.read().decode())
    except Exception as ex:  # noqa: BLE001 — surface API/permission errors plainly
        print(f"ig_reference: Graph API call failed: {ex}")
        return 0
    items = data.get("data", [])
    lines = [f"# {brand_key.upper()} Instagram — {len(items)} recent posts (house-style reference)\n"]
    n = 0
    for it in items:
        mid = it.get("id", "")
        cap = (it.get("caption") or "").strip()
        mt, pt = it.get("media_type", ""), it.get("media_product_type", "")
        lines.append(f"\n## {mid}  [{mt}/{pt}]  ❤ {it.get('like_count')} 💬 {it.get('comments_count')}\n"
                     f"{it.get('permalink', '')}\n\n{cap}\n")
        thumb = it.get("thumbnail_url") or (it.get("media_url") if mt == "IMAGE" else None)
        if thumb:
            try:
                urllib.request.urlretrieve(thumb, os.path.join(out_dir, f"{mid}.jpg"))
                n += 1
            except Exception as ex:  # noqa: BLE001
                print(f"thumb fail {mid}: {ex}")
    with open(os.path.join(out_dir, "captions.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nig_reference: {len(items)} posts, {n} thumbnails -> content/reference/{brand_key}/")
    return n


def ingest_clip(name: str, src_path: str, brand_key: str = "hp") -> dict | None:
    """Upload a ready-made local clip into a brand's Dropbox processed/ folder and
    add a ``status:"review"`` queue entry — used to save an externally-edited clip
    as a keeper. Never posts (review only)."""
    from services.ingest import dropbox_client as dbx  # lazy

    if not os.path.exists(src_path):
        print(f"ingest_clip: file not found {src_path}")
        return None
    display = None
    for path_lower, disp in _top_level_folders(dbx):
        b = classify_brand(disp)
        if b and b[0] == brand_key:
            display = disp
            break
    if not display:
        print(f"ingest_clip: no Dropbox folder for brand {brand_key}")
        return None
    nm = _slug(name) or "clip"
    out_path = f"{display.rstrip('/')}/processed/{nm}.mp4"
    dbx.upload(src_path, out_path)
    url = dbx.shared_link(out_path, raw=True)
    queue = [e for e in _load_json(QUEUE_PATH, []) if e.get("id") != f"{brand_key}-{nm}"]
    entry = {
        "id": f"{brand_key}-{nm}", "brand": brand_key,
        "text": _hp_caption(nm) if brand_key == "hp" else "",
        "media_url": url, "media_path": out_path,
        "platforms": list(REVIEW_PLATFORMS), "schedule": None,
        "status": "review", "error": None,
    }
    queue.append(entry)
    _save_json(QUEUE_PATH, queue)
    print(f"ingest_clip: saved {brand_key}-{nm} -> {out_path} (status=review)")
    return entry


def fetch_previews(which: str = "all") -> int:
    """Download finished review clips from Dropbox into ``content/preview/`` so
    they can be viewed/sent directly (Dropbox is unreachable from some sandboxes).
    ``which`` is "all" or a comma-separated id list. Never posts."""
    from services.ingest import dropbox_client as dbx  # lazy

    client = dbx._client()
    out_dir = os.path.join(ROOT, "content", "preview")
    os.makedirs(out_dir, exist_ok=True)
    sel = which.strip().lower()
    ids = None if sel in ("all", "") else {x.strip() for x in which.split(",") if x.strip()}
    queue = _load_json(QUEUE_PATH, [])
    n = 0
    for e in queue:
        if ids is not None and e.get("id") not in ids:
            continue
        mp = e.get("media_path")
        if not mp:
            continue
        dest = os.path.join(out_dir, f"{e['id']}.mp4")
        try:
            client.files_download_to_file(dest, mp)
            # GitHub blocks files >100MB. 4K previews can exceed that, so if the
            # download is too big to commit, transcode in place to a 4K proxy
            # (same 2160x3840, higher CRF) that fits under the limit. Quality
            # stays high; it's only the git bridge that needs it small.
            import subprocess  # lazy, stdlib
            CAP = 95 * 1024 * 1024
            if os.path.getsize(dest) > CAP:
                for crf in (20, 22, 24, 26):
                    tmp = dest + ".proxy.mp4"
                    subprocess.run(
                        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", dest,
                         "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                         "-movflags", "+faststart", tmp],
                        check=True)
                    if os.path.getsize(tmp) <= CAP:
                        os.replace(tmp, dest)
                        print(f"fetched {e['id']} (proxied crf{crf}, "
                              f"{os.path.getsize(dest)//(1024*1024)}MB)")
                        break
                    os.remove(tmp)
                else:
                    print(f"fetched {e['id']} (WARN: still >95MB after crf26)")
            else:
                print(f"fetched {e['id']}")
            n += 1
        except Exception as ex:  # noqa: BLE001
            # Never leave an oversized/partial file behind — it would be force-added
            # and rejected by GitHub's 100MB push limit, blocking the whole commit.
            if os.path.exists(dest) and os.path.getsize(dest) > 95 * 1024 * 1024:
                os.remove(dest)
            print(f"fetch failed {e['id']}: {ex}")
    print(f"\n{n} preview(s) in content/preview/")
    return n


def delete_ids(ids: list[str]) -> list[dict]:
    """Delete ONLY the given queue ids — each clip's Dropbox file AND its queue
    entry. Targeted (unlike prune_clips which keeps a whitelist). Never posts."""
    from services.ingest import dropbox_client as dbx  # lazy

    drop = {i.strip() for i in ids if i.strip()}
    queue = _load_json(QUEUE_PATH, [])
    kept, removed = [], 0
    for e in queue:
        if e.get("id") not in drop:
            kept.append(e)
            continue
        mp = e.get("media_path")
        if mp:
            try:
                dbx.delete(mp)
            except Exception as ex:  # noqa: BLE001 — a missing file shouldn't stop the delete
                print(f"delete failed {mp}: {ex}")
        print(f"deleted {e.get('id')}")
        removed += 1
    _save_json(QUEUE_PATH, kept)
    print(f"\nDeleted {removed} clip(s); {len(kept)} remain.")
    return kept


def clean_ready_orphans() -> None:
    """Delete any file in each brand's ``Ready To Post`` that is NOT referenced by
    a current queue entry — i.e. stale/old versions of clips that were since edited.
    Keeps Ready To Post showing only the current saved set. Never posts."""
    from services.ingest import dropbox_client as dbx  # lazy

    client = dbx._client()
    queue = _load_json(QUEUE_PATH, [])
    keep = {(e.get("media_path") or "").lower() for e in queue}
    removed = 0
    for path_lower, display in _top_level_folders(dbx):
        if not classify_brand(display):
            continue
        ready = f"{display.rstrip('/')}/{READY_FOLDER}"
        try:
            res = client.files_list_folder(ready)
        except Exception:  # noqa: BLE001 — folder may not exist
            continue
        for e in res.entries:
            if e.__class__.__name__ != "FileMetadata":
                continue
            fp = getattr(e, "path_display", "") or getattr(e, "path_lower", "")
            if not fp.lower().endswith(VIDEO_EXTS):
                continue
            if fp.lower() in keep:
                continue
            try:
                dbx.delete(fp)
                removed += 1
                print(f"removed stale saved: {fp}")
            except Exception as ex:  # noqa: BLE001
                print(f"clean failed {fp}: {ex}")
    print(f"\nRemoved {removed} stale file(s) from {READY_FOLDER}.")


def demote_ids(which: str) -> list[dict]:
    """Move clips OUT of ``Ready To Post`` back into ``processed/`` (un-save).
    ``which`` is "all" or a comma id list. Status stays ``review``. Never posts."""
    from services.ingest import dropbox_client as dbx  # lazy

    client = dbx._client()
    sel = which.strip().lower()
    ids = None if sel in ("all", "") else {x.strip() for x in which.split(",") if x.strip()}
    queue = _load_json(QUEUE_PATH, [])
    moved = 0
    for e in queue:
        if ids is not None and e.get("id") not in ids:
            continue
        mp = e.get("media_path") or ""
        if f"/{READY_FOLDER}/" not in mp:
            continue
        prefix, fname = mp.split(f"/{READY_FOLDER}/", 1)[0], mp.rsplit("/", 1)[-1]
        dest = f"{prefix}/processed/{fname}"
        try:
            client.files_move_v2(mp, dest, autorename=True)
            e["media_path"] = dest
            try:
                e["media_url"] = dbx.shared_link(dest, raw=True)
            except Exception:  # noqa: BLE001
                pass
            moved += 1
            print(f"demoted {e.get('id')} -> processed/")
        except Exception as ex:  # noqa: BLE001
            print(f"demote failed {e.get('id')}: {ex}")
    if moved:
        _save_json(QUEUE_PATH, queue)
    print(f"\nDemoted {moved} clip(s) out of {READY_FOLDER}. Nothing posted.")
    return queue


def promote_ids(ids: list[str]) -> list[dict]:
    """Move ONLY the given queue ids from ``processed/`` into the brand's
    ``Ready To Post`` folder (approved keepers). Status stays ``review`` so the
    poster never touches them — this is a 'save it' action, not a publish."""
    from services.ingest import dropbox_client as dbx  # lazy

    client = dbx._client()
    want = {i.strip() for i in ids if i.strip()}
    queue = _load_json(QUEUE_PATH, [])
    moved = 0
    for e in queue:
        if e.get("id") not in want:
            continue
        mp = e.get("media_path") or ""
        if "/processed/" not in mp:
            print(f"skip {e.get('id')}: not in processed/ ({mp})")
            continue
        prefix, fname = mp.split("/processed/", 1)[0], mp.rsplit("/", 1)[-1]
        dest = f"{prefix}/{READY_FOLDER}/{fname}"
        try:
            client.files_move_v2(mp, dest, autorename=True)
            e["media_path"] = dest
            try:
                e["media_url"] = dbx.shared_link(dest, raw=True)
            except Exception:  # noqa: BLE001
                pass
            moved += 1
            print(f"promoted {e.get('id')} -> {READY_FOLDER}/{fname}")
        except Exception as ex:  # noqa: BLE001
            print(f"promote failed {e.get('id')}: {ex}")
    if moved:
        _save_json(QUEUE_PATH, queue)
    print(f"\nPromoted {moved} clip(s) to {READY_FOLDER}. Nothing posted.")
    return queue


def save_styled(dir_rel: str) -> list[dict]:
    """Upload locally-finished clips (e.g. logo+outro versions) straight into each
    brand's HP Posts folder and repoint the matching queue entry. Status stays
    ``review`` — this 'saves' an externally-styled keeper without posting.

    ``dir_rel`` holds files named like the queue id (``hp-bryan-02.mp4``) or the
    id minus the brand prefix (``bryan-02.mp4``). Replaces the old processed/
    file with the styled one in HP Posts; the previous file is removed."""
    from services.ingest import dropbox_client as dbx  # lazy

    src_dir = dir_rel if os.path.isabs(dir_rel) else os.path.join(ROOT, dir_rel)
    queue = _load_json(QUEUE_PATH, [])
    saved = 0
    for e in queue:
        cid = e.get("id", "")
        cands = [f"{cid}.mp4"]
        if "-" in cid:
            cands.append(cid.split("-", 1)[1] + ".mp4")
        local = next((os.path.join(src_dir, c) for c in cands
                      if os.path.exists(os.path.join(src_dir, c))), None)
        if not local:
            continue
        mp = e.get("media_path") or ""
        fname = mp.rsplit("/", 1)[-1] if mp else f"{cid}.mp4"
        if "/processed/" in mp:
            prefix = mp.split("/processed/", 1)[0]
        elif f"/{READY_FOLDER}/" in mp:
            prefix = mp.split(f"/{READY_FOLDER}/", 1)[0]
        elif "/" in mp:
            prefix = mp.rsplit("/", 2)[0]
        else:
            print(f"save_styled: can't derive folder for {cid} ({mp})")
            continue
        # Save straight into the clip's project subfolder INSIDE HP Posts so new
        # keepers are always organized (Dropbox auto-creates the subfolder).
        cat = _posts_category(fname if fname else cid)
        dest = f"{prefix}/{READY_FOLDER}/{cat}/{fname}"
        dbx.upload(local, dest)
        if mp and mp != dest:
            try:
                dbx.delete(mp)
            except Exception as ex:  # noqa: BLE001 — missing old file is fine
                print(f"save_styled: old file delete skipped {mp}: {ex}")
        try:
            e["media_url"] = dbx.shared_link(dest, raw=True)
        except Exception:  # noqa: BLE001
            pass
        e["media_path"] = dest
        e["status"] = "review"
        saved += 1
        print(f"saved styled {cid} -> {dest}")
    if saved:
        _save_json(QUEUE_PATH, queue)
    print(f"\nSaved {saved} styled clip(s) to {READY_FOLDER}. Nothing posted.")
    return queue


def copy_styled(dir_rel: str, folder: str) -> int:
    """Upload locally-finished clips to a SECOND Dropbox folder (e.g. 'HP Tiktok')
    as a pure copy — no queue repoint, nothing deleted, nothing posted. Runs after
    save_styled so a clip can live in HP Posts AND another folder at once."""
    from services.ingest import dropbox_client as dbx  # lazy

    src_dir = dir_rel if os.path.isabs(dir_rel) else os.path.join(ROOT, dir_rel)
    queue = _load_json(QUEUE_PATH, [])
    n = 0
    for e in queue:
        cid = e.get("id", "")
        cands = [f"{cid}.mp4"]
        if "-" in cid:
            cands.append(cid.split("-", 1)[1] + ".mp4")
        local = next((os.path.join(src_dir, c) for c in cands
                      if os.path.exists(os.path.join(src_dir, c))), None)
        if not local:
            continue
        mp = e.get("media_path") or ""
        fname = mp.rsplit("/", 1)[-1] if mp else f"{cid}.mp4"
        prefix = mp.rsplit("/", 2)[0] if mp.count("/") >= 2 else "/HP-Content Auto."
        dest = f"{prefix}/{folder}/{fname}"
        dbx.upload(local, dest)
        n += 1
        print(f"copied {cid} -> {dest}")
    print(f"\nCopied {n} clip(s) to {folder}. Nothing posted.")
    return n


# Folder-name fragments that mark a clip as a SAVED/finished clip (case-insensitive).
# Covers the HP Posts -> HP Auto Post rename plus the HP Tiktok mirror.
SAVED_MARKERS = ("/hp posts/", "/hp auto post/", "/hp tiktok/", "/hp tik tok/")


def swap_outro(ids_csv: str) -> None:
    """Surgically replace the last OUTRO_SEC seconds (the old 8851 brand outro) of
    each saved clip with the current brand outro (content/brand/outro.mp4) — nothing
    else changes. Downloads each clip, trims the old tail, appends the normalized new
    outro, re-uploads to the SAME Dropbox path, then re-downloads to PROVE the swap
    stuck. Both outros are 3.0s so the body is left exactly intact.

    ids_csv = comma queue ids, OR "all" to scan every saved clip across HP Auto Post /
    HP Posts / HP Tiktok (rename-agnostic) and swap only the ones still on 8851."""
    from services.ingest import dropbox_client as dbx  # lazy
    import subprocess  # lazy
    import time  # lazy

    OUTRO_SEC = 3.0
    client = dbx._client()
    queue = _load_json(QUEUE_PATH, [])
    by_id = {e.get("id"): e for e in queue}
    work = os.path.join(os.getenv("INGEST_DOWNLOAD_DIR", "."), "swapoutro")
    os.makedirs(work, exist_ok=True)
    proof_dir = os.path.join(ROOT, "content", "preview")
    os.makedirs(proof_dir, exist_ok=True)

    def _dur(p: str) -> float:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", p], capture_output=True, text=True)
        try:
            return float(r.stdout.strip())
        except ValueError:
            return 0.0

    def _dl(dest: str, path: str, tries: int = 4) -> bool:
        for i in range(tries):
            try:
                client.files_download_to_file(dest, path); return True
            except Exception as ex:  # noqa: BLE001 — transient conn resets happen
                if "not_found" in str(ex).lower() or i == tries - 1:
                    if i == tries - 1:
                        print(f"  download error ({path}): {ex}")
                    return False
                time.sleep(2 * (i + 1))
        return False

    def _up(local: str, path: str, tries: int = 4) -> bool:
        for i in range(tries):
            try:
                dbx.upload(local, path); return True
            except Exception as ex:  # noqa: BLE001
                if i == tries - 1:
                    print(f"  upload error ({path}): {ex}"); return False
                time.sleep(2 * (i + 1))
        return False

    # normalize the new outro once (1080x1920@30, aac stereo)
    on = os.path.join(work, "_outro_new.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i",
                    os.path.join(ROOT, "content", "brand", "outro.mp4"), "-vf",
                    "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
                    "fps=30,setsar=1,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "18", "-c:a", "aac", "-ar", "44100", "-ac", "2", on], check=True)

    # detection reference: the OLD (8851) outro's phone-number band. A clip is only
    # swapped if its final frame matches this band — clips on the new outro or ending
    # on content are left untouched.
    import numpy as np  # lazy
    from PIL import Image  # lazy
    ref = np.asarray(Image.open(os.path.join(ROOT, "content", "brand", "outro_ref_8851.png"))
                     .convert("L")).astype("int16")
    THRESH = 4.5  # 8851 card ~1, new card ~8.5, content ~90

    def _band_diff(clip: str, d: float, save_png: str | None = None) -> float:
        fp = save_png or os.path.join(work, "lastframe.png")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{max(0, d - 0.12):.2f}",
                        "-i", clip, "-frames:v", "1", "-s", "1080x1920", fp], check=False)
        try:
            b = np.asarray(Image.open(fp).convert("L"))[1180:1420, :].astype("int16")
            return float(np.abs(b - ref).mean())
        except Exception:  # noqa: BLE001
            return 999.0

    # One recursive listing of the whole app scope: powers both the basename index
    # (id-mode self-heal) and the "all" saved-clip sweep.
    ents: list = []
    try:
        res = client.files_list_folder("", recursive=True)
        ents = list(res.entries)
        while getattr(res, "has_more", False):
            res = client.files_list_folder_continue(res.cursor); ents += res.entries
    except Exception as ex:  # noqa: BLE001
        print(f"swap_outro: could not list app scope: {ex}")
    index: dict = {}
    for en in ents:
        nm = getattr(en, "name", "")
        if not nm.lower().endswith(".mp4"):
            continue
        p = getattr(en, "path_display", None) or getattr(en, "path_lower", "")
        key = nm.lower()
        if key not in index or (f"/{READY_FOLDER}/" in p and f"/{READY_FOLDER}/" not in index[key]):
            index[key] = p
    print(f"swap_outro: indexed {len(index)} mp4(s) across the app")

    # Build the target list: (cid, dropbox_path). "all" = every saved clip anywhere.
    targets: list[tuple[str, str]] = []
    if ids_csv.strip().lower() == "all":
        seen = set()
        for en in ents:
            nm = getattr(en, "name", "")
            if not nm.lower().endswith(".mp4"):
                continue
            p = getattr(en, "path_display", None) or getattr(en, "path_lower", "")
            pl = p.lower()
            if not any(m in pl for m in SAVED_MARKERS) or p in seen:
                continue
            seen.add(p)
            targets.append((nm.rsplit(".", 1)[0], p))
        folders = sorted({p.rsplit("/", 1)[0] for _c, p in targets})
        print(f"swap_outro ALL: {len(targets)} saved clip(s) across {len(folders)} folder(s):")
        for fld in folders:
            print(f"    {fld}")
    else:
        for cid in [x.strip() for x in ids_csv.split(",") if x.strip()]:
            e = by_id.get(cid)
            mp = (e or {}).get("media_path") or ""
            real = index.get(mp.rsplit("/", 1)[-1].lower()) or mp
            if not real:
                print(f"swap_outro: {cid} not found / no path"); continue
            targets.append((cid, real))

    n = skipped = failed = verify_fail = 0
    report: list[dict] = []
    proof_saved = 0
    for cid, path in targets:
        src = os.path.join(work, "src.mp4")
        if os.path.exists(src):
            os.remove(src)
        if not _dl(src, path):
            print(f"download failed: {cid} ({path})"); failed += 1
            report.append({"id": cid, "path": path, "status": "download_failed"}); continue
        d = _dur(src)
        if d <= OUTRO_SEC + 0.5:
            print(f"skip {cid} (too short {d:.2f}s)"); skipped += 1
            report.append({"id": cid, "path": path, "status": "too_short"}); continue
        before = _band_diff(src, d)
        if before >= THRESH:
            print(f"skip {cid} (already new / no 8851, diff={before:.1f})"); skipped += 1
            report.append({"id": cid, "path": path, "before": round(before, 1),
                           "status": "already_new"}); continue
        body = os.path.join(work, "body.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-t", f"{d - OUTRO_SEC:.3f}",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-ar", "44100", "-ac", "2", body], check=True)
        lst = os.path.join(work, "l.txt")
        with open(lst, "w") as fh:
            fh.write(f"file '{os.path.abspath(body)}'\nfile '{os.path.abspath(on)}'\n")
        final = os.path.join(work, "final.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-ar", "44100", "-ac", "2", final], check=True)
        if not _up(final, path):
            failed += 1
            report.append({"id": cid, "path": path, "before": round(before, 1),
                           "status": "upload_failed"}); continue
        # PROVE it: re-download the just-uploaded file and re-measure the band.
        chk = os.path.join(work, "chk.mp4")
        if os.path.exists(chk):
            os.remove(chk)
        after = 999.0
        if _dl(chk, path):
            png = None
            if proof_saved < 10:
                png = os.path.join(proof_dir, f"verify-{cid}.png")
                proof_saved += 1
            after = _band_diff(chk, _dur(chk), save_png=png)
        if after < THRESH:
            print(f"VERIFY FAILED {cid}: still 8851 after upload (after={after:.1f})")
            verify_fail += 1
            report.append({"id": cid, "path": path, "before": round(before, 1),
                           "after": round(after, 1), "status": "verify_failed"})
        else:
            n += 1
            short = path.split("/HP Auto Post/")[-1].split("/HP Posts/")[-1]
            print(f"SWAPPED+VERIFIED {cid}  (before={before:.1f} after={after:.1f})  {short}")
            report.append({"id": cid, "path": path, "before": round(before, 1),
                           "after": round(after, 1), "status": "swapped_verified"})
        for f in (src, body, final, lst, chk):
            try: os.remove(f)
            except OSError: pass
    rep_path = os.path.join(ROOT, "content", "reference", "swap_outro_report.json")
    os.makedirs(os.path.dirname(rep_path), exist_ok=True)
    _save_json(rep_path, report)
    print(f"\nswap_outro done: {n} swapped+verified, {skipped} left alone "
          f"(already new / short), {failed} download/upload-failed, "
          f"{verify_fail} VERIFY-FAILED. Report -> content/reference/swap_outro_report.json")
    if verify_fail:
        print("WARNING: some uploads did not take effect — re-run to retry those.")


def prune_clips(keep_ids: list[str]) -> list[dict]:
    """Delete every queued clip NOT in ``keep_ids`` — both its Dropbox file and
    its queue entry — leaving only the kept set. Clears stale batches so the
    review folder shows only the current clips. Never posts anything."""
    from services.ingest import dropbox_client as dbx  # lazy

    keep = {k.strip() for k in keep_ids if k.strip()}
    queue = _load_json(QUEUE_PATH, [])
    kept, removed = [], 0
    for e in queue:
        if e.get("id") in keep:
            kept.append(e)
            continue
        mp = e.get("media_path")
        if mp:
            try:
                dbx.delete(mp)
            except Exception as ex:  # noqa: BLE001 — a missing file shouldn't stop the purge
                print(f"delete failed {mp}: {ex}")
        print(f"pruned {e.get('id')}")
        removed += 1
    _save_json(QUEUE_PATH, kept)
    print(f"\nPruned {removed} old clip(s); kept {len(kept)}.")
    return kept


# ---- SupoClip-style auto highlight selection (free, local Whisper, no LLM) ----
# Words that signal a strong hook/payoff in landscaping/reno talking-head clips.
HOOK_WORDS = (
    "finished", "finally", "reveal", "check it out", "check this out", "before",
    "after", "transformation", "transformed", "renovated", "renovation", "favorite",
    "beautiful", "expensive", "crazy", "insane", "look at", "turned out", "dream",
    "results", "result", "best", "perfect", "love",
)
FILLER_WORDS = ("um ", "uh ", " like ", "you know", "i mean", "kind of", "sort of")


def _score_segment_text(text: str, dur: float) -> float:
    """Heuristic 'is this a good moment' score for a stretch of speech (no LLM).

    Rewards lively delivery (words/sec) and hook words; penalizes filler and
    lengths far from the ~15s sweet spot. Stands in for SupoClip's paid LLM.
    """
    t = (text or "").lower()
    words = re.findall(r"[a-z']+", t)
    if not words or dur <= 0:
        return 0.0
    density = min((len(words) / dur) / 3.0, 1.0)      # ~3 words/sec reads as lively
    hooks = sum(1 for h in HOOK_WORDS if h in t)
    filler = sum(t.count(f) for f in FILLER_WORDS)
    score = density + 0.6 * hooks - 0.15 * filler
    score -= abs(dur - 15.0) / 30.0                   # prefer a satisfying ~15s
    return score


def _pick_highlights(segments, n: int = 4, min_len: float = 7.0,
                     max_len: float = 20.0) -> list[tuple[float, float, str]]:
    """Pick up to ``n`` non-overlapping [start,end] windows snapped to sentence
    (segment) boundaries, ranked by :func:`_score_segment_text`.

    This is SupoClip's 'find the best moments' brain, done locally for $0. Silent
    footage has no segments, so it returns [] (b-roll needs the montage path).
    """
    segs = [s for s in segments
            if getattr(s, "end_seconds", 0) > getattr(s, "start_seconds", 0)
            and (getattr(s, "text", "") or "").strip()]
    candidates: list[tuple[float, float, float]] = []
    for i in range(len(segs)):
        j = i
        while j < len(segs) and (segs[j].end_seconds - segs[i].start_seconds) <= max_len:
            a, b = segs[i].start_seconds, segs[j].end_seconds
            if (b - a) >= min_len:
                text = " ".join(s.text for s in segs[i:j + 1])
                candidates.append((_score_segment_text(text, b - a), a, b))
            j += 1
    candidates.sort(key=lambda c: c[0], reverse=True)
    picked: list[tuple[float, float]] = []
    for score, a, b in candidates:
        if score <= 0:
            continue
        if all(b <= pa or a >= pb for pa, pb in picked):
            picked.append((a, b))
            if len(picked) >= n:
                break
    picked.sort()
    return [(round(a, 2), round(b, 2), f"auto-{k + 1}") for k, (a, b) in enumerate(picked)]


def auto_highlights(n: int = 4, match: str | None = None) -> list[dict]:
    """Transcribe one narrated video locally and auto-cut its best moments into
    review clips — SupoClip's brain, free (faster-whisper, no AssemblyAI/LLM key).

    Targets the video whose filename contains ``match`` (or PIPELINE_VIDEO, else
    the first video found). Silent b-roll yields nothing — use the montage path.
    """
    from services.caption import transcribe  # lazy
    from services.ingest import dropbox_client as dbx  # lazy

    match = match or os.getenv("PIPELINE_VIDEO") or None
    ctx = _first_video(dbx, match)
    if not ctx:
        print("auto_highlights: no matching video found.")
        return []
    _f, _local, base, _brand, _display = ctx
    wins = _pick_highlights(transcribe(_local), n=n)
    if not wins:
        print(f"auto_highlights: no speech windows in {base} (silent b-roll?).")
        return []
    print(f"auto_highlights: {base} -> {[(a, b) for a, b, _ in wins]}")
    specs = [{"name": nm, "video": match, "start": a, "end": b} for a, b, nm in wins]
    return cut_windows(specs)


def cut_montage(spec: dict) -> dict | None:
    """Assemble a dynamic, layout-shifting montage from raw footage.

    ``spec`` = {name, segments:[...], xfade?}. Each segment is either a single
    shot ``{"shot": [video, start, end]}`` or an N-up stack
    ``{"panels": [[video, start, end], ...]}`` (2 or 3 tiles). Segments render to
    1080x1920 and crossfade together (video-only, silent — add trending audio at
    post). Mixing 3-up -> single -> 2-up gives the energetic, changing-views feel."""
    from services.ingest import dropbox_client as dbx  # lazy

    name = _slug(spec.get("name", "montage")) or "montage"
    vid_cache: dict = {}

    def resolve(match):
        k = (match or "").lower()
        if k not in vid_cache:
            vid_cache[k] = _first_video(dbx, match or None)
        return vid_cache[k]

    seg_clips: list[str] = []
    base_ctx = None
    workdir = "."
    import subprocess as _sp  # lazy

    def _clip_dur(path: str) -> float:
        r = _sp.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=nw=1:nk=1", path], capture_output=True, text=True)
        try:
            return float(r.stdout.strip())
        except ValueError:
            return 0.0

    def _win(local_path, a, b):
        """Clamp [a,b] to the clip; guarantee >=1.5s. Returns (a,b) or None if unusable."""
        d = _clip_dur(local_path)
        if d <= 0:
            return float(a), float(b)
        a = max(0.0, min(float(a), max(0.0, d - 1.5)))
        b = min(float(b), d)
        if b - a < 1.0:
            b = min(d, a + 2.0)
        return (a, b) if b - a >= 0.8 else None

    def _equal_wins(shots):
        """Per-panel (local_path, a, b) all trimmed to the SAME length (min of the
        clamped windows) so stacked panels never freeze when one clip is shorter."""
        ws = []
        for (v, a, b) in shots:
            lp = resolve(str(v))[1]
            w = _win(lp, a, b) or (0.0, 3.0)
            ws.append([lp, w[0], w[1]])
        common = max(1.5, min(w[2] - w[1] for w in ws))
        for w in ws:
            w[2] = w[1] + common      # equal duration for every panel
        return ws

    for i, seg in enumerate(spec.get("segments", [])):
        # IMAGE end-slide: {"image": "<match>", "dur": 3.5} -> Ken-Burns still of a
        # finished-project photo the owner dropped into Drop Content Here.
        if seg.get("image") and base_ctx is not None:
            img = _first_image(dbx, str(seg["image"]))
            if not img:
                print(f"montage seg {i}: image not found {seg['image']!r} — skipping")
                continue
            out = os.path.join(workdir, f"mseg-{name}-{i}.mp4")
            try:
                _still_clip(img, out, float(seg.get("dur", 3.5)))
                seg_clips.append(out)
            except Exception as ex:  # noqa: BLE001
                print(f"montage seg {i} image failed ({ex}); skipping")
            continue
        shots = seg.get("panels") or ([seg["shot"]] if seg.get("shot") else [])
        if not shots:
            continue
        ctx0 = resolve(str(shots[0][0]))
        if not ctx0:
            print(f"montage seg {i}: video not found {shots[0][0]!r} — skipping")
            continue
        if base_ctx is None:
            base_ctx, workdir = ctx0, os.path.dirname(ctx0[1])
        out = os.path.join(workdir, f"mseg-{name}-{i}.mp4")
        n = len(shots)
        try:
            if n == 1:
                v, a, b = shots[0]
                lp = resolve(str(v))[1]
                w = _win(lp, a, b)
                if not w:
                    continue
                _edit_short_4k(lp, w[0], w[1], out)
            elif seg.get("orient") == "cols":
                # side-by-side vertical columns (each tile W/n x 1920), equal length
                w = 1080 // n
                tiles = []
                for k, (lp, a, b) in enumerate(_equal_wins(shots)):
                    pp = os.path.join(workdir, f"mseg-{name}-{i}-c{k}.mp4")
                    _edit_tile(lp, a, b, pp, w, 1920)
                    tiles.append(pp)
                _hstackN(tiles, out)
            else:
                # stacked rows (each tile 1080 x H/n), equal length
                h = 1920 // n
                panels = []
                for k, (lp, a, b) in enumerate(_equal_wins(shots)):
                    pp = os.path.join(workdir, f"mseg-{name}-{i}-p{k}.mp4")
                    _edit_tile(lp, a, b, pp, 1080, h)
                    panels.append(pp)
                _stackN(panels, out)
        except Exception as ex:  # noqa: BLE001 — skip a bad segment, keep the rest
            print(f"montage seg {i} failed ({ex}); skipping")
            continue
        seg_clips.append(out)

    if not seg_clips or base_ctx is None:
        print("cut_montage: no segments rendered.")
        return None
    _f, local, base, brand, display = base_ctx
    out_local = os.path.join(workdir, f"{base}-{name}.mp4")
    _concat_v(seg_clips, out_local, xfade=float(spec.get("xfade", 0.4)))
    brand_key, dispname, tags = brand
    out_path = f"{display.rstrip('/')}/processed/{base}-{name}.mp4"
    dbx.upload(out_local, out_path)
    url = dbx.shared_link(out_path, raw=True)
    queue = [e for e in _load_json(QUEUE_PATH, [])
             if e.get("id") != f"{brand_key}-{name}"]
    entry = {
        "id": f"{brand_key}-{name}", "brand": brand_key,
        "text": _hp_caption(name) if brand_key == "hp" else "",
        "media_url": url, "media_path": out_path,
        "platforms": list(REVIEW_PLATFORMS), "schedule": None,
        "status": "review", "error": None,
    }
    queue.append(entry)
    _save_json(QUEUE_PATH, queue)
    print(f"cut_montage: {brand_key}-{name} ({len(seg_clips)} segments) -> {out_path}")
    return entry


def cut_windows(specs: list[dict]) -> list[dict]:
    """Cut explicit time windows: each spec is {name, start, end} (seconds).

    Reliable (no phrase guessing): exactly [start, end], vertical, no subtitles.
    Redoing a window with the same name auto-deletes the previous version.
    """
    from services.caption import transcribe  # lazy
    from services.ingest import dropbox_client as dbx  # lazy
    from services.write.free_writer import generate_caption  # lazy

    default_match = os.getenv("PIPELINE_VIDEO") or None
    vid_cache: dict = {}     # match -> (f, local, base, brand, display) or None
    cap_cache: dict = {}     # base -> caption

    def resolve(match):
        key = (match or "").lower()
        if key not in vid_cache:
            vid_cache[key] = _first_video(dbx, match or None)
        return vid_cache[key]

    def caption_for(local, base, dispname, tags):
        if base not in cap_cache:
            cap_cache[base] = _compose(generate_caption(
                {"transcript": _transcript_text(transcribe(local)), "brand_name": dispname},
                default_hashtags=tags))
        return cap_cache[base]

    music_path = _find_music(dbx) if any(sp.get("music") for sp in specs) else None
    if any(sp.get("music") for sp in specs) and not music_path:
        print("No music track found — drop an .mp3 in a Dropbox folder named 'Music'.")

    queue = _load_json(QUEUE_PATH, [])
    made: list[dict] = []
    for sp in specs:
        nm = _slug(sp.get("name", "clip")) or "clip"
        try:
            parts_spec = sp.get("parts")
            if parts_spec:
                # CROSS-VIDEO: each part is {video, start, end} from possibly different videos.
                # With "stack": true, the parts are tiled into vertical panels (HP's
                # split-screen look) instead of crossfaded in sequence.
                ctxs, tmp = [], []
                stack = bool(sp.get("stack"))
                ph = 1920 // len(parts_spec) if stack else 0
                for j, part in enumerate(parts_spec):
                    ctx = resolve(part.get("video") or default_match)
                    if not ctx:
                        raise RuntimeError(f"video not found: {part.get('video')!r}")
                    ctxs.append(ctx)
                    plocal = ctx[1]
                    if stack:
                        pp = os.path.join(os.path.dirname(plocal), f"pan-{nm}-{j}.mp4")
                        _edit_panel(plocal, float(part["start"]), float(part["end"]), pp, ph)
                    else:
                        pp = os.path.join(os.path.dirname(plocal), f"xv-{nm}-{j}.mp4")
                        _edit_short(plocal, float(part["start"]), float(part["end"]), pp,
                                    srt=None, mute=bool(sp.get("mute")), logo=_brand_logo(ctx[3][0]))
                    tmp.append(pp)
                _f, local, base, brand, display = ctxs[0]
                out_local = os.path.join(os.path.dirname(local), f"{base}-{nm}.mp4")
                _stackN(tmp, out_local) if stack else _concat(tmp, out_local)
            else:
                ctx = resolve(sp.get("video") or default_match)
                if not ctx:
                    raise RuntimeError("video not found")
                _f, local, base, brand, display = ctx
                lg = _brand_logo(brand[0])
                out_local = os.path.join(os.path.dirname(local), f"{base}-{nm}.mp4")
                wins = sp.get("segments") or [[sp["start"], sp["end"]]]
                if len(wins) == 1:
                    _edit_short(local, float(wins[0][0]), float(wins[0][1]), out_local, srt=None,
                                mute=bool(sp.get("mute")), music=(music_path if sp.get("music") else None),
                                logo=lg)
                else:
                    pl = []
                    for j, w in enumerate(wins):
                        pp = os.path.join(os.path.dirname(local), f"{base}-{nm}-p{j}.mp4")
                        _edit_short(local, float(w[0]), float(w[1]), pp, srt=None,
                                    mute=bool(sp.get("mute")), logo=lg)
                        pl.append(pp)
                    _concat(pl, out_local)
            # Optional: crossfade the brand outro end-card onto the tail (talking
            # clips keep audio). Set "outro": true in the spec.
            if sp.get("outro"):
                outro = os.path.join(ROOT, "content", "brand", "outro.mp4")
                fin = os.path.join(os.path.dirname(out_local), f"{base}-{nm}-fin.mp4")
                _append_outro(out_local, outro, fin)
                out_local = fin
        except Exception as ex:  # noqa: BLE001
            print(f"cut {nm} failed: {ex}")
            continue

        brand_key, dispname, tags = brand
        out_name = os.path.basename(out_local)
        out_path = f"{display.rstrip('/')}/processed/{out_name}"
        dbx.upload(out_local, out_path)
        url = dbx.shared_link(out_path, raw=True)
        caption = _hp_caption(nm) if brand_key == "hp" else caption_for(local, base, dispname, tags)
        keep = []
        for e in queue:
            if e.get("brand") == brand_key and e["id"] == f"{brand_key}-{nm}":
                # Delete the prior file ONLY if it's a different path — a same-name
                # re-render overwrites out_path, so never delete what we just uploaded.
                if e.get("media_path") and e["media_path"] != out_path:
                    try:
                        dbx.delete(e["media_path"])
                    except Exception:  # noqa: BLE001
                        pass
            else:
                keep.append(e)
        queue = keep
        entry = {
            "id": f"{brand_key}-{nm}", "brand": brand_key, "text": caption,
            "media_url": url, "media_path": out_path,
            "platforms": list(REVIEW_PLATFORMS), "schedule": None,
            "status": "review", "error": None,
        }
        queue.append(entry)
        made.append(entry)
        print(f"[{brand_key}] {nm} -> {out_path}")
    _save_json(QUEUE_PATH, queue)
    return made


def run(*, dry_run: bool = False) -> list[dict]:
    """Discover top-level brand folders and process each. Returns review entries."""
    from services.ingest import dropbox_client as dbx  # lazy

    created: list[dict] = []
    for path_lower, display in _top_level_folders(dbx):
        brand = classify_brand(display)
        if not brand:
            print(f"skip unrecognized folder: {display}")
            continue
        created += process_folder(path_lower, display, brand, dbx, dry_run=dry_run)
    return created


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Process Dropbox brand videos into the review queue.")
    parser.add_argument("--dry-run", action="store_true", help="List/route only; no download/transcribe.")
    parser.add_argument("--ls", action="store_true", help="Print the Dropbox app-folder tree and exit.")
    args = parser.parse_args(argv)

    if args.ls:
        debug_tree()
        return 0

    # DROPBOX_WHOAMI: report which Dropbox account the suite is connected to
    # (email + name), so the owner knows where to sign in. Writes it to a
    # committed file and prints it. No secrets exposed.
    if os.getenv("DROPBOX_WHOAMI", "").strip().lower() in ("1", "true", "yes", "go"):
        from services.ingest import dropbox_client as _dbx  # lazy
        acct = _dbx._client().users_get_current_account()
        info = {
            "email": getattr(acct, "email", None),
            "name": getattr(getattr(acct, "name", None), "display_name", None),
            "account_id": getattr(acct, "account_id", None),
            "account_type": str(getattr(getattr(acct, "account_type", None), "_tag", "")),
        }
        ref = os.path.join(ROOT, "content", "reference")
        os.makedirs(ref, exist_ok=True)
        with open(os.path.join(ref, "dropbox_account.json"), "w") as fh:
            json.dump(info, fh, indent=2)
        print(f"DROPBOX ACCOUNT: {info}")
        return 0

    # DROPBOX_INVENTORY: write a complete manifest of every file in the account
    # (path, size, modified) to a committed CSV so the owner has a permanent
    # master list to verify nothing goes missing.
    if os.getenv("DROPBOX_INVENTORY", "").strip().lower() in ("1", "true", "yes", "go"):
        from services.ingest import dropbox_client as _dbx  # lazy
        import csv
        cli = _dbx._client()
        rows, total = [], 0
        r = cli.files_list_folder("", recursive=True)
        while True:
            for e in r.entries:
                if e.__class__.__name__ == "FileMetadata":
                    sz = getattr(e, "size", 0)
                    total += sz
                    rows.append((getattr(e, "path_display", ""), sz,
                                 str(getattr(e, "client_modified", ""))))
            if not getattr(r, "has_more", False):
                break
            r = cli.files_list_folder_continue(r.cursor)
        rows.sort(key=lambda x: -x[1])
        ref = os.path.join(ROOT, "content", "reference")
        os.makedirs(ref, exist_ok=True)
        with open(os.path.join(ref, "dropbox_inventory.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["path", "size_bytes", "modified"])
            w.writerows(rows)
        print(f"DROPBOX INVENTORY: {len(rows)} files, {round(total/1024**3,2)} GB total")
        return 0

    # DROPBOX_USAGE: report total space used + a size breakdown of each folder
    # under "HP-Content Auto." so the owner knows what to clear before the plan
    # drops to the free tier. Writes a committed file and prints it.
    if os.getenv("DROPBOX_USAGE", "").strip().lower() in ("1", "true", "yes", "go"):
        from services.ingest import dropbox_client as _dbx  # lazy
        cli = _dbx._client()
        su = cli.users_get_space_usage()
        used = getattr(su, "used", 0)
        alloc = getattr(su, "allocation", None)
        allocated = None
        for m in ("get_individual", "get_team"):
            try:
                allocated = getattr(getattr(alloc, m)(), "allocated", None)
                if allocated:
                    break
            except Exception:  # noqa: BLE001
                pass

        def _folder_size(path):
            total, nfiles = 0, 0
            try:
                r = cli.files_list_folder(path, recursive=True)
            except Exception:  # noqa: BLE001
                return 0, 0
            while True:
                for e in r.entries:
                    if e.__class__.__name__ == "FileMetadata":
                        total += getattr(e, "size", 0); nfiles += 1
                if not getattr(r, "has_more", False):
                    break
                r = cli.files_list_folder_continue(r.cursor)
            return total, nfiles

        gb = 1024 ** 3
        folders = {}
        for path_lower, display in _top_level_folders(_dbx):
            sub = []
            try:
                rr = cli.files_list_folder(path_lower)
                sub = [e for e in rr.entries if e.__class__.__name__ == "FolderMetadata"]
            except Exception:  # noqa: BLE001
                pass
            for e in sub:
                sz, nf = _folder_size(e.path_lower)
                folders[e.path_display] = {"gb": round(sz / gb, 3), "files": nf}
        report = {
            "used_gb": round(used / gb, 3),
            "allocated_gb": round(allocated / gb, 2) if allocated else None,
            "free_tier_gb": 2,
            "folders": dict(sorted(folders.items(), key=lambda kv: -kv[1]["gb"])),
        }
        ref = os.path.join(ROOT, "content", "reference")
        os.makedirs(ref, exist_ok=True)
        with open(os.path.join(ref, "dropbox_usage.json"), "w") as fh:
            json.dump(report, fh, indent=2)
        print(f"DROPBOX USAGE: {json.dumps(report, indent=2)}")
        return 0

    # PURGE_EDITED: delete every pipeline-generated clip sitting in a staging
    # folder whose name contains "processed" (e.g. "processed", "HP Processed"),
    # across all brands — these are edited videos + orphans from old renders.
    # Leaves ORIGINAL content (HP Content / HP Talking Content) and HP Posts
    # (the ones getting posted) completely untouched. Frees space.
    # Value "list" = dry run (report only); "go"/"true" = actually delete.
    _purge = os.getenv("PURGE_EDITED", "").strip().lower()
    if _purge in ("list", "go", "1", "true", "yes"):
        from services.ingest import dropbox_client as dbx  # lazy
        cli = dbx._client()
        dry = _purge == "list"
        hit, freed, deleted = [], 0, 0
        for path_lower, display in _top_level_folders(dbx):
            try:
                kids = cli.files_list_folder(path_lower)
            except Exception:  # noqa: BLE001
                continue
            subs = []
            while True:
                for e in kids.entries:
                    if e.__class__.__name__ == "FolderMetadata" and "processed" in e.name.lower():
                        subs.append(getattr(e, "path_lower", ""))
                if not getattr(kids, "has_more", False):
                    break
                kids = cli.files_list_folder_continue(kids.cursor)
            for sp in subs:
                try:
                    r = cli.files_list_folder(sp, recursive=True)
                except Exception:  # noqa: BLE001
                    continue
                while True:
                    for e in r.entries:
                        if e.__class__.__name__ == "FileMetadata":
                            fp = getattr(e, "path_display", "") or getattr(e, "path_lower", "")
                            hit.append(fp); freed += getattr(e, "size", 0)
                            if not dry:
                                try:
                                    dbx.delete(fp); deleted += 1
                                except Exception as ex:  # noqa: BLE001
                                    print(f"del fail {fp}: {ex}")
                    if not getattr(r, "has_more", False):
                        break
                    r = cli.files_list_folder_continue(r.cursor)
        tag = "DRY RUN — would delete" if dry else "DELETED"
        print(f"PURGE_EDITED {tag}: {len(hit)} file(s), {round(freed/1024**3,3)} GB")
        for fp in hit[:300]:
            print("  ", fp)
        if not dry:
            queue = _load_json(QUEUE_PATH, [])
            kept = [q for q in queue
                    if "processed" not in (q.get("media_path") or "").rsplit("/", 1)[0].lower()]
            if len(kept) != len(queue):
                _save_json(QUEUE_PATH, kept)
            print(f"queue: kept {len(kept)} entries (HP Posts + originals)")
        return 0

    # DELETE_IDS: remove specific clips (Dropbox file + queue entry) up front,
    # then FALL THROUGH so the same run can also render replacements.
    _del = os.getenv("DELETE_IDS", "").strip()
    if _del:
        delete_ids([x.strip() for x in _del.split(",") if x.strip()])

    # DROPBOX_LS: print the Dropbox tree + the videos discovered under each
    # brand's Drop Content Here (recursively), then exit.
    if os.getenv("DROPBOX_LS", "").strip().lower() in ("1", "true", "yes"):
        debug_tree()
        from services.ingest import dropbox_client as _dbx  # lazy
        for path_lower, display in _top_level_folders(_dbx):
            if not classify_brand(display):
                continue
            vids = _brand_videos(_dbx, path_lower)
            print(f"\n== {display}: {len(vids)} video(s) discoverable ==")
            for v in vids:
                print(f"   {getattr(v, 'path', v.name)}  ({getattr(v,'size_bytes',0)//1_000_000} MB)")
            # also list IMAGES under Drop Content Here (for finished-project end-slides)
            _cli = _dbx._client()
            drop = f"{path_lower.rstrip('/')}/{DROP_FOLDER.lower()}"
            imgs = []
            try:
                r = _cli.files_list_folder(drop, recursive=True)
                while True:
                    for e in r.entries:
                        if e.__class__.__name__ == "FileMetadata" and e.name.lower().endswith(IMAGE_EXTS):
                            imgs.append(getattr(e, "path_display", "") or e.name)
                    if not getattr(r, "has_more", False):
                        break
                    r = _cli.files_list_folder_continue(r.cursor)
            except Exception:  # noqa: BLE001
                pass
            print(f"== {display}: {len(imgs)} image(s) ==")
            for ip in imgs:
                print(f"   IMG {ip}")
        return 0

    # DROPBOX_ORGANIZE: build the Ready-To-Post + Drop-Content-Here layout.
    # Any value lists the tree (dry run); "go" actually creates/moves.
    # "posts" instead sorts HP Posts into per-project subfolders (inside it).
    org = os.getenv("DROPBOX_ORGANIZE", "").strip().lower()
    if org == "posts":
        organize_posts()
        return 0
    if org:
        organize_dropbox(execute=(org == "go"))
        return 0

    # IG_REFERENCE: pull a brand's posted IG media (thumbs+captions) to study its
    # house style. Value = brand key, optional ":N" limit (e.g. "hp" or "hp:30").
    igref = os.getenv("IG_REFERENCE", "").strip()
    if igref:
        bk = igref.split(":")[0] or "hp"
        tail = igref.split(":")[1] if ":" in igref else ""
        fetch_ig_reference(bk, int(tail) if tail.isdigit() else 24)
        return 0

    # MONTAGE_SPEC json: one montage (object) OR a BATCH (list of objects). A batch
    # builds many montages in ONE run with a single sequential queue write — high
    # throughput and no concurrent-run clobber.
    montage = os.getenv("MONTAGE_SPEC", "").strip()
    # MONTAGE_SPEC_FILE: read the spec JSON from a committed repo file instead of
    # the dispatch input — avoids hand-transcription errors for large batches.
    _mfile = os.getenv("MONTAGE_SPEC_FILE", "").strip()
    if not montage and _mfile:
        _mp = _mfile if os.path.isabs(_mfile) else os.path.join(ROOT, _mfile)
        with open(_mp, encoding="utf-8") as _fh:
            montage = _fh.read().strip()
    if montage:
        import json as _json
        data = _json.loads(montage)
        specs = data if isinstance(data, list) else [data]
        made = []
        for sp in specs:
            try:
                m = cut_montage(sp)
                if m:
                    made.append(m)
            except Exception as ex:  # noqa: BLE001 — one bad montage shouldn't kill the batch
                print(f"montage {sp.get('name','?')!r} failed: {ex}")
        print(f"\nDone: {len(made)}/{len(specs)} montage(s). Nothing posted (review only).")
        return 0

    # INGEST_CLIP "name:relpath": save a ready-made local clip into Dropbox +
    # a review queue entry (e.g. an externally-combined keeper).
    ingest = os.getenv("INGEST_CLIP", "").strip()
    if ingest and ":" in ingest:
        nm, rel = ingest.split(":", 1)
        ingest_clip(nm.strip(), os.path.join(ROOT, rel.strip()))
        return 0

    # FETCH_PREVIEWS: pull finished clips from Dropbox into content/preview/.
    fp = os.getenv("FETCH_PREVIEWS", "").strip()
    if fp:
        fetch_previews(fp)
        return 0

    # SAVE_STYLED: upload locally-finished clips (logo+outro) from a committed
    # repo dir straight into HP Posts and repoint the queue. Status stays review.
    styled = os.getenv("SAVE_STYLED", "").strip()
    if styled:
        save_styled(styled)
        return 0

    # COPY_STYLED: "dir:Folder" — upload the committed finished clips to a SECOND
    # Dropbox folder (e.g. HP Tiktok) as a copy, without touching the queue.
    copy_st = os.getenv("COPY_STYLED", "").strip()
    if copy_st and ":" in copy_st:
        d, folder = copy_st.split(":", 1)
        copy_styled(d.strip(), folder.strip())
        return 0

    # MOVE_SAVED: "src:dest" — move all saved clips from <Brand>/src into
    # <Brand>/dest preserving the exact subfolder structure (e.g. HP Posts:HP Auto Post).
    mv = os.getenv("MOVE_SAVED", "").strip()
    if mv and ":" in mv:
        s, d = mv.split(":", 1)
        move_saved_folder(s.strip(), d.strip())
        return 0

    # SWAP_OUTRO: comma ids OR "all" — replace the old 8851 outro tail with the
    # current brand outro on every saved clip, then verify the swap stuck.
    swap = os.getenv("SWAP_OUTRO", "").strip()
    if swap:
        swap_outro(swap)
        return 0

    # PROMOTE_IDS: move ONLY these clips from processed/ into Ready To Post
    # (approved keepers). Status stays 'review' — nothing is posted.
    promote = os.getenv("PROMOTE_IDS", "").strip()
    if promote:
        promote_ids([x.strip() for x in promote.split(",") if x.strip()])
        return 0

    # DEMOTE_IDS: move clips back out of Ready To Post into processed/ (un-save).
    demote = os.getenv("DEMOTE_IDS", "").strip()
    if demote:
        demote_ids(demote)
        return 0

    # CLEAN_READY: delete stale/old files left in Ready To Post (edited clips'
    # previous versions) so only the current saved set remains.
    if os.getenv("CLEAN_READY", "").strip().lower() in ("1", "true", "yes", "go"):
        clean_ready_orphans()
        return 0

    # KEEP_IDS: delete every clip (Dropbox file + queue entry) not in this
    # comma-separated id list — clears stale batches from the review folder.
    keep_ids = os.getenv("KEEP_IDS", "").strip()
    if keep_ids:
        prune_clips(keep_ids.split(","))
        return 0

    # Dump a timestamped transcript so clip windows can be chosen by time.
    if os.getenv("DUMP_TRANSCRIPT", "").strip().lower() in ("1", "true", "yes"):
        dump_transcript()
        return 0

    # Dump per-video contact sheets so the footage can be 'seen' to pick shots.
    if os.getenv("DUMP_THUMBS", "").strip().lower() in ("1", "true", "yes"):
        dump_thumbs()
        return 0

    # AUTO_HIGHLIGHTS: free SupoClip-style brain — auto-pick best moments from a
    # narrated video (value = how many clips, e.g. "4"). Silent b-roll yields none.
    auto = os.getenv("AUTO_HIGHLIGHTS", "").strip()
    if auto:
        try:
            n = int(auto)
        except ValueError:
            n = 4
        made = auto_highlights(n=n)
        print(f"\nDone: {len(made)} auto highlight clip(s). Nothing posted (all status=review).")
        return 0

    # RECUT_SPECS json: explicit time windows [{"name","start","end"}] (preferred),
    # or legacy phrase recuts [{"clip","end_phrase",...}].
    specs = os.getenv("RECUT_SPECS", "").strip()
    if specs:
        import json as _json

        data = _json.loads(specs)
        if data and ("parts" in data[0] or "segments" in data[0] or ("start" in data[0] and "end" in data[0])):
            made = cut_windows(data)
            print(f"\nDone: {len(made)} clip(s). Nothing posted (all status=review).")
        else:
            total = 0
            for sp in data:
                sl = sp.get("start_lead")
                total += len(recut(
                    sp.get("end_phrase", ""), int(sp.get("clip", 2)),
                    float(sp.get("end_buffer", 1.0)),
                    float(sl) if sl is not None else None,
                ))
            print(f"\nDone: {total} recut(s).")
        return 0

    created = run(dry_run=args.dry_run)
    print(f"\nDone: {len(created)} review item(s) created. Nothing was posted (all status=review).")
    if not created and not args.dry_run:
        print("\nNo videos processed — here's what the app sees, to diagnose:")
        try:
            debug_tree()
        except Exception as e:  # noqa: BLE001
            print(f"(debug listing failed: {e})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
