"""Video pipeline: Dropbox brand folders -> captioned clip -> REVIEW queue.

For each brand subfolder in the Dropbox app folder (``/HP``, ``/Restore``, …):
pull new videos, transcribe them, write a caption (free $0 writer by default),
burn the captions onto the video, upload the finished clip back to a
``<Brand>/processed/`` folder the owner can watch, and append a queue entry with
``status:"review"``. **Nothing is ever posted** — the poster only fires
``status:"pending"``, so review items sit until the owner approves them.

Brand routing is by folder name (``/HP`` -> ``hp``), so a client's video can
only ever produce a post for that client's own accounts.

Run on GitHub Actions (heavy ffmpeg/whisper deps + Dropbox secrets live there):
    python automation/video_pipeline.py
Heavy imports (dropbox, faster-whisper, ffmpeg via subprocess) are all lazy, so
this module imports fine without them installed.
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

# Brand folder name -> (brand key, display name, default hashtags). The folder
# names match what the owner created in Dropbox.
BRANDS = {
    "HP": ("hp", "HP Landscaping", ["HPLandscaping", "landscaping", "lawncare"]),
    "Restore": ("restore", "Restore Marketing", ["RestoreMarketing", "marketing"]),
}
# Which platforms each review item targets once approved. FB + IG are connected.
REVIEW_PLATFORMS = [p.strip() for p in os.getenv("REVIEW_PLATFORMS", "instagram,facebook").split(",") if p.strip()]


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


def process_brand_folder(folder_name: str, *, dry_run: bool = False) -> list[dict]:
    """Process one brand's Dropbox folder; return the review entries created."""
    from services.ingest import dropbox_client as dbx  # lazy

    brand_key, display, default_tags = BRANDS.get(
        folder_name, (folder_name.lower(), folder_name, [])
    )
    processed = set(_load_json(PROCESSED_PATH, []))
    created: list[dict] = []

    files = dbx.list_folder(f"/{folder_name}")
    for f in files:
        if not f.name.lower().endswith(VIDEO_EXTS):
            continue
        if f.rev in processed:
            continue  # already handled
        print(f"[{brand_key}] processing {f.name} (rev {f.rev})")
        if dry_run:
            created.append({"id": f"{brand_key}-DRYRUN-{_slug(f.name)}", "brand": brand_key})
            continue
        try:
            entry = _process_one(f, brand_key, display, default_tags, dbx)
            created.append(entry)
            processed.add(f.rev)
        except Exception as e:  # noqa: BLE001 — one bad video never kills the run
            print(f"[{brand_key}] FAILED {f.name}: {e}")

    _save_json(PROCESSED_PATH, sorted(processed))
    return created


def _process_one(f, brand_key, display, default_tags, dbx) -> dict:
    """Download -> transcribe -> caption -> burn -> upload -> review entry."""
    from services.caption import burn_captions, transcribe  # lazy (whisper/ffmpeg)
    from services.write.free_writer import generate_caption  # lazy

    local = dbx.download(f)
    segments = transcribe(local)
    transcript = _transcript_text(segments)

    copy = generate_caption(
        {"transcript": transcript, "brand_name": display},
        default_hashtags=default_tags,
    )
    caption = _compose(copy)

    captioned = burn_captions(local, segments)  # returns local path to captioned mp4

    out_name = f"{_slug(f.name)}-captioned.mp4"
    out_path = f"/{display_folder(brand_key)}/processed/{out_name}"
    dbx.upload(captioned, out_path)
    url = dbx.shared_link(out_path, raw=True)

    entry = {
        "id": f"{brand_key}-{_dt.datetime.utcnow():%Y%m%d%H%M%S}-{_slug(f.name)}",
        "brand": brand_key,
        "text": caption,
        "media_url": url,
        "platforms": list(REVIEW_PLATFORMS),
        "schedule": None,
        "status": "review",   # NEVER posts (poster only fires "pending")
        "error": None,
    }
    _append_review(entry)
    print(f"[{brand_key}] review ready -> {out_path}\n  caption: {caption[:80]!r}")
    return entry


def display_folder(brand_key: str) -> str:
    """Map a brand key back to its Dropbox folder name (HP/Restore)."""
    for folder, (key, *_rest) in BRANDS.items():
        if key == brand_key:
            return folder
    return brand_key


def _append_review(entry: dict) -> None:
    queue = _load_json(QUEUE_PATH, [])
    queue.append(entry)
    _save_json(QUEUE_PATH, queue)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Process Dropbox brand videos into the review queue.")
    parser.add_argument("--dry-run", action="store_true", help="List/route only; no download/transcribe/post.")
    parser.add_argument("--brand", default=None, help="Only this folder (e.g. HP).")
    args = parser.parse_args(argv)

    folders = [args.brand] if args.brand else list(BRANDS)
    total = 0
    for folder in folders:
        created = process_brand_folder(folder, dry_run=args.dry_run)
        total += len(created)
    print(f"\nDone: {total} review item(s) created. Nothing was posted (all status=review).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
