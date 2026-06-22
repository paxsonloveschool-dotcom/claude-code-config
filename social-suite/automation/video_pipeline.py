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


def _edit_short(src: str, a: float, b: float, out_path: str, srt: str | None = None) -> str:
    """Cut [a,b], reframe to vertical 1080x1920, optionally burn bold captions."""
    import subprocess  # lazy, stdlib

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    if srt:
        vf += f",subtitles={srt}:force_style='{_CAPTION_STYLE}'"
    # Input seeking (-ss before -i) resets PTS to 0 so the shifted SRT lines up.
    cmd = [
        "ffmpeg", "-y", "-ss", f"{a:.2f}", "-i", src, "-t", f"{max(0.1, b - a):.2f}",
        "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", out_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


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

    # Alternate a style per chunk so the owner can compare: even = clean (no
    # captions), odd = bold burned subtitles. (Music/SFX added once a track exists.)
    for i, (a, b, label) in enumerate(_windows(s0, e0)):
        style = "captions" if i % 2 == 1 else "plain"
        out_name = f"{base}-{label}-{style}.mp4"
        out_local = os.path.join(os.path.dirname(local), out_name)
        srt = None
        if style == "captions":
            srt = _write_srt(segments, a, b, os.path.join(os.path.dirname(local), f"{base}-{label}.srt"))
        try:
            _edit_short(local, a, b, out_local, srt=srt)
        except Exception as ex:  # noqa: BLE001 — skip a bad cut, keep the rest
            print(f"[{brand_key}] cut {label} ({style}) failed: {ex}")
            continue
        out_path = f"{folder_display.rstrip('/')}/processed/{out_name}"
        dbx.upload(out_local, out_path)
        url = dbx.shared_link(out_path, raw=True)
        entry = {
            "id": f"{brand_key}-{stamp}-{label}-{style}",
            "brand": brand_key,
            "text": caption,
            "media_url": url,
            "platforms": list(REVIEW_PLATFORMS),
            "schedule": None,
            "status": "review",   # NEVER posts (poster only fires "pending")
            "error": None,
        }
        queue.append(entry)
        entries.append(entry)
        print(f"[{brand_key}] cut {label} [{style}]: {a:.0f}-{b:.0f}s ({b - a:.0f}s) -> {out_path}")

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
