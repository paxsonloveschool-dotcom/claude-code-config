"""The posting queue: a plain JSON file of finished posts to publish.

The Mac builds content, appends ``QueuedPost`` entries (status ``pending``),
commits ``content/queue.json``, and pushes. A GitHub Actions cron job then reads
the queue, finds *due* posts, fires them at the platform APIs, marks each
``sent``/``failed``, and writes the queue back. Pure stdlib, no network.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass


@dataclass
class QueuedPost:
    """One finished post waiting to be published.

    Attributes:
        id: Stable unique id for this post (used for dedupe/logging).
        text: Caption / body text.
        media_url: PUBLIC media URL (image or video), or None for a text post.
        platforms: Target platforms, e.g. ["instagram", "facebook"].
        schedule: ISO-8601 UTC time to post at, or None to post as soon as due.
        status: "pending" (default) -> "sent" or "failed".
        error: Failure reason when status == "failed", else None.
    """

    id: str
    text: str
    media_url: str | None = None
    platforms: list[str] = None  # type: ignore[assignment]
    schedule: str | None = None
    status: str = "pending"
    error: str | None = None

    def __post_init__(self) -> None:
        if self.platforms is None:
            self.platforms = []


def load_queue(path: str) -> list[QueuedPost]:
    """Load a queue JSON file into a list of ``QueuedPost``.

    A missing or empty file yields an empty queue. The file is a JSON array of
    objects whose keys match ``QueuedPost`` fields; unknown keys are ignored.
    """
    import os  # lazy, stdlib

    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        raw = f.read().strip()
    if not raw:
        return []
    data = json.loads(raw)

    fields = set(QueuedPost.__dataclass_fields__)
    posts: list[QueuedPost] = []
    for item in data:
        kwargs = {k: v for k, v in item.items() if k in fields}
        posts.append(QueuedPost(**kwargs))
    return posts


def save_queue(path: str, posts: list[QueuedPost]) -> None:
    """Write ``posts`` back to ``path`` as stable, pretty-printed JSON."""
    payload = [asdict(p) for p in posts]
    text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n")


def due_posts(posts: list[QueuedPost], now_iso: str) -> list[QueuedPost]:
    """Return pending posts whose schedule is None or has arrived.

    A post is due when ``status == "pending"`` AND (``schedule is None`` OR
    ``schedule <= now_iso``). ISO-8601 UTC strings compare correctly
    lexicographically, so no datetime parsing is needed.
    """
    out: list[QueuedPost] = []
    for p in posts:
        if p.status != "pending":
            continue
        if p.schedule is None or p.schedule <= now_iso:
            out.append(p)
    return out
