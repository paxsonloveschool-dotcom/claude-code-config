"""Tests for the Postiz poster (no network — payload + dry-run only)."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.publish import poster  # noqa: E402
from services.publish.poster import (  # noqa: E402
    ScheduledPost,
    build_payload,
    schedule_post,
)


def test_build_payload_multiple_channels():
    payload = build_payload(
        "great caption #yes",
        ["chan_ig", "chan_tt", "chan_yt"],
        platforms={"chan_ig": "instagram", "chan_tt": "tiktok", "chan_yt": "youtube"},
    )
    assert payload["type"] == "now"
    assert "date" in payload
    assert len(payload["posts"]) == 3

    by_id = {p["integration"]["id"]: p for p in payload["posts"]}
    assert by_id["chan_ig"]["settings"]["__type"] == "instagram"
    assert by_id["chan_tt"]["settings"]["__type"] == "tiktok"
    assert by_id["chan_yt"]["settings"]["__type"] == "youtube"
    # Caption carried per channel.
    assert by_id["chan_ig"]["value"][0]["content"] == "great caption #yes"


def test_build_payload_schedule_type():
    when = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
    payload = build_payload("c", ["a"], when=when, default_platform="x")
    assert payload["type"] == "schedule"
    assert payload["date"].startswith("2030-01-01T12:00")
    assert payload["posts"][0]["settings"]["__type"] == "x"


def test_build_payload_rejects_bad_platform():
    try:
        build_payload("c", ["a"], default_platform="myspace")
    except ValueError as e:
        assert "Invalid platform" in str(e)
    else:
        raise AssertionError("expected ValueError for invalid platform")


def test_build_payload_attaches_media():
    payload = build_payload(
        "c", ["a"], media_urls=["http://x/v.mp4"], default_platform="facebook"
    )
    assert payload["posts"][0]["value"][0]["image"] == [{"path": "http://x/v.mp4"}]


def test_dry_run_sends_nothing(monkeypatch=None):
    # Make any accidental network attempt explode.
    def _boom(*a, **k):
        raise AssertionError("dry-run must not perform any HTTP request")

    orig = poster._post_json
    poster._post_json = _boom
    try:
        result = schedule_post(
            "/tmp/clip.mp4",
            "hello world",
            channels=["c1", "c2"],
            default_platform="instagram",
            dry_run=True,
        )
    finally:
        poster._post_json = orig

    assert isinstance(result, ScheduledPost)
    assert result.status == "dry-run"
    assert result.post_id == ""
    assert result.channels == ["c1", "c2"]


def test_schedule_post_sends_payload_and_auth(monkeypatch=None):
    captured: dict = {}

    def _fake_post(url, body, api_key):
        captured["url"] = url
        captured["body"] = body
        captured["api_key"] = api_key
        return {"id": "post_123"}

    import os

    orig_post = poster._post_json
    poster._post_json = _fake_post
    os.environ["POSTIZ_API_URL"] = "https://postiz.example.com/"
    os.environ["POSTIZ_API_KEY"] = "secret-raw-key"
    try:
        result = schedule_post(
            "/tmp/clip.mp4",
            "yo",
            channels=["cc"],
            default_platform="linkedin",
        )
    finally:
        poster._post_json = orig_post
        os.environ.pop("POSTIZ_API_URL", None)
        os.environ.pop("POSTIZ_API_KEY", None)

    # URL is correct, trailing slash trimmed.
    assert captured["url"] == "https://postiz.example.com/public/v1/posts"
    # Raw key (no Bearer).
    assert captured["api_key"] == "secret-raw-key"
    assert captured["body"]["posts"][0]["settings"]["__type"] == "linkedin"
    assert result.post_id == "post_123"
    assert result.status == "posted"


def test_post_json_uses_raw_authorization_header():
    """Verify the HTTP layer sets Authorization to the raw key (no Bearer)."""
    import urllib.request

    captured: dict = {}

    class _FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"id":"x"}'

    def _fake_urlopen(req, timeout=None):
        captured["headers"] = req.headers
        captured["method"] = req.get_method()
        captured["url"] = req.full_url
        return _FakeResp()

    orig = urllib.request.urlopen
    urllib.request.urlopen = _fake_urlopen
    try:
        poster._post_json("https://h/public/v1/posts", {"a": 1}, "RAWKEY")
    finally:
        urllib.request.urlopen = orig

    # urllib title-cases header keys.
    assert captured["headers"]["Authorization"] == "RAWKEY"
    assert captured["method"] == "POST"


def test_post_json_raises_with_body_on_http_error():
    """Non-2xx must raise a clear error that includes Postiz's response body."""
    import io
    import urllib.error
    import urllib.request

    def _fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            url=req.full_url,
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"missing integration"}'),
        )

    orig = urllib.request.urlopen
    urllib.request.urlopen = _fake_urlopen
    try:
        poster._post_json("https://h/public/v1/posts", {"a": 1}, "K")
    except RuntimeError as e:
        msg = str(e)
        assert "400" in msg
        assert "missing integration" in msg  # body surfaced
    else:
        raise AssertionError("expected RuntimeError on HTTP 400")
    finally:
        urllib.request.urlopen = orig


def test_post_json_raises_on_connection_error():
    import urllib.error
    import urllib.request

    def _fake_urlopen(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    orig = urllib.request.urlopen
    urllib.request.urlopen = _fake_urlopen
    try:
        poster._post_json("https://h/public/v1/posts", {"a": 1}, "K")
    except RuntimeError as e:
        assert "connection refused" in str(e)
    else:
        raise AssertionError("expected RuntimeError on URLError")
    finally:
        urllib.request.urlopen = orig


def test_post_json_passes_timeout():
    import urllib.request

    captured: dict = {}

    class _FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"{}"

    def _fake_urlopen(req, timeout=None):
        captured["timeout"] = timeout
        return _FakeResp()

    orig = urllib.request.urlopen
    urllib.request.urlopen = _fake_urlopen
    try:
        poster._post_json("https://h/public/v1/posts", {"a": 1}, "K")
    finally:
        urllib.request.urlopen = orig
    assert captured["timeout"] is not None and captured["timeout"] > 0


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
