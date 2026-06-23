"""Offline tests for scene/shot splitting (services/score/shots.py).

Synthesizes a deterministic multi-scene video with ffmpeg and checks that
detection + post-processing return usable, contiguous shots. Skips cleanly when
ffmpeg isn't installed so the no-ffmpeg CI test job still passes.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.score import shots as S  # noqa: E402


def _have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _make_three_scene_video(path: str) -> None:
    """3 hard-cut scenes (red, green, blue), 2s each = 6s total, 30fps."""
    parts = []
    tmp = os.path.dirname(path)
    for i, color in enumerate(("red", "green", "blue")):
        p = os.path.join(tmp, f"c{i}.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i",
             f"color=c={color}:s=320x240:d=2:r=30", "-pix_fmt", "yuv420p", p],
            check=True, capture_output=True)
        parts.append(p)
    lst = os.path.join(tmp, "list.txt")
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{p}'\n")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst,
         "-c", "copy", path],
        check=True, capture_output=True)


def test_coalesce_invariants_pure():
    """_coalesce is pure (no ffmpeg) — verify the guarantees directly."""
    dur = 30.0
    shots = S._coalesce([5.0, 5.2, 10.0], dur, min_shot=0.7, max_shot=6.0)
    assert shots, "expected shots"
    # contiguous coverage of [0, dur]
    assert abs(shots[0]["start"]) < 1e-6
    assert abs(shots[-1]["end"] - dur) < 1e-6
    for a, b in zip(shots, shots[1:]):
        assert abs(a["end"] - b["start"]) < 1e-6, "shots must be contiguous"
    # bounds: the 0.2s sliver (5.0->5.2) is merged away; nothing exceeds max_shot
    for s in shots:
        assert s["dur"] >= 0.7 - 1e-6, f"shot too short: {s}"
        assert s["dur"] <= 6.0 + 1e-6, f"shot too long: {s}"
    # indices are sequential
    assert [s["i"] for s in shots] == list(range(len(shots)))


def test_coalesce_splits_long_static():
    """A single long shot with no cuts is split into <=max_shot sub-shots."""
    shots = S._coalesce([], 20.0, min_shot=0.7, max_shot=6.0)
    assert len(shots) >= 4
    assert all(s["dur"] <= 6.0 + 1e-6 for s in shots)
    assert abs(shots[-1]["end"] - 20.0) < 1e-6


def test_detect_shots_on_synthetic_video():
    if not _have_ffmpeg():
        print("  SKIP test_detect_shots_on_synthetic_video (ffmpeg not installed)")
        return
    with tempfile.TemporaryDirectory() as d:
        vid = os.path.join(d, "scenes.mp4")
        _make_three_scene_video(vid)
        assert S.probe_duration(vid) > 5.0
        shots = S.detect_shots(vid, threshold=0.3, min_shot=0.7, max_shot=6.0)
        # 3 distinct color scenes -> detector should find the 2 internal cuts,
        # i.e. ~3 shots. Allow 2..4 for codec/threshold slack.
        assert 2 <= len(shots) <= 4, f"expected ~3 shots, got {len(shots)}: {shots}"
        # contiguous + within bounds
        assert abs(shots[0]["start"]) < 1e-6
        for a, b in zip(shots, shots[1:]):
            assert abs(a["end"] - b["start"]) < 1e-6
        for s in shots:
            assert 0.7 - 1e-6 <= s["dur"] <= 6.0 + 1e-6


def test_detect_shots_missing_file_raises():
    try:
        S.detect_shots("/no/such/file.mp4")
    except FileNotFoundError:
        return
    raise AssertionError("expected FileNotFoundError for a missing file")


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
