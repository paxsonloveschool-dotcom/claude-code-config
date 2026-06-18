"""Direct Google Business Profile (GBP) — create a local post via the v4 API.

No third-party deps: the HTTP helper lazy-imports stdlib ``urllib`` so this
module imports cleanly with no network at import time, matching ``meta.py``.

Auth: a per-location OAuth 2.0 access token with the
``https://www.googleapis.com/auth/business.manage`` scope, sent as
``Authorization: Bearer <token>``.

Approval: GBP requires an API allowlisting form + OAuth verification (the
slowest queue of the six platforms — submit day one). Local posts are still on
the **v4** endpoint (``mybusiness.googleapis.com/v4``); newer Business Profile
APIs do not yet cover local posts.

Endpoint:
    ``POST https://mybusiness.googleapis.com/v4/accounts/{account_id}/locations/{location_id}/localPosts``
"""

from __future__ import annotations

import json

API_BASE = "https://mybusiness.googleapis.com/v4"

# Default media format for a single image; v4 expects PHOTO/VIDEO.
DEFAULT_MEDIA_FORMAT = "PHOTO"


def _post_json(url: str, token: str, body: dict, timeout: float = 60.0) -> dict:
    """POST ``body`` as JSON to ``url`` with a Bearer ``token``.

    Lazy-imports urllib (stdlib). Raises ``RuntimeError`` carrying Google's error
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
    except urllib.error.HTTPError as e:  # non-2xx — surface Google's body
        try:
            err_body = e.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            err_body = ""
        raise RuntimeError(
            f"GBP API POST {url} failed: HTTP {e.code} {e.reason}: {err_body}"
        ) from e
    except urllib.error.URLError as e:  # DNS/connection/timeout
        raise RuntimeError(f"GBP API POST {url} failed: {e.reason}") from e
    return json.loads(raw) if raw else {}


def post_gbp(
    access_token: str,
    account_id: str,
    location_id: str,
    summary: str,
    media_url: str | None = None,
    cta: dict | None = None,
) -> dict:
    """Create a STANDARD local post on a Google Business Profile location.

    Args:
        access_token: OAuth token with ``business.manage``.
        account_id: GBP account id (the ``accounts/{id}`` segment).
        location_id: GBP location id (the ``locations/{id}`` segment).
        summary: The post body text.
        media_url: Optional PUBLIC media URL — attached as a single PHOTO via
            ``media: [{mediaFormat, sourceUrl}]``.
        cta: Optional call-to-action dict, e.g.
            ``{"actionType": "LEARN_MORE", "url": "https://..."}``, placed under
            ``callToAction``.

    Returns:
        The created ``localPost`` resource dict (e.g. with its ``name``/``state``).
    """
    url = f"{API_BASE}/accounts/{account_id}/locations/{location_id}/localPosts"

    body: dict = {
        "languageCode": "en-US",
        "summary": summary,
        "topicType": "STANDARD",
    }
    if media_url:
        body["media"] = [
            {"mediaFormat": DEFAULT_MEDIA_FORMAT, "sourceUrl": media_url}
        ]
    if cta:
        body["callToAction"] = cta

    return _post_json(url, access_token, body)
