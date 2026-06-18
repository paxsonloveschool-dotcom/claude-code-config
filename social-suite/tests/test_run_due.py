"""Tests for run_due (posters monkeypatched, temp queue file). No network."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.publish import run_due  # noqa: E402
from services.publish.direct import meta  # noqa: E402
from services.publish.queue import QueuedPost, load_queue, save_queue  # noqa: E402

NOW = "2026-06-18T12:00:00+00:00"


def _set_env():
    os.environ["META_ACCESS_TOKEN"] = "TOKEN"
    os.environ["IG_USER_ID"] = "ig1"
    os.environ["FB_PAGE_ID"] = "fb1"


def _clear_env():
    for k in ("META_ACCESS_TOKEN", "IG_USER_ID", "FB_PAGE_ID", "BRANDS_JSON", "BRANDS_FILE"):
        os.environ.pop(k, None)


def _patch_posters(fb_calls, ig_calls, fb_raise=None, ig_raise=None):
    orig_fb, orig_ig = meta.post_facebook, meta.post_instagram

    def _fb(**kwargs):
        fb_calls.append(kwargs)
        if fb_raise:
            raise RuntimeError(fb_raise)
        return {"id": "fb"}

    def _ig(**kwargs):
        ig_calls.append(kwargs)
        if ig_raise:
            raise RuntimeError(ig_raise)
        return {"id": "ig"}

    meta.post_facebook = _fb
    meta.post_instagram = _ig
    return orig_fb, orig_ig


def _restore(orig):
    meta.post_facebook, meta.post_instagram = orig


def test_due_post_marks_sent_and_calls_both():
    fb_calls, ig_calls = [], []
    orig = _patch_posters(fb_calls, ig_calls)
    _set_env()
    try:
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "queue.json")
            save_queue(path, [
                QueuedPost(
                    id="p1", text="hello",
                    media_url="https://img/x.jpg",
                    platforms=["instagram", "facebook"],
                ),
            ])
            summary = run_due.run(path, now_iso=NOW)
            reloaded = load_queue(path)
    finally:
        _restore(orig)
        _clear_env()

    assert summary == {"posted": 1, "failed": 0, "skipped": 0}
    assert len(fb_calls) == 1 and len(ig_calls) == 1
    assert reloaded[0].status == "sent"
    assert reloaded[0].error is None


def test_future_post_is_skipped():
    fb_calls, ig_calls = [], []
    orig = _patch_posters(fb_calls, ig_calls)
    _set_env()
    try:
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "queue.json")
            save_queue(path, [
                QueuedPost(
                    id="later", text="t", media_url="https://i/x.jpg",
                    platforms=["facebook"],
                    schedule="2026-06-18T13:00:00+00:00",
                ),
            ])
            summary = run_due.run(path, now_iso=NOW)
            reloaded = load_queue(path)
    finally:
        _restore(orig)
        _clear_env()

    assert summary == {"posted": 0, "failed": 0, "skipped": 1}
    assert not fb_calls and not ig_calls
    assert reloaded[0].status == "pending"


def test_dry_run_posts_nothing():
    fb_calls, ig_calls = [], []
    orig = _patch_posters(fb_calls, ig_calls)
    _set_env()
    try:
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "queue.json")
            save_queue(path, [
                QueuedPost(
                    id="p", text="t", media_url="https://i/x.jpg",
                    platforms=["facebook"],
                ),
            ])
            summary = run_due.run(path, dry_run=True, now_iso=NOW)
            reloaded = load_queue(path)
    finally:
        _restore(orig)
        _clear_env()

    assert summary == {"posted": 0, "failed": 0, "skipped": 0}
    assert not fb_calls and not ig_calls
    # dry-run never writes statuses back.
    assert reloaded[0].status == "pending"


def test_failing_poster_marks_failed_without_aborting_others():
    fb_calls, ig_calls = [], []
    # facebook poster raises; the second (good) post must still go out.
    orig = _patch_posters(fb_calls, ig_calls, fb_raise="boom")
    _set_env()
    try:
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "queue.json")
            save_queue(path, [
                QueuedPost(id="bad", text="t", media_url="https://i/x.jpg",
                           platforms=["facebook"]),
                QueuedPost(id="good", text="t", media_url="https://i/y.jpg",
                           platforms=["instagram"]),
            ])
            summary = run_due.run(path, now_iso=NOW)
            reloaded = load_queue(path)
    finally:
        _restore(orig)
        _clear_env()

    assert summary == {"posted": 1, "failed": 1, "skipped": 0}
    by_id = {p.id: p for p in reloaded}
    assert by_id["bad"].status == "failed"
    assert "boom" in by_id["bad"].error
    assert by_id["good"].status == "sent"
    assert len(ig_calls) == 1


_BRANDS_JSON = (
    '{"hp": {"meta_access_token": "hpTOK", "ig_user_id": "hpIG", "fb_page_id": "hpFB"},'
    ' "restore": {"meta_access_token": "rTOK", "ig_user_id": "rIG", "fb_page_id": "rFB"}}'
)


def test_multibrand_routes_each_post_to_its_own_creds():
    fb_calls, ig_calls = [], []
    orig = _patch_posters(fb_calls, ig_calls)
    _clear_env()
    os.environ["BRANDS_JSON"] = _BRANDS_JSON
    try:
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "queue.json")
            save_queue(path, [
                QueuedPost(id="hp1", text="hp", media_url="https://i/hp.jpg",
                           platforms=["instagram"], brand="hp"),
                QueuedPost(id="r1", text="rs", media_url="https://i/r.jpg",
                           platforms=["facebook"], brand="restore"),
            ])
            summary = run_due.run(path, now_iso=NOW)
            reloaded = {p.id: p for p in load_queue(path)}
    finally:
        _restore(orig)
        _clear_env()

    assert summary == {"posted": 2, "failed": 0, "skipped": 0}
    # HP post -> instagram with HP creds.
    assert len(ig_calls) == 1
    assert ig_calls[0]["ig_user_id"] == "hpIG"
    assert ig_calls[0]["access_token"] == "hpTOK"
    # Restore post -> facebook with Restore creds.
    assert len(fb_calls) == 1
    assert fb_calls[0]["page_id"] == "rFB"
    assert fb_calls[0]["access_token"] == "rTOK"
    assert reloaded["hp1"].status == "sent"
    assert reloaded["r1"].status == "sent"


def test_unknown_brand_marks_only_that_post_failed():
    fb_calls, ig_calls = [], []
    orig = _patch_posters(fb_calls, ig_calls)
    _clear_env()
    os.environ["BRANDS_JSON"] = _BRANDS_JSON
    try:
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "queue.json")
            save_queue(path, [
                QueuedPost(id="ghost", text="x", media_url="https://i/g.jpg",
                           platforms=["instagram"], brand="nope"),
                QueuedPost(id="hp1", text="hp", media_url="https://i/hp.jpg",
                           platforms=["instagram"], brand="hp"),
            ])
            summary = run_due.run(path, now_iso=NOW)
            reloaded = {p.id: p for p in load_queue(path)}
    finally:
        _restore(orig)
        _clear_env()

    assert summary == {"posted": 1, "failed": 1, "skipped": 0}
    assert reloaded["ghost"].status == "failed"
    assert "nope" in reloaded["ghost"].error
    # The good HP post still went out with HP creds.
    assert reloaded["hp1"].status == "sent"
    assert len(ig_calls) == 1 and ig_calls[0]["ig_user_id"] == "hpIG"


def test_no_brand_uses_default_from_legacy_env():
    fb_calls, ig_calls = [], []
    orig = _patch_posters(fb_calls, ig_calls)
    _clear_env()
    # No BRANDS_JSON -> "default" brand built from legacy env vars.
    os.environ["META_ACCESS_TOKEN"] = "TOKEN"
    os.environ["IG_USER_ID"] = "ig1"
    os.environ["FB_PAGE_ID"] = "fb1"
    try:
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "queue.json")
            save_queue(path, [
                QueuedPost(id="legacy", text="t", media_url="https://i/x.jpg",
                           platforms=["facebook"]),  # brand=None
            ])
            summary = run_due.run(path, now_iso=NOW)
            reloaded = load_queue(path)
    finally:
        _restore(orig)
        _clear_env()

    assert summary == {"posted": 1, "failed": 0, "skipped": 0}
    assert fb_calls[0]["page_id"] == "fb1"
    assert fb_calls[0]["access_token"] == "TOKEN"
    assert reloaded[0].status == "sent"


def test_brand_with_missing_creds_marks_failed():
    fb_calls, ig_calls = [], []
    orig = _patch_posters(fb_calls, ig_calls)
    _clear_env()
    # "hp" exists but has an empty fb_page_id -> facebook post fails cleanly.
    os.environ["BRANDS_JSON"] = (
        '{"hp": {"meta_access_token": "hpTOK", "ig_user_id": "hpIG", "fb_page_id": ""}}'
    )
    try:
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d) / "queue.json")
            save_queue(path, [
                QueuedPost(id="hpfb", text="t", media_url="https://i/x.jpg",
                           platforms=["facebook"], brand="hp"),
            ])
            summary = run_due.run(path, now_iso=NOW)
            reloaded = load_queue(path)
    finally:
        _restore(orig)
        _clear_env()

    assert summary == {"posted": 0, "failed": 1, "skipped": 0}
    assert reloaded[0].status == "failed"
    assert "fb_page_id" in reloaded[0].error
    assert not fb_calls


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
