"""Offline tests for the locked-style assembly helpers (services/assemble/style.py).

Pure planning/filter helpers always run; the ffmpeg burn-in path is smoke-tested
only when ffmpeg is present (skips cleanly otherwise) so slim CI stays green.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.assemble import style as S  # noqa: E402


def test_plan_layouts_rotation_no_three_cols():
    lay = S.plan_layouts(7)
    assert len(lay) == 7
    assert lay[0] == "rows3" and lay[2] == "single" and lay[3] == "cols2"
    assert "cols3" not in lay  # owner: never 3-columns
    assert S.plan_layouts(0) == []


def test_pick_top_shots_orders_by_time_after_ranking():
    shots = [
        {"start": 0, "end": 3, "fire_score": 40},
        {"start": 3, "end": 6, "fire_score": 95},
        {"start": 6, "end": 9, "fire_score": 80},
        {"start": 9, "end": 12, "fire_score": 10},
    ]
    picked = S.pick_top_shots(shots, k=2)
    # top two by score are the 95 and 80 -> returned in time order
    assert [p["fire_score"] for p in picked] == [95, 80]
    assert picked[0]["start"] < picked[1]["start"]


def test_pick_top_shots_min_gap():
    shots = [
        {"start": 0.0, "fire_score": 90},
        {"start": 0.5, "fire_score": 88},   # too close to the 0.0 pick
        {"start": 5.0, "fire_score": 70},
    ]
    picked = S.pick_top_shots(shots, k=3, min_gap=1.0)
    starts = [p["start"] for p in picked]
    assert 0.0 in starts and 5.0 in starts and 0.5 not in starts


def test_build_serif_filter_word_and_fade():
    beats = [
        {"text": "Excellence Isn't Optional", "start": 0.3, "end": 3.0, "mode": "fade"},
        {"text": "Transform Your Outdoors", "start": 3.0, "end": 6.0, "mode": "word"},
    ]
    flt = S.build_serif_filter(beats)
    assert "drawtext=" in flt
    assert "alpha=" in flt                    # fade beat uses alpha envelope
    assert flt.count("drawtext=") >= 1 + 3    # fade(1) + word reveal(3 words)
    assert "y=h*0.44" in flt                   # centered ~0.44 height


def test_esc_neutralizes_drawtext_specials():
    out = S._esc("a:b'c%d")
    assert ":" not in out.replace("\\:", "") or "\\:" in out
    assert "'" not in out                      # apostrophe swapped for a typographic one


def _ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def test_style_chain_smoke():
    if not _ffmpeg():
        print("  SKIP test_style_chain_smoke (ffmpeg not installed)")
        return
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "src.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i",
             "testsrc=size=1080x1920:duration=4:rate=30", "-pix_fmt", "yuv420p", src],
            check=True, capture_output=True)
        a = os.path.join(d, "a.mp4")
        S.serif_beats(src, a, [{"text": "Hello World", "start": 0.2, "end": 3.5, "mode": "word"}])
        assert os.path.getsize(a) > 0
        b = os.path.join(d, "b.mp4")
        S.add_logo(a, b, logo=None)            # no logo file in temp -> copy path
        assert os.path.getsize(b) > 0
        c = os.path.join(d, "c.mp4")
        S.append_outro(b, c, outro=None)       # no outro -> copy path
        assert os.path.getsize(c) > 0


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
