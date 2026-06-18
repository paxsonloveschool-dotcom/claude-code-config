"""Tests for the ASS caption builder (pure-Python, no ffmpeg needed)."""

from __future__ import annotations

import sys
from pathlib import Path

# Make the package importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.caption.ass_builder import _fmt_time, build_ass  # noqa: E402
from services.caption.transcribe import Segment, Word  # noqa: E402


def _sample() -> list[Segment]:
    return [
        Segment(
            text="hey there friends",
            start_seconds=0.0,
            end_seconds=1.5,
            words=[
                Word("hey", 0.0, 0.4),
                Word("there", 0.5, 0.9),   # 0.1s gap before -> \k hold
                Word("friends", 0.9, 1.5),
            ],
        ),
        Segment(text="no word timings here", start_seconds=2.0, end_seconds=3.0, words=[]),
    ]


def test_fmt_time():
    assert _fmt_time(0) == "0:00:00.00"
    assert _fmt_time(1.5) == "0:00:01.50"
    assert _fmt_time(65.25) == "0:01:05.25"
    assert _fmt_time(3661.0) == "1:01:01.00"


def test_build_ass_structure():
    ass = build_ass(_sample())
    # Required sections present.
    for section in ("[Script Info]", "[V4+ Styles]", "[Events]"):
        assert section in ass, f"missing {section}"
    # One Dialogue per segment.
    assert ass.count("Dialogue:") == 2
    # 9:16 default resolution.
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass


def test_karaoke_tags():
    ass = build_ass(_sample())
    # Per-word karaoke fill tags emitted from word timings.
    assert "\\kf40}hey" in ass            # 0.4s -> 40cs
    assert "\\kf60}friends" in ass        # 0.6s -> 60cs
    assert "\\k10}" in ass                # 0.1s gap hold before "there"
    # Segment without word timings falls back to plain escaped text.
    assert "no word timings here" in ass


def test_brace_escaping():
    segs = [Segment(text="curly {braces}", start_seconds=0.0, end_seconds=1.0, words=[])]
    ass = build_ass(segs)
    # Literal braces must not leak (they delimit ASS override blocks).
    assert "{braces}" not in ass
    assert "(braces)" in ass


def _parse_dialogue_times(ass: str):
    """Return [(start, end), ...] for each Dialogue line in the script."""
    out = []
    for line in ass.splitlines():
        if line.startswith("Dialogue:"):
            fields = line.split(",", 9)
            out.append((fields[1], fields[2]))
    return out


def test_empty_segments_produce_valid_ass():
    ass = build_ass([])
    for section in ("[Script Info]", "[V4+ Styles]", "[Events]"):
        assert section in ass
    assert ass.count("Dialogue:") == 0
    # Ends cleanly on the events Format line (no dangling blank Dialogue).
    assert ass.endswith("Effect, Text\n")


def test_zero_and_negative_duration_segment_clamped():
    segs = [Segment(text="oops", start_seconds=5.0, end_seconds=2.0, words=[])]
    ass = build_ass(segs)
    (start, end), = _parse_dialogue_times(ass)
    assert start == _fmt_time(5.0)
    assert end >= start  # clamped to start, never before it


def test_out_of_order_words_do_not_emit_bad_tags():
    segs = [
        Segment(
            text="a b c",
            start_seconds=0.0,
            end_seconds=2.0,
            words=[
                Word("a", 0.0, 1.0),
                Word("b", 0.5, 0.5),   # starts before a ends + zero duration
                Word("c", 0.4, 0.4),   # fully out of order + zero duration
            ],
        )
    ]
    ass = build_ass(segs)
    # No negative \k hold and no \kf0 (both invalid / break libass timing).
    assert "\\k-" not in ass
    assert "\\kf0}" not in ass
    assert "\\kf-" not in ass
    for w in ("a", "b", "c"):
        assert f"}}{w} " in ass or ass.rstrip().endswith(w)


def test_empty_word_text_falls_back_to_segment_text():
    segs = [
        Segment(
            text="real text",
            start_seconds=0.0,
            end_seconds=1.0,
            words=[Word("", 0.0, 0.5), Word("   ", 0.5, 1.0)],
        )
    ]
    ass = build_ass(segs)
    assert "real text" in ass


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
