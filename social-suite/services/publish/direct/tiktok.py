"""Direct TikTok Content Posting API — publish a video via FILE_UPLOAD.

No third-party deps: the HTTP helpers lazy-import stdlib ``urllib`` so this
module imports cleanly with no network at import time, matching ``meta.py``.

Auth: a per-creator OAuth access token with ``video.publish`` scope, sent as
``Authorization: Bearer <token>``.

Why FILE_UPLOAD (not PULL_FROM_URL): FILE_UPLOAD streams the video bytes straight
to TikTok, so there is **no need for a public host or a verified domain** — which
keeps the whole pipeline $0 and works with a clip sitting on local disk. Default
privacy is ``SELF_ONLY`` (private): nothing is public, and ``SELF_ONLY`` is the
only level an unaudited app can post anyway.

Flow (the documented direct-post path):
    1. ``POST /v2/post/publish/creator_info/query/`` — validates the token can
       post and surfaces the creator's allowed privacy levels / limits.
    2. ``POST /v2/post/publish/video/init/`` — with ``post_info`` (caption,
       privacy_level) and ``source_info`` (FILE_UPLOAD + ``video_size`` +
       ``chunk_size`` + ``total_chunk_count``). Returns ``publish_id`` and a
       one-time ``upload_url``.
    3. ``PUT <upload_url>`` — upload the raw bytes with a ``Content-Range`` header.
    4. ``POST /v2/post/publish/status/fetch/`` — poll with the ``publish_id``
       until ``status`` is ``PUBLISH_COMPLETE`` (or a failure). ``fetch_status``
       below; the runner can poll it out-of-band.
"""

from __future__ import annotations

import json

API_BASE = "https://open.tiktokapis.com/v2"
CREATOR_INFO_URL = f"{API_BASE}/post/publish/creator_info/query/"
VIDEO_INIT_URL = f"{API_BASE}/post/publish/video/init/"
# "Upload to TikTok" (inbox draft): lands the video in the creator's TikTok app
# as a notification/draft for them to finish (add a sound, caption) and post by
# hand. Needs the ``video.upload`` scope — NOT ``video.publish`` — and requires
# NO audit and NO public/private restriction (nothing is posted by the API).
INBOX_VIDEO_INIT_URL = f"{API_BASE}/post/publish/inbox/video/init/"
STATUS_FETCH_URL = f"{API_BASE}/post/publish/status/fetch/"

# Valid privacy levels (subset returned per-creator by creator_info/query).
PRIVACY_LEVELS = (
    "PUBLIC_TO_EVERYONE",
    "MUTUAL_FOLLOW_FRIENDS",
    "FOLLOWER_OF_CREATOR",
    "SELF_ONLY",
)

# TikTok allows the whole file as a single chunk only up to 64 MB; above that a
# multi-chunk (5–64 MB/chunk) upload is required, which we don't implement —
# clips from this pipeline are short and well under the limit.
MAX_SINGLE_CHUNK_BYTES = 64 * 1024 * 1024


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


def _put_file(upload_url: str, path: str, size: int, timeout: float = 300.0) -> int:
    """Upload the whole file as a single chunk to TikTok's ``upload_url``.

    PUTs the raw bytes with the ``Content-Range``/``Content-Length`` headers
    TikTok requires. Raises ``RuntimeError`` on any non-2xx or connection error.
    """
    import urllib.error  # lazy, stdlib
    import urllib.request

    with open(path, "rb") as f:
        data = f.read()
    req = urllib.request.Request(
        upload_url,
        data=data,
        method="PUT",
        headers={
            "Content-Type": "video/mp4",
            "Content-Length": str(size),
            "Content-Range": f"bytes 0-{size - 1}/{size}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return getattr(resp, "status", 0) or resp.getcode()
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            err_body = ""
        raise RuntimeError(
            f"TikTok upload PUT failed: HTTP {e.code} {e.reason}: {err_body}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"TikTok upload PUT failed: {e.reason}") from e


def _ensure_local(video: str) -> tuple[str, bool]:
    """Resolve ``video`` to a local file path, returning ``(path, is_temp)``.

    A local path is used as-is. An ``http(s)`` URL is downloaded to a temp file
    (so a clip hosted anywhere still works) and ``is_temp`` is True so the caller
    deletes it after upload. Anything else raises.
    """
    import os

    if os.path.exists(video):
        return video, False
    if video.startswith(("http://", "https://")):
        import tempfile  # lazy, stdlib
        import urllib.request

        fd, tmp = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        try:
            urllib.request.urlretrieve(video, tmp)  # noqa: S310
        except Exception as e:  # noqa: BLE001 — clean up the temp file on failure
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise RuntimeError(f"TikTok: failed to download {video!r}: {e}") from e
        return tmp, True
    raise RuntimeError(f"TikTok: video {video!r} is not a local file or http(s) URL.")


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


def upload_to_inbox(access_token: str, video: str) -> str:
    """Send a video to the creator's TikTok inbox/drafts; return the ``publish_id``.

    This is the "Upload to TikTok" flow (``video.upload`` scope). Unlike
    ``post_tiktok`` it does NOT post anything — the video shows up in the creator's
    TikTok app as a notification/draft, and THEY finish it (add a trending sound,
    tweak the caption) and hit Post by hand. So it needs no audit, no public/
    private constraint, and lets the owner add a real TikTok song the API can't.

    Uploads via FILE_UPLOAD (streams the bytes — no public host / verified domain),
    accepting a local path or an ``http(s)`` URL (downloaded first), mirroring
    ``post_tiktok``.

    Args:
        access_token: OAuth token carrying the ``video.upload`` scope.
        video: A LOCAL video file path, or an ``http(s)`` URL (downloaded first).

    Returns:
        The ``publish_id`` string — poll ``fetch_status`` with it; the status walks
        to ``SEND_TO_USER_INBOX`` once it's waiting in the creator's TikTok app.
    """
    import os

    path, is_temp = _ensure_local(video)
    try:
        size = os.path.getsize(path)
        if size <= 0:
            raise RuntimeError(f"TikTok: video {video!r} is empty.")
        if size > MAX_SINGLE_CHUNK_BYTES:
            raise RuntimeError(
                f"TikTok: video is {size} bytes (> 64 MB single-chunk limit); "
                "chunked upload is not implemented."
            )

        # Inbox init takes ONLY source_info — no post_info (the creator sets the
        # caption/privacy/sound themselves in the app).
        init_body = {
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": size,
                "total_chunk_count": 1,
            },
        }
        resp = _post_json(INBOX_VIDEO_INIT_URL, access_token, init_body)
        data = resp.get("data") or {}
        publish_id = data.get("publish_id")
        upload_url = data.get("upload_url")
        if not publish_id or not upload_url:
            raise RuntimeError(
                f"TikTok inbox/video/init returned no publish_id/upload_url: {resp!r}"
            )

        _put_file(upload_url, path, size)
        return publish_id
    finally:
        if is_temp:
            try:
                os.remove(path)
            except OSError:
                pass


def post_tiktok(
    access_token: str,
    caption: str,
    video: str,
    privacy_level: str = "SELF_ONLY",
) -> str:
    """Direct-post a video via FILE_UPLOAD; return the ``publish_id``.

    Validates the creator (``creator_info/query``), inits a FILE_UPLOAD publish,
    then PUTs the bytes to the returned ``upload_url``.

    Args:
        access_token: OAuth token with ``video.publish``.
        caption: The video caption / description text.
        video: A LOCAL video file path, or an ``http(s)`` URL (downloaded first).
            The bytes are uploaded directly — no public host / verified domain.
        privacy_level: One of ``PRIVACY_LEVELS``; defaults to ``"SELF_ONLY"``
            (private — the only level an unaudited app can use, and what keeps
            test posts non-public).

    Returns:
        The ``publish_id`` string — poll ``fetch_status`` with it to confirm.
    """
    if privacy_level not in PRIVACY_LEVELS:
        raise ValueError(
            f"Invalid privacy_level {privacy_level!r}; expected one of {PRIVACY_LEVELS}."
        )

    import os

    path, is_temp = _ensure_local(video)
    try:
        size = os.path.getsize(path)
        if size <= 0:
            raise RuntimeError(f"TikTok: video {video!r} is empty.")
        if size > MAX_SINGLE_CHUNK_BYTES:
            raise RuntimeError(
                f"TikTok: video is {size} bytes (> 64 MB single-chunk limit); "
                "chunked upload is not implemented."
            )

        # Step 1 — confirm the creator can post (and surface their constraints).
        query_creator_info(access_token)

        # Step 2 — init a FILE_UPLOAD publish (whole file as one chunk).
        init_body = {
            "post_info": {
                "title": caption,
                "privacy_level": privacy_level,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": size,
                "chunk_size": size,
                "total_chunk_count": 1,
            },
        }
        resp = _post_json(VIDEO_INIT_URL, access_token, init_body)
        data = resp.get("data") or {}
        publish_id = data.get("publish_id")
        upload_url = data.get("upload_url")
        if not publish_id or not upload_url:
            raise RuntimeError(
                f"TikTok video/init returned no publish_id/upload_url: {resp!r}"
            )

        # Step 3 — upload the bytes.
        _put_file(upload_url, path, size)
        return publish_id
    finally:
        if is_temp:
            try:
                os.remove(path)
            except OSError:
                pass
