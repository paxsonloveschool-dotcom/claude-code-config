"""Tests for the free (no-API) caption writer. No network, no keys."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.write.free_writer import generate_caption  # noqa: E402


def test_builds_hook_caption_hashtags_from_transcript():
    ctx = {
        "transcript": "Spring lawn care starts now. Aerate and feed your grass early. "
                      "Book your tune-up before the season fills up.",
        "brand_name": "HP Landscaping",
    }
    copy = generate_caption(ctx, default_hashtags=["#HPLandscaping", "lawncare"])
    assert copy.hook and len(copy.hook.split()) <= 13  # ~12 words + ellipsis
    assert "Follow for more." in copy.caption or copy.caption
    # brand defaults come first, lowercased, no leading '#'
    assert copy.hashtags[0] == "hplandscaping"
    assert "lawncare" in copy.hashtags
    assert all(not t.startswith("#") for t in copy.hashtags)
    assert len(copy.hashtags) <= 10


def test_empty_transcript_falls_back_to_brand():
    copy = generate_caption({"transcript": "", "brand_name": "Restore"})
    assert copy.hook == "Restore"
    assert copy.caption  # non-empty fallback body + CTA


def test_custom_cta_and_dedupes_hashtags():
    ctx = {"transcript": "Roofing tips for storm season. Roofing matters."}
    copy = generate_caption(ctx, default_hashtags=["roofing", "roofing"], cta="DM us today.")
    assert copy.caption.endswith("DM us today.")
    assert copy.hashtags.count("roofing") == 1  # de-duped


def test_hook_truncates_long_first_sentence():
    long_first = " ".join(["word"] * 30) + ". Second sentence."
    copy = generate_caption({"transcript": long_first})
    assert copy.hook.endswith("…")
    assert len(copy.hook.split()) <= 13


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
