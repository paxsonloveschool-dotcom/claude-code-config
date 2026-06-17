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
