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


def test_windows_make_ten_varied_cuts():
    w = vp._windows(0.0, 60.0)
    labels = [lbl for _a, _b, lbl in w]
    assert labels[0] == "full"
    assert len(w) == 10  # full + halves + thirds + quarters
    # lengths span short to long
    lengths = sorted(round(b - a) for a, b, _l in w)
    assert lengths[0] == 15 and lengths[-1] == 60
    # a very short clip just yields the full cut
    assert vp._windows(0.0, 1.0) == [(0.0, 1.0, "full")]


def test_speech_bounds_from_segments():
    @dataclass
    class _S:
        start_seconds: float
        end_seconds: float

    s, e = vp._speech_bounds([_S(2.0, 5.0), _S(6.0, 9.0)])
    assert 1.0 <= s <= 2.0          # padded a little before first word
    assert 9.0 <= e <= 9.5          # padded a little after last word


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
