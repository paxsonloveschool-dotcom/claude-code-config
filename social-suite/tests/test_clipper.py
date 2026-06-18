"""Tests for the auto-clipper (no whisper, no ffmpeg, no network).

``select_highlights`` and ``build_ffmpeg_cmd`` are pure, so they're tested
directly. ``clip`` is tested with ``transcribe`` and ``subprocess.run``
monkeypatched, so no model loads and no encoder runs.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.clip import clipper  # noqa: E402
from services.clip.clipper import (  # noqa: E402
    Clip,
    build_ffmpeg_cmd,
    select_highlights,
)


class _Seg:
    """Minimal stand-in for caption.transcribe.Segment."""

    def __init__(self, start, end, text=""):
        self.start_seconds = start
        self.end_seconds = end
        self.text = text


def _segments(step=10.0, n=12):
    return [_Seg(i * step, i * step + step, f"seg {i}") for i in range(n)]


def test_select_highlights_respects_bounds():
    ranges = select_highlights(_segments(), min_seconds=15, max_seconds=60)
    assert ranges, "expected at least one highlight"
    for start, end in ranges:
        dur = end - start
        assert dur >= 15 - 1e-9
        assert dur <= 60 + 1e-9


def test_select_highlights_respects_max_clips():
    ranges = select_highlights(_segments(n=60), max_clips=3, min_seconds=15, max_seconds=30)
    assert len(ranges) <= 3


def test_select_highlights_is_ordered_and_non_overlapping():
    ranges = select_highlights(_segments(n=60), max_clips=5, min_seconds=15, max_seconds=30)
    for i in range(1, len(ranges)):
        # Ordered by start, and the previous clip ends before the next begins.
        assert ranges[i][0] >= ranges[i - 1][0]
        assert ranges[i][0] >= ranges[i - 1][1] - 1e-9


def test_select_highlights_empty_and_zero_clips():
    assert select_highlights([], min_seconds=15, max_seconds=60) == []
    assert select_highlights(_segments(), max_clips=0) == []


def test_select_highlights_skips_too_short_transcript():
    # Only 8s of content but a 15s minimum -> nothing qualifies.
    short = [_Seg(0.0, 4.0), _Seg(4.0, 8.0)]
    assert select_highlights(short, min_seconds=15, max_seconds=60) == []


def test_build_ffmpeg_cmd_shape():
    cmd = build_ffmpeg_cmd("/in/src.mp4", 12.0, 42.0, "/out/clip1.mp4")
    # Source input present.
    assert "/in/src.mp4" in cmd
    assert "-i" in cmd
    # Time selection via -ss / -to.
    assert "-ss" in cmd
    assert "-to" in cmd
    assert cmd[cmd.index("-ss") + 1].startswith("12")
    assert cmd[cmd.index("-to") + 1].startswith("42")
    # 9:16 reframe filter: scale to cover + center crop.
    vf = cmd[cmd.index("-vf") + 1]
    assert "scale=1080:1920" in vf
    assert "force_original_aspect_ratio=increase" in vf
    assert "crop=1080:1920" in vf
    # Output path is last.
    assert cmd[-1] == "/out/clip1.mp4"


def test_build_ffmpeg_cmd_honors_ffmpeg_binary(monkeypatch=None):
    import os

    os.environ["FFMPEG_BINARY"] = "/custom/ffmpeg"
    try:
        cmd = build_ffmpeg_cmd("/in.mp4", 0.0, 20.0, "/out.mp4")
    finally:
        os.environ.pop("FFMPEG_BINARY", None)
    assert cmd[0] == "/custom/ffmpeg"


def test_clip_end_to_end_mocked():
    import os
    import tempfile

    calls = {"transcribe": 0, "subprocess": []}

    def _fake_transcribe(path):
        calls["transcribe"] += 1
        return _segments(n=12)

    def _fake_run(cmd, *a, **k):
        calls["subprocess"].append(cmd)

        class _R:
            returncode = 0

        return _R()

    # Patch the function the clipper imports lazily + subprocess.run.
    import importlib

    tmod = importlib.import_module("services.caption.transcribe")
    orig_t = tmod.transcribe
    orig_run = clipper.subprocess.run
    tmod.transcribe = _fake_transcribe
    clipper.subprocess.run = _fake_run

    tmpdir = tempfile.mkdtemp()
    os.environ["CLIP_OUTPUT_DIR"] = tmpdir
    os.environ["CLIP_MAX_CLIPS"] = "2"
    try:
        clips = clipper.clip("/videos/long_source.mp4")
    finally:
        tmod.transcribe = orig_t
        clipper.subprocess.run = orig_run
        os.environ.pop("CLIP_OUTPUT_DIR", None)
        os.environ.pop("CLIP_MAX_CLIPS", None)

    assert calls["transcribe"] == 1
    assert 1 <= len(clips) <= 2
    assert len(calls["subprocess"]) == len(clips)
    for c in clips:
        assert isinstance(c, Clip)
        assert c.source_path == "/videos/long_source.mp4"
        assert c.output_path.startswith(tmpdir)
        assert c.aspect_ratio == "9:16"
        assert c.end_seconds > c.start_seconds
    # The ffmpeg command actually targets each output path.
    out_paths = {c.output_path for c in clips}
    cmd_outs = {cmd[-1] for cmd in calls["subprocess"]}
    assert out_paths == cmd_outs


def test_clip_no_highlights_returns_empty():
    import importlib

    tmod = importlib.import_module("services.caption.transcribe")

    def _fake_transcribe(path):
        return [_Seg(0.0, 3.0), _Seg(3.0, 6.0)]  # too short for min 15s

    def _boom_run(*a, **k):
        raise AssertionError("ffmpeg must not run when there are no highlights")

    orig_t = tmod.transcribe
    orig_run = clipper.subprocess.run
    tmod.transcribe = _fake_transcribe
    clipper.subprocess.run = _boom_run
    try:
        clips = clipper.clip("/videos/tiny.mp4")
    finally:
        tmod.transcribe = orig_t
        clipper.subprocess.run = orig_run

    assert clips == []


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
