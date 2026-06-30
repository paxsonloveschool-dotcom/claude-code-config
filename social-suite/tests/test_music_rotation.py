"""Tests for the per-clip background-music rotation (no Dropbox/ffmpeg needed)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from automation.video_pipeline import _music_rotation  # noqa: E402

SONGS = [f"song{i}.mp3" for i in range(1, 6)]


def test_empty_tracks_returns_empty():
    # No Music folder / no songs -> no rotation -> clips keep original audio.
    assert _music_rotation([], "any-video") == []


def test_keeps_every_track():
    # Shuffle must not drop or duplicate any song.
    assert sorted(_music_rotation(SONGS, "vid-A")) == sorted(SONGS)


def test_deterministic_per_video():
    # Same video name -> same order every run (reproducible).
    assert _music_rotation(SONGS, "vid-A") == _music_rotation(SONGS, "vid-A")


def test_varies_between_videos():
    # Different videos should (almost always) get a different order.
    assert _music_rotation(SONGS, "vid-A") != _music_rotation(SONGS, "vid-B")


def test_cycle_uses_all_then_loops():
    # 12 clips over 5 songs: each song appears, and it wraps around.
    rot = _music_rotation(SONGS, "vid")
    seq = [rot[i % len(rot)] for i in range(12)]
    assert set(seq) == set(SONGS)
    assert seq[:5] == rot  # first pass is the full rotation, in order
