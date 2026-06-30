"""Tests for direct TikTok Content Posting API (FILE_UPLOAD; no network)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.publish.direct import tiktok  # noqa: E402


def _tmp_video(data: bytes = b"fakevideobytes") -> str:
    fd, path = tempfile.mkstemp(suffix=".mp4")
    import os

    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path


def _patch(calls, *, init_returns=None):
    """Patch _post_json (creator_info + video/init) and _put_file. Returns originals."""
    def _fake_post(url, token, body, timeout=60.0):
        calls.append({"url": url, "token": token, "body": body})
        if url.endswith("/creator_info/query/"):
            return {"data": {"privacy_level_options": ["SELF_ONLY"]}, "error": {"code": "ok"}}
        if url.endswith("/video/init/"):
            return init_returns if init_returns is not None else {
                "data": {"publish_id": "pub_77", "upload_url": "https://upload.tiktok/abc"}
            }
        return {}

    def _fake_put(upload_url, path, size, timeout=300.0):
        calls.append({"put": upload_url, "path": path, "size": size})
        return 201

    orig = (tiktok._post_json, tiktok._put_file)
    tiktok._post_json = _fake_post
    tiktok._put_file = _fake_put
    return orig


def _restore(orig):
    tiktok._post_json, tiktok._put_file = orig


def test_post_tiktok_inits_file_upload_and_uploads_bytes():
    import os

    calls: list = []
    orig = _patch(calls)
    path = _tmp_video(b"x" * 1234)
    try:
        pub_id = tiktok.post_tiktok("TOKEN", "my caption", path, privacy_level="SELF_ONLY")
    finally:
        _restore(orig)
        os.remove(path)

    assert pub_id == "pub_77"
    # creator_info, video/init, then the PUT upload.
    assert calls[0]["url"].endswith("/creator_info/query/")
    init = calls[1]
    assert init["url"].endswith("/video/init/")
    assert init["body"]["post_info"]["privacy_level"] == "SELF_ONLY"
    assert init["body"]["post_info"]["title"] == "my caption"
    src = init["body"]["source_info"]
    assert src["source"] == "FILE_UPLOAD"
    assert src["video_size"] == 1234
    assert src["chunk_size"] == 1234
    assert src["total_chunk_count"] == 1
    # The bytes were PUT to the returned upload_url.
    put = calls[2]
    assert put["put"] == "https://upload.tiktok/abc"
    assert put["size"] == 1234


def test_upload_to_inbox_inits_and_uploads_without_post_info():
    import os

    calls: list = []
    orig = _patch(calls)
    path = _tmp_video(b"y" * 999)
    try:
        pub_id = tiktok.upload_to_inbox("TOKEN", path)
    finally:
        _restore(orig)
        os.remove(path)

    assert pub_id == "pub_77"
    # Inbox flow hits inbox/video/init/ directly (no creator_info), no post_info.
    init = calls[0]
    assert init["url"].endswith("/inbox/video/init/")
    assert "post_info" not in init["body"]
    src = init["body"]["source_info"]
    assert src["source"] == "FILE_UPLOAD"
    assert src["video_size"] == 999
    assert src["total_chunk_count"] == 1
    # Bytes PUT to the returned upload_url.
    put = calls[1]
    assert put["put"] == "https://upload.tiktok/abc"
    assert put["size"] == 999


def test_upload_to_inbox_raises_when_no_publish_id():
    import os

    calls: list = []
    orig = _patch(calls, init_returns={"data": {}})
    path = _tmp_video()
    try:
        tiktok.upload_to_inbox("T", path)
    except RuntimeError as e:
        assert "publish_id" in str(e)
    else:
        raise AssertionError("expected RuntimeError when no publish_id/upload_url")
    finally:
        _restore(orig)
        os.remove(path)


def test_post_tiktok_default_privacy_is_self_only():
    import os

    calls: list = []
    orig = _patch(calls)
    path = _tmp_video()
    try:
        tiktok.post_tiktok("T", "c", path)
    finally:
        _restore(orig)
        os.remove(path)
    assert calls[1]["body"]["post_info"]["privacy_level"] == "SELF_ONLY"


def test_post_tiktok_rejects_bad_privacy_level():
    try:
        tiktok.post_tiktok("T", "c", "/nonexistent.mp4", privacy_level="WHATEVER")
    except ValueError as e:
        assert "privacy_level" in str(e)
    else:
        raise AssertionError("expected ValueError on invalid privacy_level")


def test_post_tiktok_raises_when_no_publish_id():
    import os

    calls: list = []
    orig = _patch(calls, init_returns={"data": {}})
    path = _tmp_video()
    try:
        tiktok.post_tiktok("T", "c", path)
    except RuntimeError as e:
        assert "publish_id" in str(e)
    else:
        raise AssertionError("expected RuntimeError when no publish_id/upload_url")
    finally:
        _restore(orig)
        os.remove(path)


def test_post_tiktok_rejects_missing_video():
    try:
        tiktok.post_tiktok("T", "c", "/definitely/not/here.mp4")
    except RuntimeError as e:
        assert "not a local file" in str(e)
    else:
        raise AssertionError("expected RuntimeError for a missing local file")


def test_ensure_local_passes_through_existing_path():
    import os

    path = _tmp_video()
    try:
        resolved, is_temp = tiktok._ensure_local(path)
        assert resolved == path
        assert is_temp is False
    finally:
        os.remove(path)


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
