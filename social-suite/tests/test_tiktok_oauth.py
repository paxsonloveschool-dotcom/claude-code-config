"""Tests for the TikTok OAuth linking helper (no network — _post_form mocked)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.publish.direct import tiktok_oauth  # noqa: E402


def test_build_authorize_url_has_required_params():
    url = tiktok_oauth.build_authorize_url(
        "CKEY", "https://site/cb", state="xyz"
    )
    assert url.startswith("https://www.tiktok.com/v2/auth/authorize/?")
    assert "client_key=CKEY" in url
    assert "response_type=code" in url
    assert "scope=user.info.basic%2Cvideo.publish" in url
    assert "redirect_uri=https%3A%2F%2Fsite%2Fcb" in url
    assert "state=xyz" in url


def test_build_authorize_url_requires_client_key_and_redirect():
    for bad in (
        lambda: tiktok_oauth.build_authorize_url("", "https://s/cb"),
        lambda: tiktok_oauth.build_authorize_url("CK", ""),
    ):
        try:
            bad()
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError on missing required arg")


def _patch_post_form(calls, *, returns):
    def _fake(url, form, timeout=30.0):
        calls.append({"url": url, "form": form})
        return returns

    orig = tiktok_oauth._post_form
    tiktok_oauth._post_form = _fake
    return orig


def test_exchange_code_posts_authorization_grant_and_returns_tokens():
    calls: list = []
    orig = _patch_post_form(
        calls,
        returns={"access_token": "act", "refresh_token": "rft", "open_id": "o"},
    )
    try:
        payload = tiktok_oauth.exchange_code("CK", "CS", "THECODE", "https://s/cb")
    finally:
        tiktok_oauth._post_form = orig

    assert payload["refresh_token"] == "rft"
    assert calls[0]["url"] == "https://open.tiktokapis.com/v2/oauth/token/"
    form = calls[0]["form"]
    assert form["grant_type"] == "authorization_code"
    assert form["code"] == "THECODE"
    assert form["client_key"] == "CK"
    assert form["client_secret"] == "CS"
    assert form["redirect_uri"] == "https://s/cb"


def test_refresh_access_token_posts_refresh_grant():
    calls: list = []
    orig = _patch_post_form(
        calls, returns={"access_token": "fresh", "refresh_token": "rotated"}
    )
    try:
        payload = tiktok_oauth.refresh_access_token("CK", "CS", "OLD_RFT")
    finally:
        tiktok_oauth._post_form = orig

    assert payload["access_token"] == "fresh"
    form = calls[0]["form"]
    assert form["grant_type"] == "refresh_token"
    assert form["refresh_token"] == "OLD_RFT"
    assert "code" not in form


def test_oauth_error_in_200_body_raises():
    orig = _patch_post_form(
        [], returns={"error": "invalid_grant", "error_description": "expired"}
    )
    try:
        tiktok_oauth.refresh_access_token("CK", "CS", "RFT")
    except RuntimeError as e:
        assert "invalid_grant" in str(e)
        assert "expired" in str(e)
    else:
        raise AssertionError("expected RuntimeError on OAuth error body")
    finally:
        tiktok_oauth._post_form = orig


def test_exchange_requires_code():
    try:
        tiktok_oauth.exchange_code("CK", "CS", "", "https://s/cb")
    except ValueError as e:
        assert "code" in str(e)
    else:
        raise AssertionError("expected ValueError on empty code")


def test_check_token_ok_when_creator_info_resolves():
    from services.publish.direct import tiktok

    orig = tiktok.query_creator_info
    tiktok.query_creator_info = lambda tok: {
        "data": {"creator_nickname": "me"},
        "error": {"code": "ok"},
    }
    try:
        res = tiktok_oauth.check_token("good")
    finally:
        tiktok.query_creator_info = orig
    assert res["ok"] is True
    assert res["info"]["creator_nickname"] == "me"


def test_check_token_not_ok_on_error_code():
    from services.publish.direct import tiktok

    orig = tiktok.query_creator_info
    tiktok.query_creator_info = lambda tok: {
        "data": {},
        "error": {"code": "access_token_invalid", "message": "bad"},
    }
    try:
        res = tiktok_oauth.check_token("expired")
    finally:
        tiktok.query_creator_info = orig
    assert res["ok"] is False
    assert "access_token_invalid" in res["error"]


def test_check_token_empty_skips_network():
    res = tiktok_oauth.check_token("")
    assert res["ok"] is False
    assert "empty" in res["error"]


def test_post_form_raises_with_body_on_http_error():
    import io
    import urllib.error
    import urllib.request

    def _fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            url=req.full_url, code=400, msg="Bad Request", hdrs=None,
            fp=io.BytesIO(b'{"error":"invalid_request"}'),
        )

    orig = urllib.request.urlopen
    urllib.request.urlopen = _fake_urlopen
    try:
        tiktok_oauth._post_form(tiktok_oauth.TOKEN_URL, {"a": "b"})
    except RuntimeError as e:
        assert "400" in str(e)
        assert "invalid_request" in str(e)
    else:
        raise AssertionError("expected RuntimeError on HTTP 400")
    finally:
        urllib.request.urlopen = orig


def _run():
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  PASS {name}")
            passed += 1
    print(f"\n{passed} tests passed.")


if __name__ == "__main__":
    _run()
