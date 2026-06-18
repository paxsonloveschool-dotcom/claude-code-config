"""Tests for the Meta token health check (no network — _get_json mocked)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.publish import check_token  # noqa: E402


def test_valid_token_returns_ok_with_id():
    orig = check_token._get_json
    check_token._get_json = lambda url, timeout=30.0: {"id": "123", "name": "My Page"}
    try:
        res = check_token.check_token("good-token")
    finally:
        check_token._get_json = orig

    assert res["ok"] is True
    assert res["id"] == "123"
    assert res["name"] == "My Page"


def test_valid_token_url_carries_token_and_fields():
    seen: dict = {}

    def _fake(url, timeout=30.0):
        seen["url"] = url
        return {"id": "999"}

    orig = check_token._get_json
    check_token._get_json = _fake
    try:
        res = check_token.check_token("tok-abc")
    finally:
        check_token._get_json = orig

    assert res["ok"] is True
    assert seen["url"].startswith("https://graph.facebook.com/v21.0/me?")
    assert "access_token=tok-abc" in seen["url"]
    assert "fields=id%2Cname" in seen["url"]


def test_http_error_returns_not_ok_with_message():
    def _boom(url, timeout=30.0):
        raise RuntimeError(
            "Meta Graph GET .../me failed: HTTP 400 Bad Request: "
            '{"error":{"message":"Invalid OAuth access token."}}'
        )

    orig = check_token._get_json
    check_token._get_json = _boom
    try:
        res = check_token.check_token("expired-token")
    finally:
        check_token._get_json = orig

    assert res["ok"] is False
    assert "Invalid OAuth access token" in res["error"]
    assert "400" in res["error"]


def test_empty_token_returns_not_ok_without_calling_network():
    called = {"n": 0}

    def _should_not_run(url, timeout=30.0):
        called["n"] += 1
        return {"id": "x"}

    orig = check_token._get_json
    check_token._get_json = _should_not_run
    try:
        res = check_token.check_token("")
    finally:
        check_token._get_json = orig

    assert res["ok"] is False
    assert "META_ACCESS_TOKEN" in res["error"]
    assert called["n"] == 0  # never hit the network for an empty token


def test_missing_id_in_response_is_not_ok():
    orig = check_token._get_json
    check_token._get_json = lambda url, timeout=30.0: {"name": "no id here"}
    try:
        res = check_token.check_token("weird-token")
    finally:
        check_token._get_json = orig

    assert res["ok"] is False
    assert "no id" in res["error"]


def test_get_json_raises_with_body_on_http_error():
    import io
    import urllib.error
    import urllib.request

    def _fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            url=req.full_url,
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"error":{"message":"Invalid OAuth access token."}}'),
        )

    orig = urllib.request.urlopen
    urllib.request.urlopen = _fake_urlopen
    try:
        check_token._get_json("https://graph.facebook.com/v21.0/me?x=1")
    except RuntimeError as e:
        assert "400" in str(e)
        assert "Invalid OAuth access token" in str(e)
    else:
        raise AssertionError("expected RuntimeError on HTTP 400")
    finally:
        urllib.request.urlopen = orig


def test_main_returns_0_for_valid_and_1_for_invalid(monkeypatch=None):
    import os

    # Valid token -> exit 0
    orig_get = check_token._get_json
    orig_env = os.environ.get("META_ACCESS_TOKEN")
    os.environ["META_ACCESS_TOKEN"] = "good"
    check_token._get_json = lambda url, timeout=30.0: {"id": "1", "name": "P"}
    try:
        assert check_token.main([]) == 0
        # Invalid token -> exit 1
        check_token._get_json = lambda url, timeout=30.0: {}
        assert check_token.main(["--quiet"]) == 1
        # Empty env -> exit 1
        del os.environ["META_ACCESS_TOKEN"]
        assert check_token.main([]) == 1
    finally:
        check_token._get_json = orig_get
        if orig_env is None:
            os.environ.pop("META_ACCESS_TOKEN", None)
        else:
            os.environ["META_ACCESS_TOKEN"] = orig_env


def test_main_validates_every_brand_when_brands_json_set():
    import os

    orig_get = check_token._get_json
    orig_brands = os.environ.get("BRANDS_JSON")
    # Two brands; both tokens resolve -> exit 0.
    os.environ["BRANDS_JSON"] = (
        '{"hp": {"meta_access_token": "hpT", "ig_user_id": "i", "fb_page_id": "f"},'
        ' "restore": {"meta_access_token": "rT", "ig_user_id": "i", "fb_page_id": "f"}}'
    )
    check_token._get_json = lambda url, timeout=30.0: {"id": "1", "name": "P"}
    try:
        assert check_token.main(["--quiet"]) == 0
        # One brand has an empty token -> that check fails -> exit 1.
        os.environ["BRANDS_JSON"] = (
            '{"hp": {"meta_access_token": "", "ig_user_id": "i", "fb_page_id": "f"}}'
        )
        assert check_token.main(["--quiet"]) == 1
    finally:
        check_token._get_json = orig_get
        if orig_brands is None:
            os.environ.pop("BRANDS_JSON", None)
        else:
            os.environ["BRANDS_JSON"] = orig_brands


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
