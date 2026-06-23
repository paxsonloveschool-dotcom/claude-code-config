"""Tests for the pure helpers in automation/video_pipeline.py. No network/deps."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from automation import video_pipeline as vp  # noqa: E402  (heavy deps are lazy)


@dataclass
class _Seg:
    text: str


def test_slug_is_filesystem_safe_and_bounded():
    assert vp._slug("My Cool Clip!.MOV") == "my-cool-clip"
    assert vp._slug("a/b\\c .mp4").startswith("a-b-c")
    assert len(vp._slug("x" * 100)) <= 40


def test_display_folder_round_trips_brand_keys():
    assert vp.display_folder("hp") == "HP"
    assert vp.display_folder("restore") == "Restore"
    assert vp.display_folder("unknown") == "unknown"  # graceful fallback


def test_transcript_text_joins_segments():
    segs = [_Seg("Hello there."), _Seg(" Spring is here.")]
    assert vp._transcript_text(segs) == "Hello there. Spring is here."


def test_compose_builds_hook_caption_hashtags():
    @dataclass
    class _Copy:
        hook: str
        caption: str
        hashtags: list

    out = vp._compose(_Copy("Big news", "We did a thing.", ["hp", "lawncare"]))
    assert out.startswith("Big news")
    assert "#hp" in out and "#lawncare" in out
    assert "We did a thing." in out


def test_brands_map_folders_to_keys():
    assert vp.BRANDS["HP"][0] == "hp"
    assert vp.BRANDS["Restore"][0] == "restore"


def test_classify_brand_matches_messy_folder_names():
    # tolerant of extra words / spacing the owner might type
    assert vp.classify_brand("HP-Content Auto.")[0] == "hp"
    assert vp.classify_brand("Restore- Content Auto")[0] == "restore"
    assert vp.classify_brand("hp")[0] == "hp"
    # "restore" is checked first so a folder mentioning both routes to restore
    assert vp.classify_brand("Restore")[0] == "restore"
    # unrecognized -> None (skipped, never mis-tagged)
    assert vp.classify_brand("Random Folder") is None


def test_windows_split_into_20s_chunks():
    w = vp._windows(0.0, 71.0, target=20)
    assert len(w) == 4                       # 71s / 20 -> 4 chunks (~18s)
    assert w[0][0] == 0.0 and abs(w[-1][1] - 71.0) < 0.01  # cover full span
    # back-to-back, no overlap
    for (a, b, _l), (a2, b2, _l2) in zip(w, w[1:]):
        assert abs(b - a2) < 0.01
    for a, b, _l in w:
        assert 15 <= (b - a) <= 22           # each near the 20s target
    # a clip already near target stays whole
    assert len(vp._windows(0.0, 18.0, target=20)) == 1
    # a one-minute video -> 3 clean 20s posts
    assert len(vp._windows(0.0, 60.0, target=20)) == 3


def test_speech_bounds_from_segments():
    @dataclass
    class _S:
        start_seconds: float
        end_seconds: float

    s, e = vp._speech_bounds([_S(2.0, 5.0), _S(6.0, 9.0)])
    assert 1.0 <= s <= 2.0          # padded a little before first word
    assert 9.0 <= e <= 9.5          # padded a little after last word


@dataclass
class _Sg:
    text: str
    start_seconds: float
    end_seconds: float


def test_score_rewards_hooks_and_density():
    # a hooky, lively 15s line beats a sparse, filler-y one of the same length
    good = vp._score_segment_text("We finally finished this beautiful backyard reveal", 15.0)
    weak = vp._score_segment_text("um uh like you know i mean", 15.0)
    assert good > weak
    assert vp._score_segment_text("", 10.0) == 0.0
    assert vp._score_segment_text("anything", 0.0) == 0.0


def test_pick_highlights_picks_nonoverlapping_windows_in_range():
    segs = [
        _Sg("What's up nation today we finally finished", 0.0, 4.0),
        _Sg("one of our favorite projects of the year", 4.0, 8.0),
        _Sg("we renovated this entire backyard", 8.0, 12.0),
        _Sg("beautiful stamped concrete patio and walkway", 12.0, 16.0),
        _Sg("and check out this putting green it turned out perfect", 16.0, 22.0),
    ]
    wins = vp._pick_highlights(segs, n=2)
    assert 1 <= len(wins) <= 2
    for a, b, name in wins:
        assert 7.0 <= (b - a) <= 20.0
        assert name.startswith("auto-")
    # non-overlapping
    for (a1, b1, _), (a2, b2, _) in zip(wins, wins[1:]):
        assert b1 <= a2
    # silent footage -> nothing to pick
    assert vp._pick_highlights([], n=4) == []


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
