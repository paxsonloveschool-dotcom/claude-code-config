"""Tests for direct YouTube Data API v3 videos.insert (no network — urlopen mocked)."""

from __future__ import annotations

import io
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.publish.direct import youtube  # noqa: E402


def _patch_urlopen(captured, *, status=200, location="https://upload.googleapis.com/sess/abc"):
    def _fake(req, timeout=None):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        captured["data"] = req.data
        if status >= 400:
            raise urllib.error.HTTPError(
                url=req.full_url, code=status, msg="Forbidden", hdrs=None,
                fp=io.BytesIO(b'{"error":{"message":"insufficientPermissions"}}'),
            )

        class _Hdrs:
            def get(self_, k):
                return location if k == "Location" else None

        class _Resp:
            headers = _Hdrs()

            def __enter__(self_):
                return self_

            def __exit__(self_, *a):
                return False

        return _Resp()

    orig = urllib.request.urlopen
    urllib.request.urlopen = _fake
    return orig


def test_post_youtube_initiates_resumable_with_correct_metadata():
    import json
    captured: dict = {}
    orig = _patch_urlopen(captured)
    try:
        res = youtube.post_youtube(
            "TOKEN", "My Title", "My description", "https://cdn/v.mp4",
            privacy_status="unlisted", category_id="22",
        )
    finally:
        urllib.request.urlopen = orig

    assert res["upload_url"] == "https://upload.googleapis.com/sess/abc"
    assert captured["method"] == "POST"
    assert captured["url"] == (
        "https://www.googleapis.com/upload/youtube/v3/videos"
        "?uploadType=resumable&part=snippet,status"
    )
    assert captured["headers"]["authorization"] == "Bearer TOKEN"
    assert captured["headers"]["x-upload-content-type"] == "video/*"
    body = json.loads(captured["data"].decode("utf-8"))
    assert body["snippet"] == {
        "title": "My Title",
        "description": "My description",
        "categoryId": "22",
    }
    assert body["status"] == {"privacyStatus": "unlisted"}


def test_post_youtube_raises_when_no_location_header():
    captured: dict = {}
    orig = _patch_urlopen(captured, location=None)
    try:
        youtube.post_youtube("T", "t", "d", "https://cdn/v.mp4")
    except RuntimeError as e:
        assert "Location" in str(e)
    else:
        raise AssertionError("expected RuntimeError when no Location header")
    finally:
        urllib.request.urlopen = orig


def test_post_youtube_raises_with_body_on_http_error():
    captured: dict = {}
    orig = _patch_urlopen(captured, status=403)
    try:
        youtube.post_youtube("T", "t", "d", "https://cdn/v.mp4")
    except RuntimeError as e:
        assert "403" in str(e)
        assert "insufficientPermissions" in str(e)
    else:
        raise AssertionError("expected RuntimeError on HTTP 403")
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
