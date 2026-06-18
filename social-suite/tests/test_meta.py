"""Tests for direct Meta Graph API posting (no network — _post_form mocked)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.publish.direct import meta  # noqa: E402


def _patch_post_form(calls):
    """Replace meta._post_form with a recorder that returns canned dicts."""

    def _fake(url, params, timeout=60.0):
        calls.append({"url": url, "params": dict(params)})
        # IG container-create returns an id used as creation_id.
        if url.endswith("/media"):
            return {"id": "container_123"}
        if url.endswith("/media_publish"):
            return {"id": "ig_post_999"}
        return {"id": "fb_post_1"}

    return _fake


def test_facebook_feed_post():
    calls: list = []
    orig = meta._post_form
    meta._post_form = _patch_post_form(calls)
    try:
        res = meta.post_facebook("page42", "TOKEN", "hello world")
    finally:
        meta._post_form = orig

    assert res == {"id": "fb_post_1"}
    assert len(calls) == 1
    c = calls[0]
    assert c["url"] == "https://graph.facebook.com/v21.0/page42/feed"
    assert c["params"]["message"] == "hello world"
    assert c["params"]["access_token"] == "TOKEN"
    assert "published" not in c["params"]


def test_facebook_feed_with_link():
    calls: list = []
    orig = meta._post_form
    meta._post_form = _patch_post_form(calls)
    try:
        meta.post_facebook("p", "T", "msg", link="https://example.com")
    finally:
        meta._post_form = orig
    assert calls[0]["params"]["link"] == "https://example.com"


def test_facebook_photo_post():
    calls: list = []
    orig = meta._post_form
    meta._post_form = _patch_post_form(calls)
    try:
        meta.post_facebook("p", "T", "caption here", image_url="https://img/x.jpg")
    finally:
        meta._post_form = orig
    c = calls[0]
    assert c["url"] == "https://graph.facebook.com/v21.0/p/photos"
    assert c["params"]["url"] == "https://img/x.jpg"
    assert c["params"]["caption"] == "caption here"
    assert "message" not in c["params"]


def test_facebook_scheduled():
    calls: list = []
    orig = meta._post_form
    meta._post_form = _patch_post_form(calls)
    try:
        meta.post_facebook("p", "T", "later", scheduled_time=1893456000)
    finally:
        meta._post_form = orig
    c = calls[0]
    assert c["params"]["published"] == "false"
    assert c["params"]["scheduled_publish_time"] == "1893456000"
    assert c["url"].endswith("/p/feed")


def test_instagram_two_step():
    calls: list = []
    orig = meta._post_form
    meta._post_form = _patch_post_form(calls)
    try:
        res = meta.post_instagram(
            "ig77", "TOKEN", "nice caption", image_url="https://img/p.jpg"
        )
    finally:
        meta._post_form = orig

    assert res == {"id": "ig_post_999"}
    assert len(calls) == 2
    create, publish = calls
    assert create["url"] == "https://graph.facebook.com/v21.0/ig77/media"
    assert create["params"]["image_url"] == "https://img/p.jpg"
    assert create["params"]["caption"] == "nice caption"
    assert publish["url"] == "https://graph.facebook.com/v21.0/ig77/media_publish"
    assert publish["params"]["creation_id"] == "container_123"


def test_instagram_reel_sets_media_type():
    calls: list = []
    orig = meta._post_form
    meta._post_form = _patch_post_form(calls)
    try:
        meta.post_instagram("ig", "T", "reel", video_url="https://v/clip.mp4")
    finally:
        meta._post_form = orig
    create = calls[0]
    assert create["params"]["video_url"] == "https://v/clip.mp4"
    assert create["params"]["media_type"] == "REELS"


def test_instagram_requires_media():
    try:
        meta.post_instagram("ig", "T", "no media")
    except ValueError as e:
        assert "public image_url or video_url" in str(e)
    else:
        raise AssertionError("expected ValueError when no media url given")


def test_post_form_raises_with_body_on_http_error():
    import io
    import urllib.error
    import urllib.request

    def _fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            url=req.full_url,
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"error":{"message":"Invalid token"}}'),
        )

    orig = urllib.request.urlopen
    urllib.request.urlopen = _fake_urlopen
    try:
        meta._post_form("https://graph.facebook.com/v21.0/p/feed", {"a": "1"})
    except RuntimeError as e:
        assert "400" in str(e)
        assert "Invalid token" in str(e)  # body surfaced
    else:
        raise AssertionError("expected RuntimeError on HTTP 400")
    finally:
        urllib.request.urlopen = orig


def test_post_form_raises_on_connection_error():
    import urllib.error
    import urllib.request

    def _fake_urlopen(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    orig = urllib.request.urlopen
    urllib.request.urlopen = _fake_urlopen
    try:
        meta._post_form("https://graph.facebook.com/v21.0/p/feed", {"a": "1"})
    except RuntimeError as e:
        assert "connection refused" in str(e)
    else:
        raise AssertionError("expected RuntimeError on URLError")
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
