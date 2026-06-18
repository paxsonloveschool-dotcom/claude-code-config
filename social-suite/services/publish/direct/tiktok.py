"""Direct TikTok Content Posting API — publish a video via PULL_FROM_URL.

No third-party deps: the HTTP helper lazy-imports stdlib ``urllib`` so this
module imports cleanly with no network at import time, matching ``meta.py``.

Auth: a per-creator OAuth access token with ``video.publish`` scope, sent as
``Authorization: Bearer <token>``.

Approval: TikTok requires a one-time Content Posting API audit and a verified
domain for PULL_FROM_URL sources. ``video_url`` must be a PUBLIC URL on a
verified domain — TikTok fetches the bytes server-side (like IG/FB).

Flow (the documented direct-post path):
    1. ``POST /v2/post/publish/creator_info/query/`` — returns the creator's
       allowed privacy levels, duration limits, and interaction toggles. Call
       this first so the chosen ``privacy_level`` is valid for the creator.
    2. ``POST /v2/post/publish/video/init/`` — with ``post_info`` (caption,
       privacy_level, …) and ``source_info`` (PULL_FROM_URL + ``video_url``).
       Returns a ``publish_id``.
    3. ``POST /v2/post/publish/status/fetch/`` — poll with the ``publish_id``
       until ``status`` is ``PUBLISH_COMPLETE`` (or a failure). Documented in
       ``fetch_status`` below; the runner can poll it out-of-band.
"""

from __future__ import annotations

import json

API_BASE = "https://open.tiktokapis.com/v2"
CREATOR_INFO_URL = f"{API_BASE}/post/publish/creator_info/query/"
VIDEO_INIT_URL = f"{API_BASE}/post/publish/video/init/"
STATUS_FETCH_URL = f"{API_BASE}/post/publish/status/fetch/"

# Valid privacy levels (subset returned per-creator by creator_info/query).
PRIVACY_LEVELS = (
    "PUBLIC_TO_EVERYONE",
    "MUTUAL_FOLLOW_FRIENDS",
    "FOLLOWER_OF_CREATOR",
    "SELF_ONLY",
)


def _post_json(url: str, token: str, body: dict, timeout: float = 60.0) -> dict:
    """POST ``body`` as JSON to ``url`` with a Bearer ``token``.

    Lazy-imports urllib (stdlib). Raises ``RuntimeError`` carrying TikTok's error
    body on any non-2xx status, and on connection/timeout failures.
    """
    import urllib.error  # lazy, stdlib
    import urllib.request

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:  # non-2xx — surface TikTok's body
        try:
            err_body = e.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            err_body = ""
        raise RuntimeError(
            f"TikTok API POST {url} failed: HTTP {e.code} {e.reason}: {err_body}"
        ) from e
    except urllib.error.URLError as e:  # DNS/connection/timeout
        raise RuntimeError(f"TikTok API POST {url} failed: {e.reason}") from e
    return json.loads(raw) if raw else {}


def query_creator_info(access_token: str) -> dict:
    """Query the creator's posting capabilities (privacy levels, limits)."""
    return _post_json(CREATOR_INFO_URL, access_token, {})


def fetch_status(access_token: str, publish_id: str) -> dict:
    """Poll publish status for ``publish_id``.

    ``POST /v2/post/publish/status/fetch/`` with ``{"publish_id": ...}``; the
    ``data.status`` field walks ``PROCESSING_UPLOAD`` -> ``PUBLISH_COMPLETE`` (or
    a ``FAILED`` state with ``fail_reason``). The runner polls this out-of-band
    after ``post_tiktok`` returns the ``publish_id``.
    """
    return _post_json(STATUS_FETCH_URL, access_token, {"publish_id": publish_id})


def post_tiktok(
    access_token: str,
    caption: str,
    video_url: str,
    privacy_level: str = "SELF_ONLY",
) -> str:
    """Initiate a direct-post video publish; return the ``publish_id``.

    Calls ``creator_info/query/`` first (validates the creator can post), then
    ``video/init/`` with a PULL_FROM_URL source so TikTok pulls the bytes from
    ``video_url`` server-side.

    Args:
        access_token: OAuth token with ``video.publish``.
        caption: The video caption / description text.
        video_url: PUBLIC video URL on a verified domain (TikTok fetches it).
        privacy_level: One of ``PRIVACY_LEVELS``; defaults to ``"SELF_ONLY"``
            (the only level allowed for unaudited apps in sandbox).

    Returns:
        The ``publish_id`` string — poll ``fetch_status`` with it to confirm.
    """
    if privacy_level not in PRIVACY_LEVELS:
        raise ValueError(
            f"Invalid privacy_level {privacy_level!r}; expected one of {PRIVACY_LEVELS}."
        )

    # Step 1 — confirm the creator can post (and surface their constraints).
    query_creator_info(access_token)

    # Step 2 — initiate the pull-from-url publish.
    body = {
        "post_info": {
            "title": caption,
            "privacy_level": privacy_level,
        },
        "source_info": {
            "source": "PULL_FROM_URL",
            "video_url": video_url,
        },
    }
    resp = _post_json(VIDEO_INIT_URL, access_token, body)
    publish_id = (resp.get("data") or {}).get("publish_id")
    if not publish_id:
        raise RuntimeError(f"TikTok video/init returned no publish_id: {resp!r}")
    return publish_id
