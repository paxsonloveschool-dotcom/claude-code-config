"""Direct X (Twitter) API v2 posting — create a Tweet via ``api.x.com``.

No third-party deps: the HTTP helper lazy-imports stdlib ``urllib`` so this
module imports cleanly with no network at import time, matching ``meta.py``.

Auth: a per-user OAuth 2.0 **Bearer** access token with ``tweet.write`` scope,
sent as ``Authorization: Bearer <token>``. (X also supports OAuth 1.0a user
context; we standardize on OAuth 2.0 bearer here.)

Cost note: X's posting API is metered/paid (roughly $0.015/post, more for
link-posts) — see ``PORTAL_ARCHITECTURE.md``. No app-review gate, but billing
applies per call.

Char limit: standard Tweets are **280 characters**. We do NOT truncate here —
the caller (``adapt()``) is responsible for fitting text to the limit; an
over-length body is rejected by X and surfaced as a ``RuntimeError``.
"""

from __future__ import annotations

import json

API_BASE = "https://api.x.com/2"
TWEETS_URL = f"{API_BASE}/tweets"
MEDIA_UPLOAD_URL = f"{API_BASE}/media/upload"

TWEET_CHAR_LIMIT = 280


def _post_json(url: str, token: str, body: dict, timeout: float = 60.0) -> dict:
    """POST ``body`` as JSON to ``url`` with a Bearer ``token``.

    Lazy-imports urllib (stdlib). Raises ``RuntimeError`` carrying X's error body
    on any non-2xx status, and on connection/timeout failures, so the caller sees
    X's actual error message.
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
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:  # non-2xx — surface X's body
        try:
            err_body = e.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            err_body = ""
        raise RuntimeError(
            f"X API POST {url} failed: HTTP {e.code} {e.reason}: {err_body}"
        ) from e
    except urllib.error.URLError as e:  # DNS/connection/timeout
        raise RuntimeError(f"X API POST {url} failed: {e.reason}") from e
    return json.loads(raw) if raw else {}


def upload_media(media_url: str, access_token: str) -> str:
    """Upload one media file to X and return its ``media_id_string``.

    X media upload is a **chunked** flow at ``POST /2/media/upload``:

    1. ``INIT``     — declare ``total_bytes`` + ``media_type``; X returns a media id.
    2. ``APPEND``   — upload the raw bytes in ordered chunks (``segment_index``).
    3. ``FINALIZE`` — finish; for video, poll ``processing_info`` until ``succeeded``.

    The Tweet-create call then references the returned id(s) in
    ``media.media_ids``.

    NOTE: the actual byte upload requires reading the real media file and a
    multipart ``APPEND`` per chunk — that is environment-specific (needs the file
    bytes) and is intentionally left as a clear stub below. The Tweet-create path
    (``post_x``) is fully implemented and tested.
    """
    # TODO(impl): fetch ``media_url`` bytes, then run the INIT/APPEND/FINALIZE
    # chunked upload against MEDIA_UPLOAD_URL and return the real media_id_string.
    # INIT:     command=INIT, total_bytes, media_type  -> {"data": {"id": ...}}
    # APPEND:   command=APPEND, media_id, segment_index, media (chunk bytes)
    # FINALIZE: command=FINALIZE, media_id -> poll processing_info for video.
    raise NotImplementedError(
        "X chunked media byte-upload is not implemented in this environment. "
        "Implement INIT/APPEND/FINALIZE against MEDIA_UPLOAD_URL to attach media."
    )


def post_x(
    text: str,
    access_token: str,
    media_urls: list[str] | None = None,
) -> dict:
    """Create a Tweet via ``POST https://api.x.com/2/tweets``.

    Args:
        text: The Tweet body. X enforces a **280-character** limit on standard
            Tweets; this function does not truncate.
        access_token: OAuth 2.0 user Bearer token with ``tweet.write``.
        media_urls: Optional list of media to attach. Each is uploaded via the
            chunked ``/2/media/upload`` flow (see ``upload_media``) and its
            returned id is placed in ``media.media_ids``.

    Returns:
        The X API response dict, e.g.
        ``{"data": {"id": "<tweet-id>", "text": "..."}}``.
    """
    body: dict = {"text": text}
    if media_urls:
        media_ids = [upload_media(u, access_token) for u in media_urls]
        body["media"] = {"media_ids": media_ids}
    return _post_json(TWEETS_URL, access_token, body)
