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


def test_pick_highlights_packs_multiple_from_long_video():
    # A long talking video with three strong, separated sayings. With a tighter
    # window cap (owner: "more than 6 clips from 5 videos") the picker must return
    # MULTIPLE non-overlapping clips, not one big window that eats the timeline.
    segs = [
        _seg("Here's the number one mistake people make every single time they start.", 0.0, 14.0),
        _seg("um so yeah like you know whatever i guess it doesn't really matter.", 14.0, 26.0),
        _seg("The biggest secret nobody tells you is that consistency wins every time.", 26.0, 40.0),
        _seg("um uh and then so basically you just kind of keep going i think.", 40.0, 52.0),
        _seg("Do it right the first time and you never have to do it twice, period.", 52.0, 66.0),
    ]
    wins = V._pick_highlights(segs, n=12, min_len=6.0, max_len=28.0, min_score=0.4)
    assert len(wins) >= 3, f"expected >=3 packed clips, got {wins}"
    for _a, b, _ in wins:
        assert b - _a <= 28.0 + 1e-6      # honors the tighter window cap


def test_trim_to_clean_strips_filler_edges():
    segs = [_seg("um so today we install drainage and", 0.0, 5.0,
                 [("um", 0.0, 0.3), ("so", 0.3, 0.6), ("today", 0.6, 1.0),
                  ("we", 1.0, 1.2), ("install", 1.2, 1.8), ("drainage", 1.8, 2.5),
                  ("and", 2.5, 2.8)])]
    a, b = V._trim_to_clean(segs, 0.0, 5.0)
    assert a >= 0.5 and a < 0.7      # starts at "today", not "um/so"
    assert 2.4 < b < 2.7             # ends at "drainage", not "and"


def test_trim_drops_stutter_repeat():
    segs = [_seg("the the yard looks great", 0.0, 3.0,
                 [("the", 0.0, 0.3), ("the", 0.3, 0.6), ("yard", 0.6, 1.0),
                  ("looks", 1.0, 1.4), ("great", 1.4, 2.0)])]
    a, _b = V._trim_to_clean(segs, 0.0, 3.0)
    assert a >= 0.2                  # past the first "the" (>=0.3 minus the small pad)


def test_clip_pieces_drops_weak_middle():
    strong1 = _seg("Here is the number one thing that matters get it right.", 0.0, 6.0)
    weak = _seg("um uh like you know so yeah whatever.", 6.0, 12.0)
    strong2 = _seg("The biggest secret is consistency wins every single time.", 12.0, 18.0)
    pieces = V._clip_pieces([strong1, weak, strong2], 0.0, 18.0, drop_below=0.2)
    assert pieces == [(0.0, 6.0), (12.0, 18.0)]   # boring 6-12s middle cut out


def test_clip_pieces_all_good_is_one_run():
    s1 = _seg("Here is the number one thing that actually matters a lot.", 0.0, 6.0)
    s2 = _seg("And the biggest secret is consistency wins every time.", 6.0, 12.0)
    pieces = V._clip_pieces([s1, s2], 0.0, 12.0, drop_below=0.2)
    assert len(pieces) == 1 and pieces[0][0] == 0.0


def test_extend_to_sentence_end_completes_thought():
    # Window ends mid-thought (no terminal punctuation); the next segment finishes
    # the sentence with a small gap -> b should extend to include it.
    segs = [
        _seg("here is the number one thing that matters", 0.0, 6.0),
        _seg("you have to do it right.", 6.2, 9.0),
        _seg("and later we talk about something else.", 14.0, 18.0),
    ]
    nb = V._extend_to_sentence_end(segs, 0.0, 6.0, hard_max=30.0)
    assert abs(nb - 9.0) < 1e-6                 # pulled in the finishing segment
    # A real pause (>0.8s) is a natural stop — don't jump it.
    nb2 = V._extend_to_sentence_end(segs, 0.0, 9.0, hard_max=30.0)
    assert abs(nb2 - 9.0) < 1e-6                # 9.0 already ends with "."


def test_clip_pieces_keeps_last_weak_segment():
    # A weak trailing beat must NOT be dropped (that caused clips to end early).
    strong = _seg("Here is the number one thing that actually matters a lot.", 0.0, 6.0)
    weak_tail = _seg("you know.", 6.1, 7.2)
    pieces = V._clip_pieces([strong, weak_tail], 0.0, 7.2, drop_below=0.2)
    assert pieces and abs(pieces[-1][1] - 7.2) < 1e-6   # clip still ends at the end


def test_shift_segments_offsets_words():
    segs = [_seg("hello world", 0.0, 1.0, [("hello", 0.0, 0.5), ("world", 0.5, 1.0)])]
    out = V._shift_segments(segs, 3.0)
    assert abs(out[0].start_seconds - 3.0) < 1e-6
    assert abs(out[0].words[0].start_seconds - 3.0) < 1e-6


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
