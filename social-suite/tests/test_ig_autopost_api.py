"""Tests for the internet-based (Dropbox API) Instagram poster — pure, no network."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from automation.ig_autopost_api import (  # noqa: E402
    BRANDS_PATH,
    build_caption,
    caption_sidecar,
    clip_number,
    is_video,
    load_brand,
    load_state,
    next_clip,
    resolve_folder,
    save_state,
    talk_override,
)


@dataclass
class F:
    name: str
    path: str = ""


def test_clip_number_parses_leading_number():
    assert clip_number("1.mp4") == 1
    assert clip_number("10 talk.mp4") == 10
    assert clip_number("reel-resort.mp4") is None


def test_next_clip_smallest_above_last_numeric():
    files = [F("10.mp4"), F("2.mp4"), F("1.mp4"), F("4 talk.mp4")]
    assert next_clip(files, 0)[0] == 1
    assert next_clip(files, 2)[0] == 4            # numeric: 4 before 10
    assert next_clip(files, 10) == (None, None)   # nothing above 10


def test_is_video():
    assert is_video("3.MP4") and is_video("x.mov") and is_video("y.m4v")
    assert not is_video("3.txt") and not is_video("notes")


def test_caption_sidecar_matches_by_number():
    files = [F("5.mp4"), F("5.txt"), F("6.mp4")]
    assert caption_sidecar(files, 5).name == "5.txt"
    assert caption_sidecar(files, 6) is None      # no 6.txt


def test_talk_override_name_and_folder():
    assert talk_override("7 talk.mp4") is False                       # name says talk
    assert talk_override("7.mp4", "/HP/Talking Videos/7.mp4") is False  # folder says talk
    assert talk_override("8 song.mp4") is True                        # forced song
    assert talk_override("8.mp4", "/HP/Reels/8.mp4") is None          # undecided -> VAD


def test_build_caption_variants():
    assert build_caption("Hook", "#a #b") == "Hook\n\n#a #b"
    assert build_caption("Hook", "#a", cta="Call us") == "Hook\n\nCall us\n\n#a"
    # custom with no hashtags gets tags appended; custom with its own tags doesn't
    assert build_caption("Hook", "#a", custom="My caption") == "My caption\n\n#a"
    assert build_caption("Hook", "#a", custom="My caption #own") == "My caption #own"


def test_brands_config_is_valid():
    brands = json.load(open(BRANDS_PATH, encoding="utf-8"))
    assert {"hp", "trophy"} <= set(brands)
    for name, cfg in brands.items():
        assert cfg["songs"] and cfg["hooks"] and cfg["tags"], name
        assert cfg.get("folder") or cfg.get("folder_match"), name
    # Trophy posts only from its one queue folder in the team namespace.
    assert brands["trophy"]["folder"] == "/TROPHY EXTERIOR/Trophy Social Auto"
    assert brands["trophy"]["root_namespace_id"] == "13679018067"
    # No two consecutive Trophy hooks are identical (variety requirement).
    h = brands["trophy"]["hooks"]
    assert len(h) == len(set(h)) >= 40


def test_load_brand_unknown_raises():
    try:
        load_brand("nope")
    except SystemExit:
        return
    raise AssertionError("unknown brand should raise SystemExit")


def test_state_roundtrip_and_default():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "sub", "hp_ig_state.json")
        assert load_state(p) == {"last_num": 0, "i": 0}   # missing -> default
        save_state(p, {"last_num": 7, "i": 3})
        assert load_state(p) == {"last_num": 7, "i": 3}


# ---- resolve_folder with a fake Dropbox client (no network) ---------------

class _Folder:
    def __init__(self, path):
        self.path_display = path
        self.path_lower = path.lower()
        self.name = path.rstrip("/").split("/")[-1]


class _Res:
    def __init__(self, entries, has_more=False, cursor=""):
        self.entries = entries
        self.has_more = has_more
        self.cursor = cursor


class _FakeClient:
    def __init__(self, folders):
        self._folders = folders

    def files_list_folder(self, path):
        return _Res([_Folder(f) for f in self._folders])

    def files_list_folder_continue(self, cursor):
        return _Res([])


class _FakeDbx:
    def __init__(self, folders):
        self._c = _FakeClient(folders)

    def _client(self):
        return self._c


def test_resolve_folder_fixed_path_short_circuits():
    assert resolve_folder(_FakeDbx([]), {"folder": "/TROPHY EXTERIOR/Trophy Social Auto"}) == \
        "/TROPHY EXTERIOR/Trophy Social Auto"


def test_resolve_folder_matches_by_name():
    dbx = _FakeDbx(["/Restore Marketing", "/Apps/x/HP Auto Post", "/Other"])
    got = resolve_folder(dbx, {"folder_match": ["hp", "auto", "post"]})
    assert got == "/apps/x/hp auto post"   # path_lower of the matching folder


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
