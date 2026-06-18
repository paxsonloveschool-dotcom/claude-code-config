"""Publish all due posts from the queue — the script GitHub Actions runs.

Reads ``content/queue.json`` (overridable), finds posts that are due now, routes
each to the right platform poster using env-provided Meta credentials, marks
``sent``/``failed`` per post, and writes the queue back. One failing post never
aborts the rest.

Env:
    META_ACCESS_TOKEN  Long-lived Meta token (FB Page + IG publishing).
    IG_USER_ID         Instagram Professional account id (for "instagram").
    FB_PAGE_ID         Facebook Page id (for "facebook").
    QUEUE_PATH         Optional queue file path (default content/queue.json).

Usage:
    python services/publish/run_due.py [queue_path] [--dry-run]
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

# Make this runnable both as a module and as a bare script (GitHub Actions runs
# it by path), so ``services.publish.*`` imports resolve either way.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.publish.queue import (  # noqa: E402
    QueuedPost,
    due_posts,
    load_queue,
    save_queue,
)

DEFAULT_QUEUE_PATH = "content/queue.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _post_one(post: QueuedPost) -> None:
    """Route a single post to each of its target platforms.

    Raises on the first platform error so the caller can mark the post failed.
    Posters are looked up lazily so importing this module needs no network.
    """
    from services.publish.direct import meta  # lazy

    token = os.environ.get("META_ACCESS_TOKEN", "")
    if not token:
        raise RuntimeError("META_ACCESS_TOKEN is not set.")

    for platform in post.platforms:
        if platform == "facebook":
            page_id = os.environ.get("FB_PAGE_ID", "")
            if not page_id:
                raise RuntimeError("FB_PAGE_ID is not set (needed for facebook).")
            meta.post_facebook(
                page_id=page_id,
                access_token=token,
                message=post.text,
                image_url=post.media_url,
            )
        elif platform == "instagram":
            ig_user_id = os.environ.get("IG_USER_ID", "")
            if not ig_user_id:
                raise RuntimeError("IG_USER_ID is not set (needed for instagram).")
            if not post.media_url:
                raise RuntimeError("instagram requires a public media_url.")
            meta.post_instagram(
                ig_user_id=ig_user_id,
                access_token=token,
                caption=post.text,
                image_url=post.media_url,
            )
        else:
            raise RuntimeError(f"Unsupported platform: {platform!r}")


def run(queue_path: str, *, dry_run: bool = False, now_iso: str | None = None) -> dict:
    """Publish all due posts and return a summary dict.

    Args:
        queue_path: Path to the queue JSON file.
        dry_run: When True, route nothing — only print what WOULD post.
        now_iso: Override "now" (ISO-8601 UTC); defaults to the real now.

    Returns:
        {"posted": int, "failed": int, "skipped": int} counts.
    """
    now = now_iso or _now_iso()
    posts = load_queue(queue_path)
    due = due_posts(posts, now)
    due_ids = {id(p) for p in due}

    posted = failed = 0
    for post in due:
        targets = ",".join(post.platforms)
        if dry_run:
            print(f"[dry-run] WOULD post {post.id} -> [{targets}]: {post.text[:60]!r}")
            continue
        try:
            _post_one(post)
            post.status = "sent"
            post.error = None
            posted += 1
            print(f"[sent] {post.id} -> [{targets}]")
        except Exception as e:  # noqa: BLE001 — isolate per-post failures
            post.status = "failed"
            post.error = str(e)
            failed += 1
            print(f"[failed] {post.id} -> [{targets}]: {e}")

    skipped = sum(1 for p in posts if id(p) not in due_ids and p.status == "pending")

    if not dry_run:
        save_queue(queue_path, posts)

    summary = {"posted": posted, "failed": failed, "skipped": skipped}
    print(
        f"\nSummary: posted={posted} failed={failed} "
        f"skipped(not-due)={skipped} (dry_run={dry_run})"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Publish due posts from the queue.")
    parser.add_argument(
        "queue_path",
        nargs="?",
        default=os.environ.get("QUEUE_PATH", DEFAULT_QUEUE_PATH),
        help="Path to queue.json (default: content/queue.json or $QUEUE_PATH).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Route nothing.")
    args = parser.parse_args(argv)

    summary = run(args.queue_path, dry_run=args.dry_run)
    # Non-zero exit if anything failed, so the Action surfaces it (but the queue
    # is already saved so successes persist).
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
