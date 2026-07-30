"""Offline tests for the cloud Instagram poster (no network, no posting)."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation import ig_autopost_cloud as ig  # noqa: E402


def test_caption_rotates_and_includes_cta_and_tags():
    caps = [ig.caption_for(n) for n in range(len(ig.HOOKS) + 1)]
    # Every caption carries the phone CTA and the hashtag block.
    assert all(ig.CTA in c for c in caps)
    assert all("#fyp" in c for c in caps)
    # Hooks cycle: caption_for(0) and caption_for(len(HOOKS)) share the same hook.
    assert caps[0].split("\n")[0] == caps[len(ig.HOOKS)].split("\n")[0]
    # Adjacent captions use different hooks.
    assert caps[0].split("\n")[0] != caps[1].split("\n")[0]


def test_state_round_trip(tmp_path=None):
    d = tempfile.mkdtemp()
    orig = ig.STATE_PATH
    try:
        ig.STATE_PATH = os.path.join(d, "ig_posted.json")
        assert ig.load_state() == {"last_num": 0}      # missing file -> default
        ig.save_state({"last_num": 7})
        assert ig.load_state() == {"last_num": 7}
    finally:
        ig.STATE_PATH = orig


def test_reuses_facebook_clip_selection():
    # The cloud IG poster must share Facebook's next-number logic verbatim.
    from automation import fb_autopost
    assert ig.next_clip is fb_autopost.next_clip
    assert ig.POST_WEEKDAYS == fb_autopost.POST_WEEKDAYS == (0, 2, 4)


def _run():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")


if __name__ == "__main__":
    _run()
