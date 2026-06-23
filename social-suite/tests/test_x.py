"""Tests for direct X (Twitter) v2 posting (no network — urlopen mocked)."""

from __future__ import annotations

import io
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.publish.direct import x  # noqa: E402


def _patch_urlopen(captured, *, status=200, body=b'{"data":{"id":"tw1"}}'):
    def _fake(req, timeout=None):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["headers"] = dict(req.header_items())
        captured["data"] = req.data
        if status >= 400:
            raise urllib.error.HTTPError(
                url=req.full_url, code=status, msg="Bad Request",
                hdrs=None, fp=io.BytesIO(body),
            )

        class _Resp:
            def __enter__(self_):
                return self_

            def __exit__(self_, *a):
                return False

            def read(self_):
                return body

        return _Resp()

    orig = urllib.request.urlopen
    urllib.request.urlopen = _fake
    return orig


def test_post_x_text_only_builds_correct_request():
    import json
    captured: dict = {}
    orig = _patch_urlopen(captured)
    try:
        res = x.post_x("hello x", "TOKEN")
    finally:
        urllib.request.urlopen = orig

    assert res == {"data": {"id": "tw1"}}
    assert captured["url"] == "https://api.x.com/2/tweets"
    assert captured["method"] == "POST"
    # Bearer auth header (urllib title-cases header keys).
    hdrs = {k.lower(): v for k, v in captured["headers"].items()}
    assert hdrs["authorization"] == "Bearer TOKEN"
    assert hdrs["content-type"] == "application/json"
    body = json.loads(captured["data"].decode("utf-8"))
    assert body == {"text": "hello x"}


def test_post_x_with_media_uploads_and_attaches_ids():
    import json
    captured: dict = {}
    orig = _patch_urlopen(captured)
    orig_upload = x.upload_media
    x.upload_media = lambda url, token: "media_42"
    try:
        x.post_x("with pic", "T", media_urls=["https://img/a.jpg"])
    finally:
        urllib.request.urlopen = orig
        x.upload_media = orig_upload

    body = json.loads(captured["data"].decode("utf-8"))
    assert body["text"] == "with pic"
    assert body["media"] == {"media_ids": ["media_42"]}


def test_post_x_raises_with_body_on_http_error():
    captured: dict = {}
    orig = _patch_urlopen(
        captured, status=400, body=b'{"title":"Unauthorized","detail":"bad token"}'
    )
    try:
        x.post_x("boom", "T")
    except RuntimeError as e:
        assert "400" in str(e)
        assert "bad token" in str(e)  # body surfaced
    else:
        raise AssertionError("expected RuntimeError on HTTP 400")
    finally:
        urllib.request.urlopen = orig


def test_upload_media_is_stubbed_notimplemented():
    try:
        x.upload_media("https://img/a.jpg", "T")
    except NotImplementedError as e:
        assert "byte-upload" in str(e) or "upload" in str(e).lower()
    else:
        raise AssertionError("expected NotImplementedError from stubbed upload")


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
