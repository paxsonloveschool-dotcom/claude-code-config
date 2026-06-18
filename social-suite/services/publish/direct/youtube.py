"""Direct YouTube Data API v3 — upload a video via ``videos.insert`` (resumable).

No third-party deps: the HTTP helper lazy-imports stdlib ``urllib`` so this
module imports cleanly with no network at import time, matching ``meta.py``.

Auth: a per-channel OAuth 2.0 access token with the
``https://www.googleapis.com/auth/youtube.upload`` scope, sent as
``Authorization: Bearer <token>``.

Approval: YouTube requires OAuth verification + a compliance audit. Until the
audit passes, uploads are forced ``private`` regardless of ``privacy_status``,
and a low daily quota applies (~6 uploads/day). See ``PORTAL_ARCHITECTURE.md``.

Limits: ``title`` ≤ 100 chars, ``description`` ≤ 5000 chars (YouTube rejects
over-length values). We do NOT truncate — the caller fits the text.

Flow (resumable upload):
    1. INITIATE — ``POST .../upload/youtube/v3/videos?uploadType=resumable&part=snippet,status``
       with the snippet/status metadata JSON. YouTube returns a ``Location``
       header: the resumable **upload URL**.
    2. UPLOAD   — ``PUT`` the raw video bytes to that upload URL (single shot or
       chunked with ``Content-Range``). On success YouTube returns the video
       resource JSON with its ``id``.
"""

from __future__ import annotations

import json

INSERT_URL = (
    "https://www.googleapis.com/upload/youtube/v3/videos"
    "?uploadType=resumable&part=snippet,status"
)

TITLE_MAX = 100
DESCRIPTION_MAX = 5000


def _initiate_resumable(
    url: str, token: str, metadata: dict, timeout: float = 60.0
) -> str:
    """POST the metadata to start a resumable upload; return the upload URL.

    Sends the snippet/status JSON with ``X-Upload-Content-Type`` so YouTube
    allocates a session. Reads the ``Location`` response header — the URL the
    video bytes are PUT to. Raises ``RuntimeError`` carrying Google's error body
    on any non-2xx status or connection failure.
    """
    import urllib.error  # lazy, stdlib
    import urllib.request

    data = json.dumps(metadata).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": "video/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            location = resp.headers.get("Location")
            if not location:
                raise RuntimeError(
                    "YouTube resumable initiate returned no Location header."
                )
            return location
    except urllib.error.HTTPError as e:  # non-2xx — surface Google's body
        try:
            err_body = e.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            err_body = ""
        raise RuntimeError(
            f"YouTube videos.insert initiate failed: HTTP {e.code} {e.reason}: {err_body}"
        ) from e
    except urllib.error.URLError as e:  # DNS/connection/timeout
        raise RuntimeError(f"YouTube videos.insert initiate failed: {e.reason}") from e


def post_youtube(
    access_token: str,
    title: str,
    description: str,
    video_path_or_url: str,
    privacy_status: str = "public",
    category_id: str = "22",
) -> dict:
    """Initiate a YouTube ``videos.insert`` resumable upload.

    Builds the snippet/status metadata and performs the **initiate** step,
    returning the resumable upload URL the bytes go to.

    Args:
        access_token: OAuth token with ``youtube.upload``.
        title: Video title (≤ 100 chars).
        description: Video description (≤ 5000 chars).
        video_path_or_url: Local file path or URL to the video bytes. The byte
            ``PUT`` step is stubbed (see TODO) — this returns the upload URL.
        privacy_status: ``"public"`` | ``"unlisted"`` | ``"private"`` (forced
            ``private`` until the channel's compliance audit passes).
        category_id: YouTube category id (default ``"22"`` = People & Blogs).

    Returns:
        ``{"upload_url": <resumable URL>, "video_path_or_url": ...}``. After the
        byte ``PUT`` is implemented this should return the created video resource
        (with its ``id``) instead.
    """
    metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
        },
    }

    upload_url = _initiate_resumable(INSERT_URL, access_token, metadata)

    # TODO(impl): stream the video bytes from ``video_path_or_url`` to
    # ``upload_url`` via an HTTP PUT (single-shot or chunked with Content-Range),
    # then return the parsed video resource JSON (with its ``id``). The byte
    # streaming is environment-specific (needs the real file/stream) and is
    # intentionally left stubbed; the initiate step above is fully implemented.
    return {"upload_url": upload_url, "video_path_or_url": video_path_or_url}
