"""Offline tests for the visual scoring brain (services/score/visual.py).

combine() is pure and always tested. The frame-metric path needs ffmpeg + Pillow
and is skipped cleanly when ffmpeg is absent so the slim CI job stays green.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.score import visual as V  # noqa: E402


def test_combine_is_zero_to_100_and_monotonic():
    lo = V.combine({"sharpness": 0, "exposure": 0, "motion": 0, "colorfulness": 0})
    hi = V.combine({"sharpness": 1, "exposure": 1, "motion": 1, "colorfulness": 1})
    assert lo == 0.0
    assert hi == 100.0
    mid = V.combine({"sharpness": 0.5, "exposure": 0.5, "motion": 0.5, "colorfulness": 0.5})
    assert lo < mid < hi


def test_combine_redistributes_missing_clip_weight():
    """With no clip metric, a perfect heuristic shot still scores 100 (weight
    is redistributed, not left as dead weight)."""
    s = V.combine({"sharpness": 1, "exposure": 1, "motion": 1, "colorfulness": 1})
    assert s == 100.0
    # clip present and bad should pull a perfect shot down.
    s2 = V.combine({"sharpness": 1, "exposure": 1, "motion": 1, "colorfulness": 1,
                    "clip": 0.0})
    assert s2 < 100.0


def test_combine_clamps_out_of_range():
    s = V.combine({"sharpness": 5, "exposure": -3})
    assert 0.0 <= s <= 100.0


def test_combine_empty_metrics():
    assert V.combine({}) == 0.0


def test_get_scorer_defaults_to_heuristic():
    assert V.get_scorer().name == "heuristic"
    assert V.get_scorer("nonexistent").name == "heuristic"


def _ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def _make_clip(path: str, color: str, dur: float = 2.0) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i",
         f"testsrc=size=320x240:duration={dur}:rate=30", "-pix_fmt", "yuv420p", path],
        check=True, capture_output=True)


def test_score_shot_real_clip():
    if not _ffmpeg():
        print("  SKIP test_score_shot_real_clip (ffmpeg not installed)")
        return
    with tempfile.TemporaryDirectory() as d:
        vid = os.path.join(d, "t.mp4")
        _make_clip(vid, "testsrc")
        m = V.score_shot(vid, 0.0, 2.0, samples=4)
        for k in ("sharpness", "exposure", "motion", "colorfulness", "fire_score"):
            assert k in m, f"missing {k}"
        assert 0.0 <= m["fire_score"] <= 100.0
        # testsrc is a busy, colourful pattern -> should not score rock-bottom.
        assert m["fire_score"] > 0.0


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
