"""Schedule/post a finished clip via the Postiz public API.

Pushes a captioned clip + AI copy to one or more social channels through a Postiz
instance, optionally scheduled for a future time.

TODO(impl): fill in against the Postiz public API.
    - Endpoint: POST {POSTIZ_API_URL}/public/v1/posts
    - Auth: API key header (e.g. `Authorization: <POSTIZ_API_KEY>`) — confirm the
      exact header for your Postiz version.
    - The clip media is uploaded to Postiz first (its upload endpoint), then
      referenced by the post payload; channels come from POSTIZ_DEFAULT_CHANNELS
      unless overridden.
    - Use httpx for the request.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ScheduledPost:
    """Result of scheduling/posting via Postiz.

    Attributes:
        post_id: Postiz post id (empty until created).
        channels: Channel/integration ids the post targets.
        scheduled_for: When the post is scheduled (None = post now).
        status: Postiz status, e.g. "scheduled" | "posted" | "error".
    """

    post_id: str = ""
    channels: list[str] = field(default_factory=list)
    scheduled_for: datetime | None = None
    status: str = "pending"


def schedule_post(
    clip_path: str,
    caption: str,
    channels: list[str] | None = None,
    when: datetime | None = None,
) -> ScheduledPost:
    """Schedule or immediately post a clip to social channels.

    Args:
        clip_path: Path to the captioned video to publish.
        caption: Caption text (hook + body + hashtags, already composed).
        channels: Postiz channel ids; defaults to POSTIZ_DEFAULT_CHANNELS.
        when: Schedule time; None posts immediately.

    Returns:
        A ``ScheduledPost`` describing the created post.

    TODO(impl): Postiz public API — upload media, then POST /public/v1/posts.
    """
    _ = os.getenv("POSTIZ_API_URL")
    _ = os.getenv("POSTIZ_API_KEY")
    if channels is None:
        raw = os.getenv("POSTIZ_DEFAULT_CHANNELS", "")
        channels = [c.strip() for c in raw.split(",") if c.strip()]
    raise NotImplementedError("Call Postiz public API: POST /public/v1/posts.")
