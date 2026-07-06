"""Direct Meta Graph API posting for Facebook Pages and Instagram.

No Postiz, no server — these call ``graph.facebook.com`` directly so a GitHub
Actions cron job can publish on a schedule. Both functions lazy-import
``urllib`` (stdlib) inside the HTTP helper, so this module imports with no
third-party deps and touches the network only when a poster is actually called.

Auth: a single long-lived Meta user/page access token (``access_token``) with
the ``pages_manage_posts`` / ``instagram_content_publish`` permissions. The same
token drives both the FB Page and the IG Professional account linked to it.

Facebook supports server-side scheduling; Instagram does NOT (see
``post_instagram``).
"""

from __future__ import annotations

import json

GRAPH_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


def _post_form(url: str, params: dict, timeout: float = 60.0) -> dict:
    """POST ``params`` as ``application/x-www-form-urlencoded`` to ``url``.

    Lazy-imports urllib (stdlib). Raises ``RuntimeError`` carrying the Graph API
    error body on any non-2xx status, and on connection/timeout failures, so the
    caller sees Meta's actual error message.
    """
    import urllib.error  # lazy, stdlib
    import urllib.parse
    import urllib.request

    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:  # non-2xx — surface Graph's body
        try:
            err_body = e.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            err_body = ""
        raise RuntimeError(
            f"Meta Graph POST {url} failed: HTTP {e.code} {e.reason}: {err_body}"
        ) from e
    except urllib.error.URLError as e:  # DNS/connection/timeout
        raise RuntimeError(f"Meta Graph POST {url} failed: {e.reason}") from e
    return json.loads(raw) if raw else {}


def post_facebook(
    page_id: str,
    access_token: str,
    message: str,
    link: str | None = None,
    image_url: str | None = None,
    scheduled_time: int | None = None,
) -> dict:
    """Post to a Facebook Page feed (or as a photo when ``image_url`` is given).

    Args:
        page_id: The Facebook Page id to post to.
        access_token: Page access token with ``pages_manage_posts``.
        message: The post text / photo caption.
        link: Optional URL to attach (feed posts only; ignored for photos).
        image_url: Optional PUBLIC image URL. When set, posts to ``/photos``
            instead of ``/feed``.
        scheduled_time: Optional unix timestamp (seconds, UTC) for server-side
            scheduling. When set, the post is created unpublished
            (``published=false``) with ``scheduled_publish_time`` so Facebook
            publishes it later — no need to keep this process running.

    Returns:
        The Graph API response dict (e.g. ``{"id": "<post-id>"}``).
    """
    edge = "photos" if image_url else "feed"
    url = f"{GRAPH_BASE}/{page_id}/{edge}"

    params: dict = {"access_token": access_token}
    if image_url:
        params["url"] = image_url
        if message:
            params["caption"] = message
    else:
        params["message"] = message
        if link:
            params["link"] = link

    if scheduled_time is not None:
        params["published"] = "false"
        params["scheduled_publish_time"] = str(int(scheduled_time))

    return _post_form(url, params)


def post_facebook_video(
    page_id: str,
    access_token: str,
    message: str,
    video_url: str,
    scheduled_time: int | None = None,
) -> dict:
    """Post a native video to a Facebook Page (keeps the video's own audio).

    Uploads to the Page's ``/videos`` edge via ``file_url`` (Meta fetches the
    bytes server-side, so a public URL — e.g. a Dropbox ``raw=1`` link — works and
    the process needn't stay running). The video plays with its own audio track
    (outro/native sound); no library music is added (a Page can't).

    Args:
        page_id: The Facebook Page id.
        access_token: Page access token with ``pages_manage_posts``.
        message: Caption / description.
        video_url: PUBLIC video URL Meta can fetch.
        scheduled_time: Optional unix timestamp (seconds, UTC). When set, the
            video is created unpublished with ``scheduled_publish_time`` so
            Facebook publishes it later (must be 10 min–30 days out).

    Returns:
        The Graph API response dict (e.g. ``{"id": "<video-id>"}``).
    """
    url = f"{GRAPH_BASE}/{page_id}/videos"
    params: dict = {
        "access_token": access_token,
        "file_url": video_url,
        "description": message,
    }
    if scheduled_time is not None:
        params["published"] = "false"
        params["scheduled_publish_time"] = str(int(scheduled_time))
    return _post_form(url, params)


def post_instagram(
    ig_user_id: str,
    access_token: str,
    caption: str,
    image_url: str | None = None,
    video_url: str | None = None,
) -> dict:
    """Publish an Instagram post via the 2-step Content Publishing flow.

    Step 1: ``POST /{ig_user_id}/media`` with the media URL + caption to create a
    media *container* (returns a ``creation_id``).
    Step 2: ``POST /{ig_user_id}/media_publish`` with that ``creation_id`` to
    actually publish it.

    IMPORTANT: Instagram requires a **PUBLIC media URL** (``image_url`` or
    ``video_url``) — Meta fetches it server-side, so a localhost/private path
    will fail. The IG Graph API has **no scheduling** parameter: this publishes
    immediately at call time. To schedule IG, run this poster at the desired
    time (e.g. via the GitHub Actions cron).

    Args:
        ig_user_id: The Instagram Professional account user id.
        access_token: Token with ``instagram_content_publish``.
        caption: The post caption (text + hashtags).
        image_url: Public image URL for a photo post.
        video_url: Public video URL for a Reel (sets ``media_type=REELS``).

    Returns:
        The ``media_publish`` response dict (e.g. ``{"id": "<media-id>"}``).
    """
    if not image_url and not video_url:
        raise ValueError("post_instagram requires a public image_url or video_url.")

    # Step 1 — create the media container.
    create_params: dict = {"access_token": access_token, "caption": caption}
    if video_url:
        create_params["video_url"] = video_url
        create_params["media_type"] = "REELS"
    else:
        create_params["image_url"] = image_url

    create_url = f"{GRAPH_BASE}/{ig_user_id}/media"
    container = _post_form(create_url, create_params)
    creation_id = container.get("id")
    if not creation_id:
        raise RuntimeError(
            f"Instagram media container creation returned no id: {container!r}"
        )

    # Step 2 — publish the container.
    publish_url = f"{GRAPH_BASE}/{ig_user_id}/media_publish"
    publish_params = {"access_token": access_token, "creation_id": creation_id}
    return _post_form(publish_url, publish_params)
