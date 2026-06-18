"""Migrate the flat ``content/queue.json`` (QueuedPost format) into the DB.

Each QueuedPost becomes one ``Post`` under the given brand, fanned out to one
``PostTarget`` per platform. Channels are created on demand (disconnected) so
targets always reference a real channel. A MediaAsset is created when the post
carries a ``media_url``. Idempotent on ``Post.external_ref`` (the queue id).

QueuedPost shape (see services/publish/queue.py)::

    {"id", "text", "media_url", "platforms": [...], "schedule", "status", "error"}
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Union

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    Channel,
    HealthStatus,
    MediaAsset,
    MediaKind,
    Platform,
    Post,
    PostSource,
    PostStatus,
    PostTarget,
    PostTargetStatus,
)

# queue.json platform strings -> Platform enum (queue uses full names).
_PLATFORM_MAP = {
    "facebook": Platform.facebook,
    "instagram": Platform.instagram,
    "x": Platform.x,
    "twitter": Platform.x,
    "tiktok": Platform.tiktok,
    "youtube": Platform.youtube,
    "gbp": Platform.gbp,
    "google": Platform.gbp,
    "google_business": Platform.gbp,
}

_QUEUE_STATUS_TO_POST = {
    "pending": PostStatus.scheduled,
    "sent": PostStatus.published,
    "failed": PostStatus.failed,
}
_QUEUE_STATUS_TO_TARGET = {
    "pending": PostTargetStatus.pending,
    "sent": PostTargetStatus.published,
    "failed": PostTargetStatus.failed,
}


def _parse_dt(value: Union[str, None]) -> Union[datetime, None]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _get_or_create_channel(db: Session, brand_id: int, platform: Platform) -> Channel:
    ch = db.execute(
        select(Channel).where(
            Channel.brand_id == brand_id, Channel.platform == platform
        )
    ).scalar_one_or_none()
    if ch is None:
        ch = Channel(
            brand_id=brand_id,
            platform=platform,
            health_status=HealthStatus.disconnected,
            enabled=True,
        )
        db.add(ch)
        db.flush()
    return ch


def migrate_queue(queue_json_path: str, db: Session, brand_id: int) -> int:
    """Read ``queue_json_path`` and create Post + PostTarget rows under
    ``brand_id``. Returns the number of Posts created (skips ones already
    migrated, matched on the queue id via ``Post.external_ref``)."""
    with open(queue_json_path, "r", encoding="utf-8") as fh:
        items = json.load(fh)

    created = 0
    for item in items:
        ext_ref = item.get("id")
        if ext_ref:
            existing = db.execute(
                select(Post).where(
                    Post.brand_id == brand_id, Post.external_ref == ext_ref
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue

        q_status = item.get("status", "pending")
        post = Post(
            brand_id=brand_id,
            base_text=item.get("text", "") or "",
            status=_QUEUE_STATUS_TO_POST.get(q_status, PostStatus.scheduled),
            scheduled_for=_parse_dt(item.get("schedule")),
            source=PostSource.pipeline,
            external_ref=ext_ref,
        )
        db.add(post)
        db.flush()

        media_asset = None
        media_url = item.get("media_url")
        if media_url:
            media_asset = MediaAsset(
                brand_id=brand_id,
                kind=MediaKind.image,
                public_url=media_url,
            )
            db.add(media_asset)
            db.flush()
            post.media_asset_ids = str(media_asset.id)

        for raw in item.get("platforms", []):
            platform = _PLATFORM_MAP.get(str(raw).lower())
            if platform is None:
                continue
            channel = _get_or_create_channel(db, brand_id, platform)
            db.add(
                PostTarget(
                    post_id=post.id,
                    channel_id=channel.id,
                    media_asset_id=media_asset.id if media_asset else None,
                    status=_QUEUE_STATUS_TO_TARGET.get(
                        q_status, PostTargetStatus.pending
                    ),
                    error=item.get("error"),
                )
            )
        created += 1

    db.commit()
    return created
