"""Offline tests for the bulk review feed renderer (services/review/feed.py).

Pure HTML generation — no ffmpeg, no network — so it always runs.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.review import feed as F  # noqa: E402


def test_sort_best_first_then_unscored():
    items = [
        {"id": "a", "fire_score": 40},
        {"id": "b", "fire_score": 90},
        {"id": "c"},                       # unscored -> last
        {"id": "d", "fire_score": 65},
    ]
    order = [it["id"] for it in F.sort_items(items)]
    assert order == ["b", "d", "a", "c"], order


def test_render_contains_each_clip_and_score():
    items = [
        {"id": "hp-x", "brand": "hp", "fire_score": 82, "src": "x.mp4", "text": "fire"},
        {"id": "hp-y", "brand": "hp", "fire_score": 41, "src": "y.mp4", "text": "meh"},
    ]
    out = F.render_review_html(items)
    assert "<!doctype html>" in out.lower()
    assert "hp-x" in out and "hp-y" in out
    assert "82" in out and "41" in out
    # best-first: the 82 card appears before the 41 card.
    assert out.index("hp-x") < out.index("hp-y")
    assert "x.mp4" in out and "KEEP_IDS" in out


def test_render_escapes_html_in_caption():
    out = F.render_review_html(
        [{"id": "z", "brand": "hp", "src": "z.mp4", "text": "<script>alert(1)</script>"}])
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out


def test_render_empty():
    out = F.render_review_html([])
    assert "No clips in review" in out


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
