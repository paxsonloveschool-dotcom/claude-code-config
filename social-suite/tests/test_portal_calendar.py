"""Tests for the portal /calendar view (reads queue.json). No network."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from portal import app as portal_app  # noqa: E402

_QUEUE = [
    {"id": "hp-001", "brand": "hp", "text": "Spring lawn care time", "media_url": None,
     "platforms": ["facebook"], "schedule": None, "status": "sent"},
    {"id": "hp-002", "brand": "hp", "text": "Before and after mow", "media_url": "https://x/y.jpg",
     "platforms": ["facebook", "instagram"], "schedule": "2026-06-19T13:00:00Z", "status": "paused"},
    {"id": "restore-001", "brand": "restore", "text": "Water damage? Call now", "media_url": None,
     "platforms": ["facebook"], "schedule": None, "status": "paused"},
]


def _client_with_queue(tmpdir):
    path = Path(tmpdir) / "queue.json"
    path.write_text(json.dumps(_QUEUE), encoding="utf-8")
    os.environ["QUEUE_PATH"] = str(path)
    return TestClient(portal_app.app)


def test_calendar_renders_all_brands_and_posts():
    with tempfile.TemporaryDirectory() as d:
        client = _client_with_queue(d)
        try:
            r = client.get("/calendar")
        finally:
            os.environ.pop("QUEUE_PATH", None)
    assert r.status_code == 200
    body = r.text
    assert "Content Calendar" in body
    # both brands shown
    assert "hp" in body and "restore" in body
    # post content + ids surfaced
    assert "Spring lawn care time" in body
    assert "hp-002" in body
    assert "Water damage? Call now" in body
    # status tally rendered (2 paused, 1 sent)
    assert "paused" in body and "sent" in body


def test_calendar_groups_and_counts():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "queue.json"
        path.write_text(json.dumps(_QUEUE), encoding="utf-8")
        os.environ["QUEUE_PATH"] = str(path)
        try:
            groups, totals = portal_app._load_queue_grouped()
        finally:
            os.environ.pop("QUEUE_PATH", None)
    names = [g["brand"] for g in groups]
    assert names == ["hp", "restore"]  # sorted
    hp = next(g for g in groups if g["brand"] == "hp")
    assert hp["count"] == 2
    # unscheduled ("now") posts sort before scheduled ones
    assert hp["posts"][0]["schedule"] is None
    assert totals == {"sent": 1, "paused": 2}


def test_calendar_empty_when_no_queue():
    os.environ["QUEUE_PATH"] = "/nonexistent/queue.json"
    try:
        client = TestClient(portal_app.app)
        r = client.get("/calendar")
    finally:
        os.environ.pop("QUEUE_PATH", None)
    assert r.status_code == 200
    assert "No queued content yet" in r.text


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
