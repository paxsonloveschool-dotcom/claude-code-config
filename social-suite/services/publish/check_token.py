"""Meta access-token health check — fail loud before we ever try to post.

A long-lived Meta Page token is "effectively non-expiring," but it can still be
revoked, have its password changed underneath it, or lose a permission. This
module hits the cheapest authenticated Graph endpoint (``GET /me``) to confirm
the token still resolves to an account, so a broken/expired token fails the
GitHub Actions run *loudly and early* instead of silently skipping posts.

Lazy-imports ``urllib`` (stdlib) inside the HTTP helper, so importing this module
pulls in no third-party deps and touches the network only when called.

CLI: reads ``META_ACCESS_TOKEN`` from the environment, exits 0 if the token is
valid, 1 otherwise with a clear message. Use ``--quiet`` to suppress the
success line (errors still print).
"""

from __future__ import annotations

import json

GRAPH_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"


def _get_json(url: str, timeout: float = 30.0) -> dict:
    """GET ``url`` and return the parsed JSON body.

    Lazy-imports urllib (stdlib). Raises ``RuntimeError`` carrying the Graph API
    error body on any non-2xx status, and on connection/timeout failures, so the
    caller sees Meta's actual error message.
    """
    import urllib.error  # lazy, stdlib
    import urllib.request

    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:  # non-2xx — surface Graph's body
        try:
            err_body = e.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            err_body = ""
        raise RuntimeError(
            f"Meta Graph GET {url} failed: HTTP {e.code} {e.reason}: {err_body}"
        ) from e
    except urllib.error.URLError as e:  # DNS/connection/timeout
        raise RuntimeError(f"Meta Graph GET {url} failed: {e.reason}") from e
    return json.loads(raw) if raw else {}


def check_token(access_token: str) -> dict:
    """Check whether ``access_token`` is a valid Meta Graph token.

    Calls ``GET /me?fields=id,name`` (the page/user the token belongs to).

    Returns:
        On success: ``{"ok": True, "id": <str>, "name": <str|None>}``.
        On failure: ``{"ok": False, "error": <str>}`` — never raises for an
        ordinary auth/HTTP failure; the message is suitable for a log line.
    """
    if not access_token:
        return {"ok": False, "error": "META_ACCESS_TOKEN is empty or not set."}

    import urllib.parse  # lazy, stdlib

    query = urllib.parse.urlencode({"fields": "id,name", "access_token": access_token})
    url = f"{GRAPH_BASE}/me?{query}"
    try:
        body = _get_json(url)
    except RuntimeError as e:
        return {"ok": False, "error": str(e)}

    account_id = body.get("id")
    if not account_id:
        return {"ok": False, "error": f"/me returned no id: {body!r}"}
    return {"ok": True, "id": account_id, "name": body.get("name")}


def main(argv: list[str] | None = None) -> int:
    import argparse
    import os

    parser = argparse.ArgumentParser(
        description="Check the META_ACCESS_TOKEN is valid (exit 0=ok, 1=bad)."
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the success line (errors still print).",
    )
    args = parser.parse_args(argv)

    token = os.environ.get("META_ACCESS_TOKEN", "")
    result = check_token(token)

    if result["ok"]:
        if not args.quiet:
            who = result.get("name") or result["id"]
            print(f"META_ACCESS_TOKEN OK — resolves to {who} (id {result['id']}).")
        return 0

    print(f"META_ACCESS_TOKEN INVALID — {result['error']}")
    print(
        "Generate a fresh non-expiring Page token "
        "(see social-suite/META_SETUP.md) and update the META_ACCESS_TOKEN secret."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
