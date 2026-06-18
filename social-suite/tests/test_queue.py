"""Tests for the posting queue (load/save round-trip + due logic). No network."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.publish.queue import (  # noqa: E402
    QueuedPost,
    due_posts,
    load_queue,
    save_queue,
)


def test_round_trip_load_save():
    posts = [
        QueuedPost(
            id="a",
            text="hi",
            media_url="https://x/a.jpg",
            platforms=["instagram", "facebook"],
            schedule="2026-01-01T00:00:00+00:00",
        ),
        QueuedPost(id="b", text="yo", platforms=["facebook"]),
    ]
    with tempfile.TemporaryDirectory() as d:
        path = str(Path(d) / "queue.json")
        save_queue(path, posts)
        loaded = load_queue(path)

    assert len(loaded) == 2
    assert loaded[0] == posts[0]
    assert loaded[1].platforms == ["facebook"]
    assert loaded[1].status == "pending"
    assert loaded[1].media_url is None


def test_load_missing_file_is_empty():
    with tempfile.TemporaryDirectory() as d:
        assert load_queue(str(Path(d) / "nope.json")) == []


def test_load_ignores_unknown_keys():
    with tempfile.TemporaryDirectory() as d:
        path = str(Path(d) / "q.json")
        Path(path).write_text(
            '[{"id":"x","text":"t","platforms":["facebook"],"extra":"ignored"}]'
        )
        loaded = load_queue(path)
    assert loaded[0].id == "x"
    assert not hasattr(loaded[0], "extra")


def test_due_respects_status():
    posts = [
        QueuedPost(id="p", text="t", platforms=["facebook"], status="pending"),
        QueuedPost(id="s", text="t", platforms=["facebook"], status="sent"),
        QueuedPost(id="f", text="t", platforms=["facebook"], status="failed"),
    ]
    due = due_posts(posts, "2026-06-18T00:00:00+00:00")
    assert [p.id for p in due] == ["p"]


def test_due_respects_schedule():
    now = "2026-06-18T12:00:00+00:00"
    posts = [
        QueuedPost(id="no_sched", text="t", platforms=["facebook"]),
        QueuedPost(
            id="past", text="t", platforms=["facebook"],
            schedule="2026-06-18T11:00:00+00:00",
        ),
        QueuedPost(
            id="exact", text="t", platforms=["facebook"], schedule=now,
        ),
        QueuedPost(
            id="future", text="t", platforms=["facebook"],
            schedule="2026-06-18T13:00:00+00:00",
        ),
    ]
    due_ids = {p.id for p in due_posts(posts, now)}
    assert due_ids == {"no_sched", "past", "exact"}
    assert "future" not in due_ids


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
