"""Tests for automation/build_queue.py (no network, stdlib only)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from automation import build_queue  # noqa: E402


def _write_content(tmp, brand, n):
    posts = [
        {
            "id": f"{brand}-{i:03d}",
            "brand": brand,
            "text": f"{brand} post {i}",
            "media_url": None,
            "platforms": ["facebook"],
            "schedule": None,
            "status": "pending",
        }
        for i in range(1, n + 1)
    ]
    (Path(tmp) / f"{brand}-content.json").write_text(json.dumps(posts), encoding="utf-8")


def _patch_dirs(tmp):
    build_queue.CONTENT_DIR = str(tmp)
    build_queue.QUEUE_PATH = str(Path(tmp) / "queue.json")


def test_merges_brands_and_keeps_brand_tag(tmp_path):
    _patch_dirs(tmp_path)
    _write_content(tmp_path, "hp", 3)
    _write_content(tmp_path, "restore", 2)
    q = build_queue.build(now=datetime(2026, 6, 18, tzinfo=timezone.utc))
    assert len(q) == 5
    assert {p["brand"] for p in q} == {"hp", "restore"}
    # every post stays tagged with the brand it came from (no cross-contamination)
    assert all(p["id"].startswith(p["brand"]) for p in q)


def test_first_post_per_brand_is_immediate_rest_scheduled(tmp_path):
    _patch_dirs(tmp_path)
    _write_content(tmp_path, "hp", 3)
    now = datetime(2026, 6, 18, tzinfo=timezone.utc)
    q = build_queue.build(now=now)
    hp = [p for p in q if p["brand"] == "hp"]
    assert hp[0]["schedule"] is None  # first posts now
    assert hp[1]["schedule"] == "2026-06-19T13:00:00Z"  # tomorrow, hp slot
    assert hp[2]["schedule"] == "2026-06-20T13:00:00Z"  # next day


def test_staggered_slots_between_brands(tmp_path):
    _patch_dirs(tmp_path)
    _write_content(tmp_path, "hp", 2)
    _write_content(tmp_path, "restore", 2)
    q = build_queue.build(now=datetime(2026, 6, 18, tzinfo=timezone.utc))
    hp1 = next(p for p in q if p["id"] == "hp-002")
    re1 = next(p for p in q if p["id"] == "restore-002")
    assert hp1["schedule"] == "2026-06-19T13:00:00Z"
    assert re1["schedule"] == "2026-06-19T16:00:00Z"  # different slot, no collision


def test_preserves_status_of_already_sent_posts(tmp_path):
    _patch_dirs(tmp_path)
    _write_content(tmp_path, "hp", 2)
    # Pretend hp-001 already went out.
    (Path(tmp_path) / "queue.json").write_text(
        json.dumps([{"id": "hp-001", "status": "sent", "error": None}]),
        encoding="utf-8",
    )
    q = build_queue.build(now=datetime(2026, 6, 18, tzinfo=timezone.utc))
    sent = next(p for p in q if p["id"] == "hp-001")
    assert sent["status"] == "sent"  # not reset to pending → never re-posted
    nxt = next(p for p in q if p["id"] == "hp-002")
    assert nxt["status"] == "pending"  # untouched posts stay pending


def _run():
    import tempfile

    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            with tempfile.TemporaryDirectory() as d:
                fn(Path(d))
            print(f"  PASS {name}")
            passed += 1
    print(f"\n{passed} tests passed.")


if __name__ == "__main__":
    _run()
