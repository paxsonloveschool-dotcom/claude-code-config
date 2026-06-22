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


def _edit_short(src: str, a: float, b: float, out_path: str, srt: str | None = None,
                mute: bool = False, music: str | None = None) -> str:
    """Cut [a,b], reframe vertical 1080x1920. Optional bold captions, mute audio,
    or replace audio with looped background ``music``."""
    import subprocess  # lazy, stdlib

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    dur = max(0.1, b - a)
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    if srt:
        vf += f",subtitles={srt}:force_style='{_CAPTION_STYLE}'"
    cmd = ["ffmpeg", "-y", "-ss", f"{a:.2f}", "-i", src]
    if music:
        cmd += ["-stream_loop", "-1", "-i", music]   # loop the track to fill the clip
    cmd += ["-t", f"{dur:.2f}", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23"]
    if music:
        cmd += ["-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "160k"]
    elif mute:
        cmd += ["-an"]
    else:
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    cmd += ["-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def _concat(parts: list[str], out_path: str, xfade: float = 0.4) -> str:
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
    for path_lower, display in _top_level_folders(dbx):
        brand = classify_brand(display)
        if not brand:
            continue
        vids = [f for f in dbx.list_folder(path_lower) if f.name.lower().endswith(VIDEO_EXTS)]
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
                ctxs, tmp = [], []
                for j, part in enumerate(parts_spec):
                    ctx = resolve(part.get("video") or default_match)
                    if not ctx:
                        raise RuntimeError(f"video not found: {part.get('video')!r}")
                    ctxs.append(ctx)
                    plocal = ctx[1]
                    pp = os.path.join(os.path.dirname(plocal), f"xv-{nm}-{j}.mp4")
                    _edit_short(plocal, float(part["start"]), float(part["end"]), pp,
                                srt=None, mute=bool(sp.get("mute")))
                    tmp.append(pp)
                _f, local, base, brand, display = ctxs[0]
                out_local = os.path.join(os.path.dirname(local), f"{base}-{nm}.mp4")
                _concat(tmp, out_local)
            else:
                ctx = resolve(sp.get("video") or default_match)
                if not ctx:
                    raise RuntimeError("video not found")
                _f, local, base, brand, display = ctx
                out_local = os.path.join(os.path.dirname(local), f"{base}-{nm}.mp4")
                wins = sp.get("segments") or [[sp["start"], sp["end"]]]
                if len(wins) == 1:
                    _edit_short(local, float(wins[0][0]), float(wins[0][1]), out_local, srt=None,
                                mute=bool(sp.get("mute")), music=(music_path if sp.get("music") else None))
                else:
                    pl = []
                    for j, w in enumerate(wins):
                        pp = os.path.join(os.path.dirname(local), f"{base}-{nm}-p{j}.mp4")
                        _edit_short(local, float(w[0]), float(w[1]), pp, srt=None, mute=bool(sp.get("mute")))
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
        caption = caption_for(local, base, dispname, tags)
        keep = []
        for e in queue:
            if e.get("brand") == brand_key and e["id"].endswith(f"-{nm}"):
                if e.get("media_path"):
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

    # Dump a timestamped transcript so clip windows can be chosen by time.
    if os.getenv("DUMP_TRANSCRIPT", "").strip().lower() in ("1", "true", "yes"):
        dump_transcript()
        return 0

    # Dump per-video contact sheets so the footage can be 'seen' to pick shots.
    if os.getenv("DUMP_THUMBS", "").strip().lower() in ("1", "true", "yes"):
        dump_thumbs()
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
