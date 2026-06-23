"""Tests for direct Google Business Profile v4 localPosts (no network — urlopen mocked)."""

from __future__ import annotations

import io
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.publish.direct import gbp  # noqa: E402


def _patch_urlopen(captured, *, status=200, body=b'{"name":"accounts/a/locations/l/localPosts/p1"}'):
    def _fake(req, timeout=None):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        captured["data"] = req.data
        if status >= 400:
            raise urllib.error.HTTPError(
                url=req.full_url, code=status, msg="Forbidden", hdrs=None,
                fp=io.BytesIO(b'{"error":{"status":"PERMISSION_DENIED"}}'),
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


def test_post_gbp_builds_correct_endpoint_and_payload():
    import json
    captured: dict = {}
    orig = _patch_urlopen(captured)
    try:
        res = gbp.post_gbp(
            "TOKEN", "acct1", "loc9", "Spring cleanup special!",
            media_url="https://cdn/p.jpg",
            cta={"actionType": "LEARN_MORE", "url": "https://hp.example"},
        )
    finally:
        urllib.request.urlopen = orig

    assert res == {"name": "accounts/a/locations/l/localPosts/p1"}
    assert captured["method"] == "POST"
    assert captured["url"] == (
        "https://mybusiness.googleapis.com/v4/accounts/acct1/locations/loc9/localPosts"
    )
    assert captured["headers"]["authorization"] == "Bearer TOKEN"
    body = json.loads(captured["data"].decode("utf-8"))
    assert body["summary"] == "Spring cleanup special!"
    assert body["topicType"] == "STANDARD"
    assert body["languageCode"] == "en-US"
    assert body["media"] == [{"mediaFormat": "PHOTO", "sourceUrl": "https://cdn/p.jpg"}]
    assert body["callToAction"] == {"actionType": "LEARN_MORE", "url": "https://hp.example"}


def test_post_gbp_text_only_omits_media_and_cta():
    import json
    captured: dict = {}
    orig = _patch_urlopen(captured)
    try:
        gbp.post_gbp("T", "a", "l", "Just text")
    finally:
        urllib.request.urlopen = orig
    body = json.loads(captured["data"].decode("utf-8"))
    assert body["summary"] == "Just text"
    assert "media" not in body
    assert "callToAction" not in body


def test_post_gbp_raises_with_body_on_http_error():
    captured: dict = {}
    orig = _patch_urlopen(captured, status=403)
    try:
        gbp.post_gbp("T", "a", "l", "x")
    except RuntimeError as e:
        assert "403" in str(e)
        assert "PERMISSION_DENIED" in str(e)
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
