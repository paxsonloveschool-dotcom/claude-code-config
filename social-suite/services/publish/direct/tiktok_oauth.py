"""TikTok OAuth v2 — link an account and keep its token alive.

The posting module (``tiktok.py``) needs a per-creator access token with the
``video.publish`` scope. Unlike a Meta Page token (effectively non-expiring),
a TikTok **access** token lives only ~24h; the **refresh** token lives ~365
days. So for an unattended cron we store the *refresh* token (plus the app's
``client_key`` / ``client_secret``) and mint a fresh access token just-in-time
before each post — mirroring the Dropbox refresh-token flow already used for
ingest.

This module is the "linking" layer:
    1. ``build_authorize_url`` — the URL the account owner visits once to grant
       ``video.publish``. TikTok redirects back to ``redirect_uri?code=...``.
    2. ``exchange_code`` — swap that one-time ``code`` for the first
       ``access_token`` + ``refresh_token`` (run once per account).
    3. ``refresh_access_token`` — swap a stored ``refresh_token`` for a fresh
       ``access_token`` (run by the poster before every post). TikTok rotates
       the refresh token on each call, so the caller should persist the new one.
    4. ``check_token`` — cheapest authenticated call (``creator_info/query``) to
       confirm a token still works, parallel to Meta's ``check_token``.

Pure stdlib (lazy ``urllib``) — imports with no third-party deps and touches the
network only when a function is called.

Docs: https://developers.tiktok.com/doc/oauth-user-access-token-management
"""

from __future__ import annotations

import json

AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"

# Scopes needed to direct-post a video on the creator's behalf.
DEFAULT_SCOPES = ("user.info.basic", "video.publish")


def _post_form(url: str, form: dict, timeout: float = 30.0) -> dict:
    """POST ``form`` as ``application/x-www-form-urlencoded`` and parse JSON.

    The TikTok token endpoint takes form-encoded bodies (not JSON, unlike the
    posting endpoints). Lazy-imports stdlib ``urllib``. Raises ``RuntimeError``
    carrying TikTok's error body on any non-2xx status or connection failure.
    """
    import urllib.error  # lazy, stdlib
    import urllib.parse
    import urllib.request

    data = urllib.parse.urlencode(form).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-cache",
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
            f"TikTok OAuth POST {url} failed: HTTP {e.code} {e.reason}: {err_body}"
        ) from e
    except urllib.error.URLError as e:  # DNS/connection/timeout
        raise RuntimeError(f"TikTok OAuth POST {url} failed: {e.reason}") from e
    return json.loads(raw) if raw else {}


def _raise_for_oauth_error(body: dict, what: str) -> dict:
    """TikTok returns HTTP 200 with an ``error`` field on logical failures."""
    err = body.get("error")
    # The token endpoint uses "" / absent for success; an OAuth error is a
    # non-empty string code (e.g. "invalid_grant").
    if err:
        desc = body.get("error_description") or ""
        raise RuntimeError(f"TikTok {what} failed: {err}: {desc}")
    return body


def build_authorize_url(
    client_key: str,
    redirect_uri: str,
    *,
    scopes: tuple[str, ...] | list[str] = DEFAULT_SCOPES,
    state: str = "",
) -> str:
    """Build the consent URL the account owner visits once to grant access.

    Args:
        client_key: The app's Client Key (developers.tiktok.com → your app).
        redirect_uri: A redirect URI registered on the app EXACTLY as here.
        scopes: Scopes to request; ``video.publish`` is required to post.
        state: Opaque value echoed back on the redirect (CSRF guard).

    Returns:
        The full ``https://www.tiktok.com/v2/auth/authorize/?...`` URL.
    """
    import urllib.parse  # lazy, stdlib

    if not client_key:
        raise ValueError("client_key is required.")
    if not redirect_uri:
        raise ValueError("redirect_uri is required.")

    query = {
        "client_key": client_key,
        "response_type": "code",
        "scope": ",".join(scopes),
        "redirect_uri": redirect_uri,
    }
    if state:
        query["state"] = state
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(query)}"


def exchange_code(
    client_key: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> dict:
    """Exchange a one-time auth ``code`` for the first access + refresh token.

    Run ONCE per account, right after the owner approves the consent screen.

    Returns the parsed token payload, including ``access_token``,
    ``refresh_token``, ``expires_in``, ``refresh_expires_in``, ``open_id`` and
    ``scope``. Store the ``refresh_token`` (+ ``client_key``/``client_secret``)
    for unattended posting.
    """
    if not code:
        raise ValueError("code is required.")
    body = _post_form(
        TOKEN_URL,
        {
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
    )
    return _raise_for_oauth_error(body, "code exchange")


def refresh_access_token(
    client_key: str,
    client_secret: str,
    refresh_token: str,
) -> dict:
    """Swap a stored ``refresh_token`` for a fresh ``access_token``.

    Called by the poster before each post (the access token only lives ~24h).
    TikTok ROTATES the refresh token on each call, so persist the returned
    ``refresh_token`` for next time.

    Returns the parsed token payload (same shape as ``exchange_code``).
    """
    if not refresh_token:
        raise ValueError("refresh_token is required.")
    body = _post_form(
        TOKEN_URL,
        {
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    return _raise_for_oauth_error(body, "token refresh")


def check_token(access_token: str) -> dict:
    """Check whether ``access_token`` can post (cheapest authenticated call).

    Hits ``creator_info/query`` — the same endpoint the poster calls first — so
    a valid result means the token is live and carries the posting scope.

    Returns:
        On success: ``{"ok": True, "info": <creator data dict>}``.
        On failure: ``{"ok": False, "error": <str>}`` — never raises for an
        ordinary auth/HTTP failure; the message suits a log line.
    """
    if not access_token:
        return {"ok": False, "error": "TikTok access token is empty or not set."}
    from services.publish.direct import tiktok  # lazy

    try:
        body = tiktok.query_creator_info(access_token)
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}
    err = body.get("error") or {}
    # creator_info/query returns error.code == "ok" on success.
    code = err.get("code") if isinstance(err, dict) else err
    if code and code != "ok":
        return {"ok": False, "error": f"{code}: {err.get('message', '')}"}
    return {"ok": True, "info": body.get("data") or {}}


def main(argv: list[str] | None = None) -> int:
    """CLI: ``authorize | exchange | refresh | check`` the TikTok OAuth flow."""
    import argparse
    import os

    parser = argparse.ArgumentParser(
        description="TikTok OAuth helper: link an account and refresh its token."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_auth = sub.add_parser("authorize", help="Print the consent URL to visit.")
    p_auth.add_argument("--client-key", default=os.environ.get("TIKTOK_CLIENT_KEY", ""))
    p_auth.add_argument("--redirect-uri", required=True)
    p_auth.add_argument("--scopes", default=",".join(DEFAULT_SCOPES))
    p_auth.add_argument("--state", default="")

    p_ex = sub.add_parser("exchange", help="Exchange a one-time code for tokens.")
    p_ex.add_argument("--client-key", default=os.environ.get("TIKTOK_CLIENT_KEY", ""))
    p_ex.add_argument("--client-secret", default=os.environ.get("TIKTOK_CLIENT_SECRET", ""))
    p_ex.add_argument("--code", required=True)
    p_ex.add_argument("--redirect-uri", required=True)

    p_rf = sub.add_parser("refresh", help="Refresh an access token from a refresh token.")
    p_rf.add_argument("--client-key", default=os.environ.get("TIKTOK_CLIENT_KEY", ""))
    p_rf.add_argument("--client-secret", default=os.environ.get("TIKTOK_CLIENT_SECRET", ""))
    p_rf.add_argument("--refresh-token", default=os.environ.get("TIKTOK_REFRESH_TOKEN", ""))

    p_ck = sub.add_parser("check", help="Verify an access token can post.")
    p_ck.add_argument("--access-token", default=os.environ.get("TIKTOK_ACCESS_TOKEN", ""))

    args = parser.parse_args(argv)

    if args.cmd == "authorize":
        scopes = tuple(s.strip() for s in args.scopes.split(",") if s.strip())
        print(
            build_authorize_url(
                args.client_key, args.redirect_uri, scopes=scopes, state=args.state
            )
        )
        return 0

    if args.cmd == "exchange":
        payload = exchange_code(
            args.client_key, args.client_secret, args.code, args.redirect_uri
        )
        print(json.dumps(payload, indent=2))
        return 0

    if args.cmd == "refresh":
        payload = refresh_access_token(
            args.client_key, args.client_secret, args.refresh_token
        )
        print(json.dumps(payload, indent=2))
        return 0

    if args.cmd == "check":
        result = check_token(args.access_token)
        if result["ok"]:
            print("TikTok access token OK — creator info reachable, posting scope present.")
            return 0
        print(f"TikTok access token INVALID — {result['error']}")
        print(
            "Refresh it from the stored refresh token, or re-link the account "
            "(see social-suite/TIKTOK_SETUP.md)."
        )
        return 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
