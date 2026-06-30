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


def process_folder(folder_path: str, folder_display: str, brand, dbx, *, dry_run: bool = False) -> list[dict]:
    """Process the videos directly inside one matched brand folder."""
    brand_key, display, default_tags = brand
    processed = set(_load_json(PROCESSED_PATH, []))
    created: list[dict] = []

    for f in dbx.list_folder(folder_path):
        if not f.name.lower().endswith(VIDEO_EXTS) or f.rev in processed:
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
    cmd = ["ffmpeg", "-y"]
    for p in parts:
        cmd += ["-i", p]
    fc = [f"[{i}:v]fps=30,scale=1080:1920,setsar=1,format=yuv420p[n{i}]" for i in range(n)]
    vlab, off = "[n0]", durs[0] - xfade
    for i in range(1, n):
        nv = f"[v{i}]"
        fc.append(f"{vlab}[n{i}]xfade=transition=fade:duration={xfade}:offset={off:.3f}{nv}")
        vlab, off = nv, off + durs[i] - xfade
    cmd += ["-filter_complex", ";".join(fc), "-map", vlab, "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
            "-movflags", "+faststart", out_path]
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
        vids = [f for f in dbx.list_folder(path_lower) if f.name.lower().endswith(VIDEO_EXTS)]
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
    # CONTENT_FOLDER scopes reads to a subfolder under each brand, e.g.
    # "HP Talking Content" (SupoClip talking clips) or "HP Content" (work footage).
    _sub = (os.getenv("CONTENT_FOLDER") or "").strip()
    for path_lower, display in _top_level_folders(dbx):
        brand = classify_brand(display)
        if not brand:
            continue
        src = f"{path_lower.rstrip('/')}/{_sub.lower()}" if _sub else path_lower
        try:
            vids = [f for f in dbx.list_folder(src) if f.name.lower().endswith(VIDEO_EXTS)]
        except Exception:  # noqa: BLE001 — subfolder missing for this brand
            vids = []
        if match:
            vids = [f for f in vids if match.lower() in f.name.lower()]
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


def _list_videos(dbx, limit: int = 1, match: str | None = None) -> list:
    """Up to ``limit`` videos from the first matching brand's (CONTENT_FOLDER-
    scoped) folder, each downloaded -> (file, local, base, brand, display).
    Stays within ONE brand folder (per-brand isolation)."""
    import shutil
    _sub = (os.getenv("CONTENT_FOLDER") or "").strip()
    out: list = []
    for path_lower, display in _top_level_folders(dbx):
        brand = classify_brand(display)
        if not brand:
            continue
        src = f"{path_lower.rstrip('/')}/{_sub.lower()}" if _sub else path_lower
        try:
            vids = [f for f in dbx.list_folder(src)
                    if f.name.lower().endswith(VIDEO_EXTS)]
        except Exception:  # noqa: BLE001 — subfolder missing for this brand
            vids = []
        if match:
            # Match against the SLUG (same form as clip ids), so a user-friendly
            # "sep-17-2025" matches a raw filename like "Video Sep 17 2025 ...".
            m = _slug(match)
            vids = [f for f in vids if m in _slug(f.name) or match.lower() in f.name.lower()]
        if not vids:
            continue
        for f in vids[:limit]:
            raw = dbx.download(f)
            base = _slug(f.name) or "clip"
            ext = os.path.splitext(f.name)[1] or ".mp4"
            local = os.path.join(os.path.dirname(raw), f"{base}{ext}")
            if os.path.abspath(local) != os.path.abspath(raw):
                shutil.copy(raw, local)
            out.append((f, local, base, brand, display))
        break          # only the first brand folder that has videos
    return out


def dump_transcript() -> None:
    """Transcribe EVERY video in the brand folders and print/commit a timestamped
    transcript per video, so good clip windows can be chosen by time."""
    import shutil
    from services.caption import transcribe  # lazy
    from services.ingest import dropbox_client as dbx  # lazy

    out_dir = os.path.join(ROOT, "content", "transcripts")
    os.makedirs(out_dir, exist_ok=True)
    count = 0
    for path_lower, display in _top_level_folders(dbx):
        if not classify_brand(display):
            continue
        for f in dbx.list_folder(path_lower):
            if not f.name.lower().endswith(VIDEO_EXTS):
                continue
            raw = dbx.download(f)
            base = _slug(f.name) or "clip"
            ext = os.path.splitext(f.name)[1] or ".mp4"
            local = os.path.join(os.path.dirname(raw), f"{base}{ext}")
            if os.path.abspath(local) != os.path.abspath(raw):
                shutil.copy(raw, local)
            segs = transcribe(local)
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
    for path_lower, display in _top_level_folders(dbx):
        if not classify_brand(display):
            continue
        for f in dbx.list_folder(path_lower):
            if not f.name.lower().endswith(VIDEO_EXTS):
                continue
            raw = dbx.download(f)
            base = _slug(f.name) or "clip"
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nw=1:nk=1", raw],
                capture_output=True, text=True)
            try:
                dur = max(1.0, float(r.stdout.strip()))
            except ValueError:
                dur = 10.0
            fps = max(0.05, 6.0 / dur)
            sheet = os.path.join(out_dir, f"{base}.jpg")
            subprocess.run(
                ["ffmpeg", "-y", "-i", raw, "-vf",
                 f"fps={fps:.4f},scale=320:-1,tile=3x2:padding=6:margin=6",
                 "-frames:v", "1", "-q:v", "4", sheet],
                check=False, capture_output=True)
            print(f"contact sheet {base}.jpg (dur={dur:.1f}s)")


def detect_shots_bulk(match: str | None = None, force: bool = False) -> int:
    """Scene-split every brand video into a shot list — Phase 1 of the bulk
    pipeline. Writes ``content/shots/<brand>-<base>.json`` (start/end per shot)
    for the scoring stage to consume. NEVER touches the queue or posts anything.

    Dedupe is the shot file itself: a video is re-detected only when its Dropbox
    ``rev`` changed (or ``force``). ``match`` limits to filenames containing it.
    Uses the free ffmpeg scene filter (PySceneDetect if installed) — no API keys.
    """
    from services.ingest import dropbox_client as dbx  # lazy
    from services.score.shots import detect_shots  # lazy (ffmpeg)

    out_dir = os.path.join(ROOT, "content", "shots")
    os.makedirs(out_dir, exist_ok=True)
    made = 0
    for path_lower, display in _top_level_folders(dbx):
        brand = classify_brand(display)
        if not brand:
            continue
        brand_key = brand[0]
        for f in dbx.list_folder(path_lower):
            if not f.name.lower().endswith(VIDEO_EXTS):
                continue
            if match and match.lower() not in f.name.lower():
                continue
            base = _slug(f.name) or "clip"
            shot_path = os.path.join(out_dir, f"{brand_key}-{base}.json")
            if not force and os.path.exists(shot_path):
                prev = _load_json(shot_path, {})
                if prev.get("rev") and prev.get("rev") == getattr(f, "rev", ""):
                    print(f"[{brand_key}] shots up-to-date: {base} (skip)")
                    continue
            try:
                raw = dbx.download(f)
                shots = detect_shots(raw)
            except Exception as ex:  # noqa: BLE001 — one bad video never kills the run
                print(f"[{brand_key}] shot-detect FAILED {f.name}: {ex}")
                continue
            dur = shots[-1]["end"] if shots else 0.0
            _save_json(shot_path, {
                "video": f.name,
                "base": base,
                "brand": brand_key,
                "rev": getattr(f, "rev", ""),
                "duration": round(dur, 2),
                "n_shots": len(shots),
                "detector": getattr(detect_shots, "last_detector", "ffmpeg"),
                "shots": shots,
            })
            made += 1
            print(f"[{brand_key}] {base}: {len(shots)} shots ({dur:.1f}s) -> "
                  f"content/shots/{brand_key}-{base}.json")
    print(f"\ndetect_shots_bulk: wrote/updated {made} shot list(s). "
          f"Nothing posted (analysis only).")
    return made


def score_shots_bulk(match: str | None = None, force: bool = False) -> int:
    """Phase 2: score every shot's postability and rank them best-first.

    For each brand video it (re)detects shots if needed, scores each shot with
    the free visual brain (sharpness/motion/exposure/colour, + optional CLIP),
    and writes ``content/scores/<brand>-<base>.json`` — the ranked feed Phase 4
    surfaces. Dedupes on Dropbox ``rev``. NEVER touches the queue or posts."""
    from services.ingest import dropbox_client as dbx  # lazy
    from services.score.shots import detect_shots  # lazy
    from services.score.visual import score_shot  # lazy (PIL+ffmpeg)

    shots_dir = os.path.join(ROOT, "content", "shots")
    scores_dir = os.path.join(ROOT, "content", "scores")
    os.makedirs(scores_dir, exist_ok=True)
    scorer = os.getenv("SCORER", "heuristic")
    made = 0
    for path_lower, display in _top_level_folders(dbx):
        brand = classify_brand(display)
        if not brand:
            continue
        brand_key = brand[0]
        for f in dbx.list_folder(path_lower):
            if not f.name.lower().endswith(VIDEO_EXTS):
                continue
            if match and match.lower() not in f.name.lower():
                continue
            base = _slug(f.name) or "clip"
            score_path = os.path.join(scores_dir, f"{brand_key}-{base}.json")
            if not force and os.path.exists(score_path):
                prev = _load_json(score_path, {})
                if prev.get("rev") and prev.get("rev") == getattr(f, "rev", ""):
                    print(f"[{brand_key}] scores up-to-date: {base} (skip)")
                    continue
            try:
                raw = dbx.download(f)
                shot_file = os.path.join(shots_dir, f"{brand_key}-{base}.json")
                shots = _load_json(shot_file, {}).get("shots") or detect_shots(raw)
                scored = []
                for sh in shots:
                    m = score_shot(raw, float(sh["start"]), float(sh["end"]))
                    scored.append({**sh, **m})
            except Exception as ex:  # noqa: BLE001 — one bad video never kills the run
                print(f"[{brand_key}] score FAILED {f.name}: {ex}")
                continue
            ranked = sorted(range(len(scored)),
                            key=lambda i: scored[i].get("fire_score", 0), reverse=True)
            best = scored[ranked[0]]["fire_score"] if scored else 0
            _save_json(score_path, {
                "video": f.name, "base": base, "brand": brand_key,
                "rev": getattr(f, "rev", ""), "scorer": scorer,
                "n_shots": len(scored), "best_score": best,
                "ranked": ranked, "shots": scored,
            })
            made += 1
            print(f"[{brand_key}] {base}: scored {len(scored)} shots, "
                  f"best={best:.1f} -> content/scores/{brand_key}-{base}.json")
    print(f"\nscore_shots_bulk: wrote/updated {made} score file(s). "
          f"Nothing posted (analysis only).")
    return made


def build_review_feed() -> str:
    """Phase 4: write content/review/index.html — a best-first page of the
    clips in review, scored where known. Reads the queue + content/scores/*.json;
    plays local content/preview/*.mp4 when present, else the Dropbox media_url.
    Never posts; purely a fast keep/kill surface for the owner."""
    import glob  # lazy, stdlib
    from services.review.feed import render_review_html  # lazy

    # base/brand -> best_score, so a clip can inherit a score even if its entry
    # didn't carry one (e.g. a montage named after the source video's base).
    best_by_base: dict[str, float] = {}
    for sp in glob.glob(os.path.join(ROOT, "content", "scores", "*.json")):
        d = _load_json(sp, {})
        if d.get("base"):
            best_by_base[f"{d.get('brand')}-{d['base']}"] = d.get("best_score")

    preview_dir = os.path.join(ROOT, "content", "preview")
    items = []
    for e in _load_json(QUEUE_PATH, []):
        if e.get("status") != "review":
            continue
        cid = e.get("id", "")
        score = e.get("fire_score")
        if score is None:
            for key, val in best_by_base.items():
                if cid.startswith(key):
                    score = val
                    break
        local = os.path.join(preview_dir, f"{cid}.mp4")
        src = f"../preview/{cid}.mp4" if os.path.exists(local) else (e.get("media_url") or "")
        items.append({"id": cid, "brand": e.get("brand", ""), "fire_score": score,
                      "text": e.get("text", ""), "src": src})

    out_dir = os.path.join(ROOT, "content", "review")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(render_review_html(items))
    print(f"build_review_feed: {len(items)} clip(s) -> content/review/index.html")
    return out_path


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
            print(f"fetched {e['id']}")
            n += 1
        except Exception as ex:  # noqa: BLE001
            print(f"fetch failed {e['id']}: {ex}")
    print(f"\n{n} preview(s) in content/preview/")
    return n


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


def copy_clips(ids: list[str], dest_sub: str = "HP Posts") -> int:
    """Copy the listed clips' Dropbox files into the brand's ``dest_sub`` folder
    (e.g. 'HP Posts'). Does NOT post — just places the owner-approved clips where
    they want them. Leaves the originals + queue entries untouched."""
    from services.ingest import dropbox_client as dbx  # lazy

    sel = {i.strip() for i in ids if i.strip()}
    queue = _load_json(QUEUE_PATH, [])
    n = 0
    for e in queue:
        if e.get("id") not in sel:
            continue
        mp = e.get("media_path")
        if not mp:
            continue
        brand_root = os.path.dirname(os.path.dirname(mp))   # ".../<brand>"
        dest = f"{brand_root}/{dest_sub}/{os.path.basename(mp)}"
        try:
            dbx.copy(mp, dest)
            print(f"copied {e.get('id')} -> {dest}")
            n += 1
        except Exception as ex:  # noqa: BLE001 — one bad copy shouldn't stop the rest
            print(f"copy failed {e.get('id')}: {ex}")
    print(f"\nCopied {n} clip(s) to '{dest_sub}'. Nothing posted.")
    return n


def delete_clips(delete_ids: list[str]) -> list[dict]:
    """Delete the listed clips (Dropbox file + queue entry); keep everything else.
    The inverse of :func:`prune_clips` — safer when removing a few bad clips out
    of many (list the few to drop, not the many to keep). Never posts."""
    from services.ingest import dropbox_client as dbx  # lazy

    drop = {k.strip() for k in delete_ids if k.strip()}
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
            except Exception as ex:  # noqa: BLE001 — missing file is fine, still drop the entry
                print(f"delete failed {mp}: {ex}")
        print(f"deleted {e.get('id')}")
        removed += 1
    _save_json(QUEUE_PATH, kept)
    print(f"\nDeleted {removed} clip(s); kept {len(kept)}.")
    return kept


# ---- SupoClip-style auto highlight selection (free, local Whisper, no LLM) ----
# Words that signal a strong hook/payoff in landscaping/reno talking-head clips.
HOOK_WORDS = (
    "finished", "finally", "reveal", "check it out", "check this out", "before",
    "after", "transformation", "transformed", "renovated", "renovation", "favorite",
    "beautiful", "expensive", "crazy", "insane", "look at", "turned out", "dream",
    "results", "result", "best", "perfect", "love",
)
# Phrases that open a strong, self-contained "saying" — a clip that starts on one
# of these tends to be quotable and grabs attention in the first second.
OPENER_PHRASES = (
    "here's", "the biggest", "most people", "the secret", "the truth", "if you",
    "the number one", "the best", "the worst", "the key", "the problem", "the reason",
    "this is why", "that's why", "the thing about", "a lot of people", "the mistake",
    "let me tell you", "i'll tell you", "what i", "remember", "listen", "honestly",
    "my advice", "pro tip", "fun fact", "the trick",
)
# Punchy, opinionated, concrete words that make a line land.
PUNCH_WORDS = (
    "never", "always", "huge", "guarantee", "guaranteed", "promise", "proven",
    "secret", "mistake", "biggest", "number one", "literally", "game changer",
    "worth it", "trust me", "the most", "every time", "matters", "important",
    "key", "difference", "quality", "value", "honest", "real",
)
FILLER_WORDS = ("um ", "uh ", " like ", "you know", "i mean", "kind of", "sort of",
                " uh,", " um,", "basically", " so yeah", "i guess")
# A trailing word that means the thought isn't finished — bad place to end a clip.
DANGLING_TAILS = ("and", "but", "so", "because", "or", "the", "a", "to", "that",
                  "with", "for", "of", "if", "when", "we", "i", "it's", "like")


def _score_segment_text(text: str, dur: float) -> float:
    """Heuristic 'is this a good, quotable saying' score (no LLM, $0).

    Rewards: lively delivery, a strong opener, punch/hook words, and a COMPLETE
    thought (ends on sentence punctuation). Penalizes: filler, word repetition,
    dead air (very low words/sec), a dangling unfinished tail, and lengths far
    from the short-clip sweet spot (~14s). A genuinely weak stretch scores <= 0
    so it never becomes a clip — that's the 'accurate' part.
    """
    raw = (text or "").strip()
    t = raw.lower()
    words = re.findall(r"[a-z']+", t)
    if len(words) < 4 or dur <= 0:
        return 0.0

    wps = len(words) / dur
    density = min(wps / 2.8, 1.0)                  # lively delivery
    if wps < 1.1:                                  # long silences / dead air
        density -= 0.5

    opener = 1.0 if any(t.startswith(p) or f" {p}" in t[:40] for p in OPENER_PHRASES) else 0.0
    hooks = min(sum(1 for h in HOOK_WORDS if h in t), 3)
    punch = min(sum(1 for p in PUNCH_WORDS if p in t), 3)

    ends_clean = 1.0 if raw.endswith((".", "!", "?")) else 0.0
    last = words[-1]
    dangling = 1.0 if (last in DANGLING_TAILS and not ends_clean) else 0.0

    filler = sum(t.count(f) for f in FILLER_WORDS)
    filler_density = filler / max(1, len(words) / 8)   # per ~8 words
    uniq = len(set(words)) / len(words)                # 1.0 = no repetition
    repetition = max(0.0, 0.7 - uniq)                  # penalize heavy repeats

    score = (density
             + 0.9 * opener
             + 0.4 * hooks
             + 0.35 * punch
             + 0.5 * ends_clean
             - 0.7 * dangling
             - 0.25 * filler_density
             - 1.2 * repetition)
    # Ideal length 12-30s (no penalty), gentle penalty outside (owner spec #6).
    score -= max(0.0, abs(dur - 21.0) - 9.0) / 30.0
    return score


# Windows shorter than this must be a complete sentence to qualify (so short
# clips are punchy one-liners, never cut-off fragments).
SHORT_CLIP_MAX = 6.0
_SENT_END = re.compile(r"[.!?][\"')\]]*\s*$")


def _pick_highlights(segments, n: int = 4, min_len: float = 7.0,
                     max_len: float = 20.0, min_score: float = 0.0
                     ) -> list[tuple[float, float, str]]:
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
                # Short clips are welcome, but only as a COMPLETE thought — a
                # window under SHORT_CLIP_MAX must end on . ! or ? so we never
                # ship a cut-off fragment. Longer windows are trimmed/extended
                # later, so they aren't gated here.
                if (b - a) < SHORT_CLIP_MAX and not _SENT_END.search(text.strip()):
                    j += 1
                    continue
                candidates.append((_score_segment_text(text, b - a), a, b))
            j += 1
    candidates.sort(key=lambda c: c[0], reverse=True)
    picked: list[tuple[float, float]] = []
    for score, a, b in candidates:
        if score <= min_score:           # only GREAT clips clear the bar
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


def _slice_segments(segments, a: float, b: float):
    """Return transcript segments inside ``[a,b]``, re-timed to start at 0 — so an
    animated-caption file lines up with a clip cut from that window."""
    from services.caption.transcribe import Segment, Word  # lazy

    out = []
    for s in segments:
        ss = getattr(s, "start_seconds", None)
        se = getattr(s, "end_seconds", None)
        if ss is None or se is None or se <= a or ss >= b:
            continue
        ns, ne = max(ss, a) - a, min(se, b) - a
        if ne <= ns:
            continue
        words = []
        for w in (getattr(s, "words", None) or []):
            ws = getattr(w, "start_seconds", None)
            we = getattr(w, "end_seconds", None)
            if ws is None or we is None or we <= a or ws >= b:
                continue
            words.append(Word(text=getattr(w, "text", ""),
                              start_seconds=max(ws, a) - a, end_seconds=min(we, b) - a))
        out.append(Segment(text=(getattr(s, "text", "") or "").strip(),
                           start_seconds=ns, end_seconds=ne, words=words))
    return out


def _burn_ass(src: str, ass_path: str, out_path: str) -> str:
    """Burn an ASS (word-by-word animated) subtitle file onto a clip, keep audio."""
    import subprocess  # lazy
    safe = ass_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    subprocess.run(
        ["ffmpeg", "-y", "-i", src, "-vf", f"ass={safe}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-c:a", "copy", "-movflags", "+faststart", out_path],
        check=True, capture_output=True)
    return out_path


# ---- clean cuts, internal-weak removal, caption re-timing (talking clips) ----
# Words that should never START or END a clip (stutters / filler / dangling).
_EDGE_FILLER = {"um", "uh", "er", "umm", "uhh", "hmm", "so", "like", "well",
                "yeah", "okay", "ok", "and", "but", "or", "you", "know", "i",
                "mean", "just", "basically", "actually"}


def _norm_word(w) -> str:
    return re.sub(r"[^a-z']", "", (getattr(w, "text", "") or "").lower())


def _words_in(segments, a: float, b: float):
    """Flat list of timed words inside [a,b], in order."""
    out = []
    for s in segments:
        for w in (getattr(s, "words", None) or []):
            ws = getattr(w, "start_seconds", None)
            we = getattr(w, "end_seconds", None)
            if ws is None or we is None or we <= a or ws >= b:
                continue
            out.append(w)
    return out


def _trim_to_clean(segments, a: float, b: float, pad: float = 0.08) -> tuple[float, float]:
    """Nudge [a,b] so the clip STARTS and ENDS on a clear, content word — never
    a stutter, filler word, or mid-pause (owner spec #4)."""
    words = _words_in(segments, a, b)
    if not words:
        return a, b
    i, j = 0, len(words) - 1
    while i < j and _norm_word(words[i]) in _EDGE_FILLER:
        i += 1
    # drop an immediate stutter repeat at the new start ("we we", "the the")
    if i + 1 < j and _norm_word(words[i]) and _norm_word(words[i]) == _norm_word(words[i + 1]):
        i += 1
    while j > i and _norm_word(words[j]) in _EDGE_FILLER:
        j -= 1
    na = max(a, float(getattr(words[i], "start_seconds", a)) - pad)
    nb = min(b, float(getattr(words[j], "end_seconds", b)) + pad)
    return (na, nb) if nb > na else (a, b)


# Whisper "base" mis-hears HP's spoken brand lines. Fix them in the captions
# (owner choice: fast brand-word correction, not a slower model). Each rule is
# (mis-heard word sequence -> correct words); matching is case/punctuation
# -insensitive and timing is redistributed across the replacement words so the
# karaoke stays in sync. Keep rules specific so normal speech is never touched.
# Source tokens are MATCHED after _norm_alnum (lowercase, punctuation+hyphens
# stripped) — so Whisper's hyphenated single tokens like "higher-privileged"
# normalize to "higherprivileged" and must be listed in that joined form, NOT as
# two words. Both the 2-token (hyphenated) and 3-word spellings are covered.
_BRAND_FIXES = [
    (["higherprivileged", "nation"], ["Higher", "Purpose", "Nation"]),
    (["higherpurpose", "nation"], ["Higher", "Purpose", "Nation"]),
    (["higher", "privileged", "nation"], ["Higher", "Purpose", "Nation"]),
    (["higher", "purpose", "nation"], ["Higher", "Purpose", "Nation"]),
    (["hide", "purpose", "nation"], ["Higher", "Purpose", "Nation"]),
    (["hyde", "purpose", "nation"], ["Higher", "Purpose", "Nation"]),
    (["high", "purpose", "nation"], ["Higher", "Purpose", "Nation"]),
    (["hydepurpose", "nation"], ["Higher", "Purpose", "Nation"]),
    (["hyperbist", "nation"], ["Higher", "Purpose", "Nation"]),
    (["hyperbness", "nation"], ["Higher", "Purpose", "Nation"]),
    (["hyperb", "nation"], ["Higher", "Purpose", "Nation"]),
    (["hb", "nation"], ["HP", "Nation"]),
    (["hp", "nation"], ["HP", "Nation"]),
    (["hpe", "nation"], ["HP", "Nation"]),
    (["hbnation"], ["HP", "Nation"]),
]


def _norm_alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _fix_brand_words(segments):
    """Correct known brand mis-hears in the transcript before captions are burned.

    Operates on the word list so the burned karaoke text is right; timing for a
    replacement is spread evenly across the new words and trailing punctuation is
    preserved. Unmatched words pass through untouched."""
    from services.caption.transcribe import Segment, Word  # lazy

    out = []
    for s in segments:
        words = list(getattr(s, "words", None) or [])
        if not words:
            out.append(s)
            continue
        fixed: list = []
        i = 0
        while i < len(words):
            hit = None
            for src, dst in _BRAND_FIXES:
                k = len(src)
                if i + k <= len(words) and all(
                        _norm_alnum(getattr(words[i + t], "text", "")) == src[t]
                        for t in range(k)):
                    hit = (k, dst)
                    break
            if hit:
                k, dst = hit
                a = float(getattr(words[i], "start_seconds", 0.0))
                b = float(getattr(words[i + k - 1], "end_seconds", a))
                last_txt = (getattr(words[i + k - 1], "text", "") or "").strip()
                mt = re.search(r"[^A-Za-z0-9]+$", last_txt)
                trail = mt.group(0) if mt else ""
                m = len(dst)
                span = (b - a) / m if m else 0.0
                for t, wt in enumerate(dst):
                    ws = a + t * span
                    we = b if t == m - 1 else a + (t + 1) * span
                    fixed.append(Word(text=wt + (trail if t == m - 1 else ""),
                                      start_seconds=ws, end_seconds=we))
                i += k
            else:
                fixed.append(words[i])
                i += 1
        new_text = " ".join((getattr(w, "text", "") or "") for w in fixed).strip()
        out.append(Segment(text=new_text or s.text, start_seconds=s.start_seconds,
                           end_seconds=s.end_seconds, words=fixed))
    return out


def _all_words(segments):
    """Every timed word across the segments, in time order."""
    ws = []
    for s in segments:
        for w in (getattr(s, "words", None) or []):
            if getattr(w, "start_seconds", None) is not None and \
               getattr(w, "end_seconds", None) is not None:
                ws.append(w)
    ws.sort(key=lambda w: w.start_seconds)
    return ws


def _snap_bounds(segments, a: float, b: float, lead: float = 0.18,
                 trail: float = 0.32):
    """Move the cut points into the SILENCE around the speech so a clip never
    starts or ends mid-word (owner: "stop cutting over my words").

    ``a`` is pulled back into the gap just before the first word inside [a,b]
    (without crossing into the previous word); ``b`` is pushed into the gap just
    after the last word (without crossing into the next word). Generous lead/trail
    give the clip breathing room when there's a real pause."""
    words = _all_words(segments)
    if not words:
        return a, b
    inside = [w for w in words if w.end_seconds > a and w.start_seconds < b]
    if not inside:
        return a, b
    first, last = inside[0], inside[-1]
    # previous / next word (may sit outside [a,b]) so we don't slice into them
    prev_end = max([w.end_seconds for w in words if w.end_seconds <= first.start_seconds + 1e-3]
                   or [first.start_seconds - lead - 0.001])
    next_start = min([w.start_seconds for w in words if w.start_seconds >= last.end_seconds - 1e-3]
                     or [last.end_seconds + trail + 0.001])
    na = first.start_seconds - lead
    if na < prev_end:                       # would clip the previous word
        na = (prev_end + first.start_seconds) / 2.0   # sit in the gap instead
    nb = last.end_seconds + trail
    if nb > next_start:                     # would clip the next word
        nb = (last.end_seconds + next_start) / 2.0
    na = max(0.0, na)
    return (na, nb) if nb > na else (a, b)


def _split_block(words, max_len: float):
    """Split a too-long run of words at its LARGEST internal pause, recursively,
    until every piece is <= ``max_len`` — so a long monologue breaks at natural
    stops, never mid-sentence."""
    a, b = words[0].start_seconds, words[-1].end_seconds
    if b - a <= max_len or len(words) < 2:
        return [(a, b)]
    gi = max(range(len(words) - 1),
             key=lambda i: words[i + 1].start_seconds - words[i].end_seconds)
    return _split_block(words[:gi + 1], max_len) + _split_block(words[gi + 1:], max_len)


def _speech_blocks(segments, min_gap: float = 1.2, min_len: float = 4.0,
                   max_len: float = 55.0):
    """Cut the video into NON-OVERLAPPING blocks of continuous talking, split only
    where the speaker actually pauses (a gap >= ``min_gap``). Each block is one
    complete clip — a walkthrough that's narrated straight through stays ONE clip;
    a long block is split at its biggest internal pauses so no piece runs over
    ``max_len``. This replaces the old overlapping-window picker that chopped over
    sentences (owner: "one clean complete clip, don't cut over my talking")."""
    words = _all_words(segments)
    if not words:
        return []
    blocks: list[list] = []
    cur = [words[0]]
    for w in words[1:]:
        if w.start_seconds - cur[-1].end_seconds >= min_gap:
            blocks.append(cur)
            cur = [w]
        else:
            cur.append(w)
    blocks.append(cur)
    out: list[tuple[float, float, str]] = []
    for blk in blocks:
        a, b = blk[0].start_seconds, blk[-1].end_seconds
        if b - a < min_len:
            continue                       # skip a stray word / tiny fragment
        text = " ".join((getattr(w, "text", "") or "") for w in blk)
        if _score_segment_text(text, b - a) <= 0.0:
            continue                       # pure filler/dead-air block
        for (pa, pb) in _split_block(blk, max_len):
            if pb - pa >= min_len:
                out.append((round(pa, 2), round(pb, 2), ""))
    return [(a, b, f"auto-{k + 1}") for k, (a, b, _) in enumerate(out)]


def _shift_segments(segs, off: float):
    """Shift sliced (clip-relative) segments by ``off`` seconds (for stitching)."""
    from services.caption.transcribe import Segment, Word  # lazy
    out = []
    for s in segs:
        out.append(Segment(
            text=s.text, start_seconds=s.start_seconds + off,
            end_seconds=s.end_seconds + off,
            words=[Word(text=w.text, start_seconds=w.start_seconds + off,
                        end_seconds=w.end_seconds + off) for w in s.words]))
    return out


def _clip_pieces(segments, a: float, b: float, drop_below: float) -> list[tuple[float, float]]:
    """Inside [a,b], keep the talking and only cut out a LONG dead/filler stretch
    in the MIDDLE (jump-cut) — never the first or last bit, and never a short
    connective beat. This keeps clips continuous and complete instead of
    "cutting out" or ending early; only a genuinely boring >=1.8s middle run is
    removed (owner spec #5: e.g. "first 5s + 13-20s", boring 6-12s cut).

    Returns merged (start,end) runs. A dropped middle stretch splits the runs;
    everything else stays one continuous piece."""
    segs: list[list[float]] = []
    for s in segments:
        ss, se = getattr(s, "start_seconds", None), getattr(s, "end_seconds", None)
        if ss is None or se is None or se <= a or ss >= b:
            continue
        ss, se = max(ss, a), min(se, b)
        if se <= ss:
            continue
        score = _score_segment_text(getattr(s, "text", "") or "", se - ss)
        segs.append([ss, se, score])
    if not segs:
        return []
    n = len(segs)
    runs: list[list[float]] = []
    for idx, (ss, se, score) in enumerate(segs):
        interior = 0 < idx < n - 1
        # Only drop an INTERIOR, weak, and long-enough (>=1.8s) stretch. Keeping
        # the first/last segment and all short beats is what stops clips from
        # ending early or jump-cutting on every little pause.
        if interior and score < drop_below and (se - ss) >= 1.8:
            continue
        if runs and ss - runs[-1][1] < 0.6:
            runs[-1][1] = se              # bridge small pauses -> one smooth run
        else:
            runs.append([ss, se])
    return [(round(x, 2), round(y, 2)) for x, y in runs]


def _extend_to_thought_end(segments, a: float, b: float, hard_max: float,
                           pause_gap: float = 0.9) -> float:
    """Push ``b`` forward to where the speaker ACTUALLY stops talking — a real
    pause — not just the first period (owner: "clips cut off before I finish").

    Whisper drops a period at every little breath, so stopping at the first ``.``
    chops the thought. Instead, keep extending through every following word while
    the gap to it is under ``pause_gap`` (still talking), and stop at the first
    real pause >= ``pause_gap`` or the ``hard_max`` length cap. _snap_bounds then
    lands the cut inside that pause."""
    words = _all_words(segments)
    if not words:
        return b
    nb = last_end = b
    for w in words:
        if w.start_seconds < nb - 0.05:
            continue                      # already inside the clip
        if w.start_seconds - last_end >= pause_gap:
            break                         # real pause -> the thought is done
        if w.end_seconds - a > hard_max:
            break                         # length cap
        nb = last_end = w.end_seconds
    return max(nb, b)


def _hardcat(parts: list[str], out_path: str) -> str:
    """Jump-cut concat (no crossfade) — keeps audio and exact durations so the
    stitched captions stay perfectly in sync."""
    import subprocess  # lazy
    if len(parts) == 1:
        import shutil
        shutil.copy(parts[0], out_path)
        return out_path
    lst = out_path + ".txt"
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{os.path.abspath(p)}'\n")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out_path],
        check=True, capture_output=True)
    os.remove(lst)
    return out_path


def auto_clips(n: int = 4, match: str | None = None, captions: bool = True) -> list[dict]:
    """Talking-head -> short clips of the best sayings, with animated subtitles.

    Processes up to ``AUTO_CLIPS_VIDEOS`` source videos (default 1) from the
    CONTENT_FOLDER-scoped brand folder. For each: transcribe, accurately pick its
    strongest self-contained moments, clean-cut + drop weak middles, burn the
    few-words-at-a-time karaoke captions, add logo + outro, and add a
    ``status:"review"`` entry. NEVER posts. CAPTIONS=0 skips subs."""
    from services.ingest import dropbox_client as dbx  # lazy

    match = match or os.getenv("PIPELINE_VIDEO") or None
    captions = captions and os.getenv("CAPTIONS", "1").strip().lower() not in ("0", "false", "no")
    nv_raw = (os.getenv("AUTO_CLIPS_VIDEOS") or "1").strip().lower()
    n_videos = 100000 if nv_raw in ("all", "0", "max", "*", "") else int(nv_raw)
    vids = _list_videos(dbx, n_videos, match)
    if not vids:
        print("auto_clips: no matching video found.")
        return []
    print(f"auto_clips: processing {len(vids)} video(s): {[v[2] for v in vids]}")
    queue = _load_json(QUEUE_PATH, [])
    made: list[dict] = []
    for ctx in vids:
        try:
            made += _clips_for_video(ctx, n, captions, dbx, queue)
        except Exception as ex:  # noqa: BLE001 — one bad video never kills the batch
            print(f"auto_clips: video {ctx[2]} failed: {ex}")
    _save_json(QUEUE_PATH, queue)
    print(f"auto_clips: {len(made)} captioned clip(s) from {len(vids)} video(s). "
          f"Nothing posted (status=review).")
    return made


def _clips_for_video(ctx, n: int, captions: bool, dbx, queue: list) -> list[dict]:
    """Make the captioned clips for ONE source video (mutates ``queue``)."""
    from services.caption import transcribe  # lazy
    from services.caption.burn import write_ass  # lazy
    from services.assemble.style import append_outro  # lazy — brand end-card

    _f, local, base, brand, display = ctx
    brand_key, dispname, tags = brand
    segs = _fix_brand_words(transcribe(local))   # correct brand mis-hears first
    # Diagnostic: how much speech did Whisper actually find? 0 segments == truly
    # silent/no-audio footage; >0 == someone is talking and MUST yield clips.
    spoken = [s for s in segs
              if (getattr(s, "text", "") or "").strip()
              and getattr(s, "end_seconds", 0) > getattr(s, "start_seconds", 0)]
    words = sum(len((getattr(s, "text", "") or "").split()) for s in spoken)
    print(f"auto_clips: {base}: {len(spoken)} speech segment(s), ~{words} words.")
    # Pull MULTIPLE good sayings per video (owner: "more than 6 clips from 5
    # videos"). Tighter windows (<=28s, near the 12-30s ideal) let a longer
    # video pack 2-4 clips instead of one 45s window eating the whole timeline;
    # a 0.4 floor still drops filler/dead-air (those score <=0) but lets solid
    # sayings through so weak videos still yield something. Both env-tunable.
    # ONE clean complete clip per continuous block of talking — split only where
    # the speaker actually pauses (>= CLIP_PAUSE_GAP). No overlapping windows, no
    # cutting over sentences. A straight-through walkthrough stays one clip; a
    # long block is split at its biggest internal pauses (<= CLIP_MAX_LEN).
    pause_gap = float(os.getenv("CLIP_PAUSE_GAP", "1.2"))
    max_len = float(os.getenv("CLIP_MAX_LEN", "55"))
    wins = _speech_blocks(segs, min_gap=pause_gap, min_len=4.0, max_len=max_len)
    if not wins:
        why = ("only filler/garbled speech, no real saying"
               if spoken else "TRULY no speech (0 segments)")
        print(f"auto_clips: {base}: no usable block ({why}) — skipped as b-roll "
              f"(use the montage path for footage with no real talking).")
        return []
    print(f"auto_clips: {base} -> {[(a, b) for a, b, _ in wins]}")

    workdir = os.path.dirname(local)
    # Caption look (owner spec): bold sans, white + thin outline, ~48-60px, shown
    # a few words at a time. Roboto ships on the runner (fonts-roboto).
    font = os.getenv("CAPTION_FONT", "Roboto")
    fsize = int(os.getenv("CAPTION_FONT_SIZE", "54"))
    max_words = int(os.getenv("CAPTION_MAX_WORDS", "4"))
    made: list[dict] = []
    lg = _brand_logo(brand_key)
    for a0, b0, nm in wins:
        cut = os.path.join(workdir, f"{base}-{nm}.mp4")
        try:
            # The block already ends at a real pause; just trim filler edges and
            # snap the cut points INTO the surrounding silence (never mid-word).
            a, b = _trim_to_clean(segs, a0, b0)
            a, b = _snap_bounds(segs, a, b)
            # ONE continuous slice — never jump-cut, so no words are dropped out
            # of the middle of someone talking.
            pieces = [(a, b)]
            parts: list[str] = []
            clip_segs: list = []
            off = 0.0
            for k, (pa, pb) in enumerate(pieces):
                pp = os.path.join(workdir, f"{base}-{nm}-p{k}.mp4")
                _edit_short(local, pa, pb, pp, srt=None, mute=False, logo=lg)
                parts.append(pp)
                clip_segs += _shift_segments(_slice_segments(segs, pa, pb), off)
                off += max(0.1, pb - pa)
            _hardcat(parts, cut)          # jump-cut concat (single piece = copy)
            final = cut
            if captions:
                ass = os.path.join(workdir, f"{base}-{nm}.ass")
                write_ass(clip_segs, ass, font=font, font_size=fsize,
                          max_words=max_words)
                capped = os.path.join(workdir, f"{base}-{nm}-cap.mp4")
                _burn_ass(cut, ass, capped)
                final = capped
            # brand outro end-card on every clip
            with_outro = os.path.join(workdir, f"{base}-{nm}-final.mp4")
            try:
                append_outro(final, with_outro)
                final = with_outro
            except Exception as ex:  # noqa: BLE001 — keep the clip even if outro fails
                print(f"auto_clips: outro skipped for {nm}: {ex}")
        except Exception as ex:  # noqa: BLE001 — one bad clip never kills the run
            print(f"auto_clips: clip {nm} failed: {ex}")
            continue
        saying = _transcript_text(clip_segs)[:280]
        if not saying.strip():
            # No spoken words landed in this window — never ship a silent
            # "talking" clip. Skip it rather than upload dead air.
            print(f"auto_clips: {nm}: empty transcript after trim — skipped (no talking).")
            continue
        out_name = f"{base}-{nm}.mp4"
        out_path = f"{display.rstrip('/')}/processed/{out_name}"
        dbx.upload(final, out_path)
        url = dbx.shared_link(out_path, raw=True)
        queue[:] = [e for e in queue if e.get("id") != f"{brand_key}-{base}-{nm}"]
        entry = {
            "id": f"{brand_key}-{base}-{nm}", "brand": brand_key,
            "text": saying, "media_url": url, "media_path": out_path,
            "platforms": list(REVIEW_PLATFORMS), "schedule": None,
            "status": "review", "error": None,
        }
        queue.append(entry)
        made.append(entry)
        print(f"[{brand_key}] {nm}: {a:.0f}-{b:.0f}s -> {out_path}  \"{saying[:60]}\"")
    return made


_HP_BEATS = (
    ("Excellence Isn't Optional", "fade"),
    ("It's Our Standard", "word"),
    ("Transform Your Outdoors", "fade"),
)


def _auto_beats(duration: float) -> list[dict]:
    """Spread the default HP serif lines across a montage's duration."""
    n = len(_HP_BEATS)
    usable = max(2.0, duration - 0.6)
    span = usable / n
    beats = []
    for i, (text, mode) in enumerate(_HP_BEATS):
        s = 0.3 + i * span
        beats.append({"text": text, "start": round(s, 2),
                      "end": round(s + span - 0.15, 2), "mode": mode})
    return beats


def auto_montage(match: str | None = None, target_s: float | None = None,
                 style: bool = True) -> dict | None:
    """Phase 3: auto-build a 10–20s locked-style montage from a video's BEST shots.

    Plans a clip that lands near ``target_s`` (default 15s, env MONTAGE_TARGET)
    using ONLY shots at/above the quality floor (env MONTAGE_MIN_SCORE, default 50)
    — a weak video yields no clip rather than bad content. Lays the chosen shots
    out in shifting layouts (each trimmed to a beat), crossfades them, then — when
    ``style`` — burns serif beats, logos the corner, and crossfades the outro on.
    Uploads as a ``status:"review"`` entry carrying its ``fire_score``. NEVER posts."""
    from services.ingest import dropbox_client as dbx  # lazy
    from services.score.shots import detect_shots  # lazy
    from services.score.visual import score_shot  # lazy
    from services.assemble.style import (  # lazy
        select_for_montage, serif_beats, add_logo, append_outro)

    match = match or os.getenv("PIPELINE_VIDEO") or None
    target_s = target_s if target_s is not None else float(os.getenv("MONTAGE_TARGET", "15"))
    min_score = float(os.getenv("MONTAGE_MIN_SCORE", "50"))
    beat_s = float(os.getenv("MONTAGE_BEAT", "3.0"))
    ctx = _first_video(dbx, match)
    if not ctx:
        print("auto_montage: no matching video found.")
        return None
    _f, local, base, brand, display = ctx
    brand_key, dispname, tags = brand

    # Load (or compute) shot scores for this video.
    score_file = os.path.join(ROOT, "content", "scores", f"{brand_key}-{base}.json")
    scored = _load_json(score_file, {}).get("shots")
    if not scored:
        shots = detect_shots(local)
        scored = [{**s, **score_shot(local, s["start"], s["end"])} for s in shots]

    # Plan a target-length montage from only good shots (quality floor applied).
    plan = select_for_montage(scored, target_s=target_s, beat_s=beat_s,
                              min_score=min_score, min_gap=1.0, xfade=0.45)
    if not plan:
        print(f"auto_montage: no shots clear the quality bar ({min_score}) for "
              f"{base} — skipping (no clip rather than weak content).")
        return None
    seg_scores = [sc for seg in plan for sc in seg["scores"] if sc is not None]

    # Render each planned segment in its layout.
    workdir = os.path.dirname(local)
    seg_clips: list[str] = []
    for li, seg in enumerate(plan):
        lay, wins = seg["layout"], seg["windows"]
        n = len(wins)
        out = os.path.join(workdir, f"aseg-{base}-{li}.mp4")
        if n == 1:
            _edit_short(local, float(wins[0][0]), float(wins[0][1]), out, mute=True)
        elif lay == "cols2":
            w = 1080 // n
            tiles = []
            for j, (a, b) in enumerate(wins):
                pp = os.path.join(workdir, f"aseg-{base}-{li}-c{j}.mp4")
                _edit_tile(local, float(a), float(b), pp, w, 1920)
                tiles.append(pp)
            _hstackN(tiles, out)
        else:  # rows2 / rows3
            h = 1920 // n
            panels = []
            for j, (a, b) in enumerate(wins):
                pp = os.path.join(workdir, f"aseg-{base}-{li}-p{j}.mp4")
                _edit_tile(local, float(a), float(b), pp, 1080, h)
                panels.append(pp)
            _stackN(panels, out)
        seg_clips.append(out)

    montage = os.path.join(workdir, f"{base}-automontage.mp4")
    _concat_v(seg_clips, montage, xfade=0.45)

    final = montage
    if style:
        try:
            import subprocess
            dur = float(subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nw=1:nk=1", montage],
                capture_output=True, text=True).stdout.strip() or "12")
            styled = os.path.join(workdir, f"{base}-styled.mp4")
            tmp1 = os.path.join(workdir, f"{base}-t1.mp4")
            tmp2 = os.path.join(workdir, f"{base}-t2.mp4")
            serif_beats(montage, tmp1, _auto_beats(dur))   # b-roll: text overlay OK
            add_logo(tmp1, tmp2)
            append_outro(tmp2, styled)
            final = styled
        except Exception as ex:  # noqa: BLE001 — styling is best-effort; ship the montage
            print(f"auto_montage: styling skipped ({ex}); using unstyled montage.")
            final = montage

    fire = round(sum(seg_scores) / len(seg_scores), 1) if seg_scores else 0.0
    out_path = f"{display.rstrip('/')}/processed/{base}-automontage.mp4"
    dbx.upload(final, out_path)
    url = dbx.shared_link(out_path, raw=True)
    queue = [e for e in _load_json(QUEUE_PATH, [])
             if e.get("id") != f"{brand_key}-{base}-auto"]
    entry = {
        "id": f"{brand_key}-{base}-auto", "brand": brand_key,
        "text": _hp_caption(base) if brand_key == "hp" else "",
        "media_url": url, "media_path": out_path,
        "platforms": list(REVIEW_PLATFORMS), "schedule": None,
        "status": "review", "error": None, "fire_score": fire,
    }
    queue.append(entry)
    _save_json(QUEUE_PATH, queue)
    print(f"auto_montage: {brand_key}-{base}-auto ({len(seg_clips)} segments, "
          f"fire={fire}) -> {out_path}")
    return entry


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
    for i, seg in enumerate(spec.get("segments", [])):
        shots = seg.get("panels") or ([seg["shot"]] if seg.get("shot") else [])
        if not shots:
            continue
        ctx0 = resolve(str(shots[0][0]))
        if not ctx0:
            raise RuntimeError(f"video not found: {shots[0][0]!r}")
        if base_ctx is None:
            base_ctx, workdir = ctx0, os.path.dirname(ctx0[1])
        out = os.path.join(workdir, f"mseg-{name}-{i}.mp4")
        n = len(shots)
        if n == 1:
            v, a, b = shots[0]
            _edit_short(resolve(str(v))[1], float(a), float(b), out, mute=True)
        elif seg.get("orient") == "cols":
            # side-by-side vertical columns (each tile W/n x 1920)
            w = 1080 // n
            tiles = []
            for k, (v, a, b) in enumerate(shots):
                pp = os.path.join(workdir, f"mseg-{name}-{i}-c{k}.mp4")
                _edit_tile(resolve(str(v))[1], float(a), float(b), pp, w, 1920)
                tiles.append(pp)
            _hstackN(tiles, out)
        else:
            # stacked rows (each tile 1080 x H/n)
            h = 1920 // n
            panels = []
            for k, (v, a, b) in enumerate(shots):
                pp = os.path.join(workdir, f"mseg-{name}-{i}-p{k}.mp4")
                _edit_tile(resolve(str(v))[1], float(a), float(b), pp, 1080, h)
                panels.append(pp)
            _stackN(panels, out)
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

    # IG_REFERENCE: pull a brand's posted IG media (thumbs+captions) to study its
    # house style. Value = brand key, optional ":N" limit (e.g. "hp" or "hp:30").
    igref = os.getenv("IG_REFERENCE", "").strip()
    if igref:
        bk = igref.split(":")[0] or "hp"
        tail = igref.split(":")[1] if ":" in igref else ""
        fetch_ig_reference(bk, int(tail) if tail.isdigit() else 24)
        return 0

    # MONTAGE_SPEC json: assemble a layout-shifting hype montage (3-up/2-up/single).
    montage = os.getenv("MONTAGE_SPEC", "").strip()
    if montage:
        import json as _json
        made = cut_montage(_json.loads(montage))
        print(f"\nDone: montage {'created' if made else 'failed'}. Nothing posted (review only).")
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

    # KEEP_IDS: delete every clip (Dropbox file + queue entry) not in this
    # comma-separated id list — clears stale batches from the review folder.
    keep_ids = os.getenv("KEEP_IDS", "").strip()
    if keep_ids:
        prune_clips(keep_ids.split(","))
        return 0

    # DELETE_IDS: delete just these clips (Dropbox file + queue entry); keep the
    # rest — for clearing out a handful of bad/garbled/orphan clips.
    del_ids = os.getenv("DELETE_IDS", "").strip()
    if del_ids:
        delete_clips(del_ids.split(","))
        return 0

    # COPY_IDS: copy approved clips into a brand subfolder (e.g. 'HP Posts').
    copy_ids = os.getenv("COPY_IDS", "").strip()
    if copy_ids:
        copy_clips(copy_ids.split(","), os.getenv("COPY_DEST", "HP Posts").strip() or "HP Posts")
        return 0

    # Dump a timestamped transcript so clip windows can be chosen by time.
    if os.getenv("DUMP_TRANSCRIPT", "").strip().lower() in ("1", "true", "yes"):
        dump_transcript()
        return 0

    # Dump per-video contact sheets so the footage can be 'seen' to pick shots.
    if os.getenv("DUMP_THUMBS", "").strip().lower() in ("1", "true", "yes"):
        dump_thumbs()
        return 0

    # DETECT_SHOTS: Phase 1 of the bulk pipeline — scene-split every brand video
    # into content/shots/*.json for scoring. "1"/"true" = all; "force" to redo
    # unchanged videos; any other value = a filename substring to target one.
    ds = os.getenv("DETECT_SHOTS", "").strip()
    if ds:
        low = ds.lower()
        force = low in ("force", "all-force")
        match = None if low in ("1", "true", "yes", "all", "force", "all-force") else ds
        detect_shots_bulk(match=match, force=force)
        return 0

    # SCORE_SHOTS: Phase 2 — score + rank every shot best-first into
    # content/scores/*.json. Same value grammar as DETECT_SHOTS.
    ss = os.getenv("SCORE_SHOTS", "").strip()
    if ss:
        low = ss.lower()
        force = low in ("force", "all-force")
        match = None if low in ("1", "true", "yes", "all", "force", "all-force") else ss
        score_shots_bulk(match=match, force=force)
        return 0

    # AUTO_MONTAGE: Phase 3 — auto-assemble a locked-style montage from a video's
    # top-scored shots (value = how many shots to use, e.g. "6").
    am = os.getenv("AUTO_MONTAGE", "").strip()
    if am:
        try:
            target = float(am)
        except ValueError:
            target = None   # "1"/"true" -> default 15s target
        made = auto_montage(target_s=target)
        print(f"\nDone: {1 if made else 0} auto montage. Nothing posted (status=review).")
        return 0

    # REVIEW_FEED: Phase 4 — (re)build the best-first review page.
    if os.getenv("REVIEW_FEED", "").strip().lower() in ("1", "true", "yes"):
        build_review_feed()
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

    # AUTO_CLIPS: talking-head -> best sayings as short clips WITH animated
    # subtitles (value = how many clips, e.g. "4"). Set CAPTIONS=0 to skip subs.
    ac = os.getenv("AUTO_CLIPS", "").strip()
    if ac:
        try:
            n = int(ac)
        except ValueError:
            n = 4
        made = auto_clips(n=n)
        print(f"\nDone: {len(made)} captioned clip(s). Nothing posted (all status=review).")
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
