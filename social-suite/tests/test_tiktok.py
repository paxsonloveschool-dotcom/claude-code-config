"""Tests for direct TikTok Content Posting API (no network — _post_json mocked)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.publish.direct import tiktok  # noqa: E402


def _patch_post_json(calls, *, init_returns=None):
    def _fake(url, token, body, timeout=60.0):
        calls.append({"url": url, "token": token, "body": body})
        if url.endswith("/creator_info/query/"):
            return {"data": {"privacy_level_options": ["SELF_ONLY", "PUBLIC_TO_EVERYONE"]}}
        if url.endswith("/video/init/"):
            return init_returns if init_returns is not None else {"data": {"publish_id": "pub_77"}}
        return {}

    orig = tiktok._post_json
    tiktok._post_json = _fake
    return orig


def test_post_tiktok_queries_then_inits_and_returns_publish_id():
    calls: list = []
    orig = _patch_post_json(calls)
    try:
        pub_id = tiktok.post_tiktok(
            "TOKEN", "my caption", "https://cdn/v.mp4", privacy_level="PUBLIC_TO_EVERYONE"
        )
    finally:
        tiktok._post_json = orig

    assert pub_id == "pub_77"
    assert len(calls) == 2
    query, init = calls
    assert query["url"] == "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
    assert init["url"] == "https://open.tiktokapis.com/v2/post/publish/video/init/"
    assert init["token"] == "TOKEN"
    # post_info + source_info shape.
    assert init["body"]["post_info"]["title"] == "my caption"
    assert init["body"]["post_info"]["privacy_level"] == "PUBLIC_TO_EVERYONE"
    assert init["body"]["source_info"] == {
        "source": "PULL_FROM_URL",
        "video_url": "https://cdn/v.mp4",
    }


def test_post_tiktok_default_privacy_is_self_only():
    calls: list = []
    orig = _patch_post_json(calls)
    try:
        tiktok.post_tiktok("T", "c", "https://cdn/v.mp4")
    finally:
        tiktok._post_json = orig
    init = calls[1]
    assert init["body"]["post_info"]["privacy_level"] == "SELF_ONLY"


def test_post_tiktok_rejects_bad_privacy_level():
    try:
        tiktok.post_tiktok("T", "c", "https://cdn/v.mp4", privacy_level="WHATEVER")
    except ValueError as e:
        assert "privacy_level" in str(e)
    else:
        raise AssertionError("expected ValueError on invalid privacy_level")


def test_post_tiktok_raises_when_no_publish_id():
    calls: list = []
    orig = _patch_post_json(calls, init_returns={"data": {}})
    try:
        tiktok.post_tiktok("T", "c", "https://cdn/v.mp4")
    except RuntimeError as e:
        assert "publish_id" in str(e)
    else:
        raise AssertionError("expected RuntimeError when no publish_id returned")
    finally:
        tiktok._post_json = orig


def test_post_json_raises_with_body_on_http_error():
    import io
    import urllib.error
    import urllib.request

    def _fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            url=req.full_url, code=401, msg="Unauthorized", hdrs=None,
            fp=io.BytesIO(b'{"error":{"code":"access_token_invalid"}}'),
        )

    orig = urllib.request.urlopen
    urllib.request.urlopen = _fake_urlopen
    try:
        tiktok._post_json(tiktok.VIDEO_INIT_URL, "T", {})
    except RuntimeError as e:
        assert "401" in str(e)
        assert "access_token_invalid" in str(e)
    else:
        raise AssertionError("expected RuntimeError on HTTP 401")
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
