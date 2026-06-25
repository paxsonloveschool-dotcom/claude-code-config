"""Offline tests for talking-head clip selection + subtitle slicing.

The scorer and segment-slicing are pure (no whisper/ffmpeg) and always run; the
caption burn-in is smoke-tested only when ffmpeg is present.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import automation.video_pipeline as V  # noqa: E402
from services.caption.transcribe import Segment, Word  # noqa: E402


def test_scorer_prefers_complete_quotable_saying():
    strong = V._score_segment_text(
        "Here's the biggest mistake people make: they wait until it's too late. "
        "Do it right the first time.", 13)
    filler = V._score_segment_text(
        "um so yeah like you know we were kind of just and uh", 13)
    assert strong > 1.0
    assert filler <= 0.0            # weak stretch never becomes a clip
    assert strong > filler


def test_scorer_penalizes_dangling_end_and_dead_air():
    dangling = V._score_segment_text("we really wanted to make it good and", 13)
    clean = V._score_segment_text("we really wanted to make it good.", 13)
    assert clean > dangling
    dead_air = V._score_segment_text("so... yeah.", 18)   # 3 words / 18s
    assert dead_air <= 0.0


def _seg(text, s, e, words=None):
    return Segment(text=text, start_seconds=s, end_seconds=e,
                   words=[Word(text=w, start_seconds=ws, end_seconds=we)
                          for w, ws, we in (words or [])])


def test_slice_segments_reties_to_zero():
    segs = [
        _seg("intro", 0.0, 4.0),
        _seg("hello world", 10.0, 13.0,
             [("hello", 10.0, 11.0), ("world", 11.2, 12.8)]),
        _seg("later", 30.0, 33.0),
    ]
    out = V._slice_segments(segs, 9.0, 14.0)
    assert len(out) == 1
    s = out[0]
    assert abs(s.start_seconds - 1.0) < 1e-6      # 10.0 - 9.0
    assert abs(s.end_seconds - 4.0) < 1e-6        # 13.0 - 9.0
    assert [w.text for w in s.words] == ["hello", "world"]
    assert abs(s.words[0].start_seconds - 1.0) < 1e-6


def test_pick_highlights_orders_and_floors():
    segs = [
        _seg("Here's the number one thing that actually matters. Get it right.", 0.0, 13.0),
        _seg("um uh like you know so yeah whatever i guess.", 13.0, 26.0),
        _seg("The biggest secret nobody tells you is consistency wins every time.", 26.0, 39.0),
    ]
    wins = V._pick_highlights(segs, n=3, min_len=6.0, max_len=24.0)
    assert wins, "expected at least one strong window"
    # the pure-filler middle segment should not be a standalone pick
    starts = [a for a, _b, _ in wins]
    assert 13.0 not in starts


def _ffmpeg():
    return shutil.which("ffmpeg") is not None


def test_caption_burn_smoke():
    if not _ffmpeg():
        print("  SKIP test_caption_burn_smoke (ffmpeg not installed)")
        return
    from services.caption.burn import write_ass
    with tempfile.TemporaryDirectory() as d:
        vid = os.path.join(d, "v.mp4")
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                        "color=c=navy:s=1080x1920:d=3:r=30", "-pix_fmt", "yuv420p", vid],
                       check=True, capture_output=True)
        segs = [_seg("hello world this is a test", 0.2, 2.8,
                     [("hello", 0.2, 0.6), ("world", 0.6, 1.0), ("this", 1.0, 1.3),
                      ("is", 1.3, 1.5), ("a", 1.5, 1.6), ("test", 1.6, 2.6)])]
        ass = os.path.join(d, "s.ass")
        write_ass(segs, ass, font="DejaVu Sans", font_size=60)
        out = os.path.join(d, "out.mp4")
        V._burn_ass(vid, ass, out)
        assert os.path.exists(out) and os.path.getsize(out) > 0


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
