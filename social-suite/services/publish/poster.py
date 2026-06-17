"""Schedule/post a finished clip via the Postiz public API.

Pushes a captioned clip + AI copy to one or more social channels through a Postiz
instance, optionally scheduled for a future time.

Postiz public API (per RESEARCH.md):
    - Endpoint: ``POST {POSTIZ_API_URL}/public/v1/posts``
    - Auth header: ``Authorization: <api-key>`` (raw key, NO ``Bearer`` prefix).
    - Body: ``type`` (``now|schedule|draft``), ``date`` (ISO-8601), and a
      ``posts[]`` array with one entry per channel:
        {"integration": {"id": <channel-id>},
         "value": [{"content": <caption>}],
         "settings": {"__type": <platform>}}
      where ``__type`` is one of instagram|facebook|tiktok|youtube|x|linkedin.

The HTTP layer uses the stdlib (``urllib``) so this module needs no third-party
dependency. ``build_payload`` is a pure function; ``schedule_post`` supports a
``dry_run`` path that returns the payload without sending anything.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

# Platform ids accepted by Postiz's ``settings.__type``.
VALID_PLATFORMS = {"instagram", "facebook", "tiktok", "youtube", "x", "linkedin"}


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


def _resolve_channels(channels: list[str] | None) -> list[str]:
    """Fall back to POSTIZ_DEFAULT_CHANNELS when no channels are given."""
    if channels:
        return list(channels)
    raw = os.getenv("POSTIZ_DEFAULT_CHANNELS", "")
    return [c.strip() for c in raw.split(",") if c.strip()]


def _iso(when: datetime | None) -> str:
    """ISO-8601 timestamp; uses now (UTC) when ``when`` is None."""
    dt = when or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def build_payload(
    caption: str,
    channels: list[str],
    *,
    when: datetime | None = None,
    media_urls: list[str] | None = None,
    platforms: dict[str, str] | None = None,
    default_platform: str = "instagram",
) -> dict:
    """Build the Postiz ``POST /public/v1/posts`` request body.

    Pure function — no env reads, no I/O.

    Args:
        caption: Composed caption text (hook + body + hashtags).
        channels: Postiz integration (channel) ids; one ``posts[]`` entry each.
        when: Schedule time. None => ``type`` is "now"; otherwise "schedule".
        media_urls: Optional already-uploaded media URLs to attach per channel.
        platforms: Optional {channel_id: platform} map for ``settings.__type``.
            Channels not present use ``default_platform``.
        default_platform: ``__type`` for channels missing from ``platforms``.

    Returns:
        A JSON-serializable dict ready to POST.
    """
    platforms = platforms or {}
    media = [{"path": u} for u in (media_urls or [])]

    posts = []
    for cid in channels:
        platform = platforms.get(cid, default_platform)
        if platform not in VALID_PLATFORMS:
            raise ValueError(
                f"Invalid platform '{platform}' for channel '{cid}'; "
                f"must be one of {sorted(VALID_PLATFORMS)}."
            )
        value_entry: dict = {"content": caption}
        if media:
            value_entry["image"] = media
        posts.append(
            {
                "integration": {"id": cid},
                "value": [value_entry],
                "settings": {"__type": platform},
            }
        )

    return {
        "type": "now" if when is None else "schedule",
        "date": _iso(when),
        "posts": posts,
    }


def _post_json(url: str, body: dict, api_key: str) -> dict:
    """POST ``body`` as JSON to ``url`` with the raw Postiz auth header."""
    import urllib.error  # lazy, stdlib
    import urllib.request

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": api_key,  # raw key, no "Bearer"
        },
    )
    with urllib.request.urlopen(req) as resp:  # noqa: S310 (trusted self-hosted URL)
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def schedule_post(
    clip_path: str,
    caption: str,
    channels: list[str] | None = None,
    when: datetime | None = None,
    *,
    media_urls: list[str] | None = None,
    platforms: dict[str, str] | None = None,
    default_platform: str = "instagram",
    dry_run: bool = False,
) -> ScheduledPost:
    """Schedule or immediately post a clip to social channels.

    Args:
        clip_path: Path to the captioned video to publish (for reference/logging).
        caption: Caption text (hook + body + hashtags, already composed).
        channels: Postiz channel ids; defaults to POSTIZ_DEFAULT_CHANNELS.
        when: Schedule time; None posts immediately ("now").
        media_urls: Optional already-uploaded media URLs to attach.
        platforms: Optional {channel_id: platform} map for ``settings.__type``.
        default_platform: Platform ``__type`` for channels not in ``platforms``.
        dry_run: If True, build and return the payload without sending anything.

    Returns:
        A ``ScheduledPost`` describing the created (or would-be) post.
    """
    resolved = _resolve_channels(channels)
    payload = build_payload(
        caption,
        resolved,
        when=when,
        media_urls=media_urls,
        platforms=platforms,
        default_platform=default_platform,
    )

    if dry_run:
        return ScheduledPost(
            post_id="",
            channels=resolved,
            scheduled_for=when,
            status="dry-run",
        )

    api_url = os.getenv("POSTIZ_API_URL", "").rstrip("/")
    api_key = os.getenv("POSTIZ_API_KEY", "")
    if not api_url or not api_key:
        raise RuntimeError("POSTIZ_API_URL and POSTIZ_API_KEY must be set.")

    url = f"{api_url}/public/v1/posts"
    result = _post_json(url, payload, api_key)

    post_id = str(result.get("id") or result.get("postId") or "")
    return ScheduledPost(
        post_id=post_id,
        channels=resolved,
        scheduled_for=when,
        status="scheduled" if when is not None else "posted",
    )


def _main(argv: list[str] | None = None) -> int:
    """CLI: build a payload (and --dry-run prints it without sending)."""
    import argparse

    parser = argparse.ArgumentParser(description="Post a clip via Postiz.")
    parser.add_argument("clip_path")
    parser.add_argument("caption")
    parser.add_argument("--channels", default="", help="comma-separated channel ids")
    parser.add_argument("--platform", default="instagram")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    channels = [c.strip() for c in args.channels.split(",") if c.strip()] or None
    result = schedule_post(
        args.clip_path,
        args.caption,
        channels=channels,
        default_platform=args.platform,
        dry_run=args.dry_run,
    )
    print(json.dumps(result.__dict__, default=str, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
