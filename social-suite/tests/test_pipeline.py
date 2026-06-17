"""Tests for pipeline stage-chaining robustness (no heavy deps, no network).

We monkeypatch the stage functions the pipeline imports so we can exercise the
real chaining logic — in particular that a stage returning EMPTY (no new files,
no clips, no segments) flows through without crashing and reports a sane count.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.orchestrator import pipeline  # noqa: E402


def _patch(stage_overrides: dict):
    """Apply name->callable overrides onto the pipeline module; return restorer."""
    originals = {name: getattr(pipeline, name) for name in stage_overrides}
    for name, fn in stage_overrides.items():
        setattr(pipeline, name, fn)

    def restore():
        for name, fn in originals.items():
            setattr(pipeline, name, fn)

    return restore


def test_dry_run_does_not_touch_stages():
    out = pipeline.run_pipeline(dry_run=True)
    assert out["status"] == "ok"
    assert out["dry_run"] is True
    assert out["processed"] == 0


def test_no_new_files_publishes_nothing():
    restore = _patch(
        {
            "list_new_files": lambda *a, **k: ([], None),
            # None of the others should be called.
            "download": lambda *a, **k: (_ for _ in ()).throw(AssertionError("download")),
            "clip": lambda *a, **k: (_ for _ in ()).throw(AssertionError("clip")),
        }
    )
    try:
        out = pipeline.run_pipeline(dry_run=False)
    finally:
        restore()
    assert out["status"] == "ok"
    assert out["published"] == 0


def test_file_with_no_clips_does_not_crash():
    f = object()
    restore = _patch(
        {
            "list_new_files": lambda *a, **k: ([f], "cur"),
            "download": lambda x: "/tmp/raw.mp4",
            "clip": lambda x: [],  # no clip-worthy moments
            # downstream stages must never be reached on an empty clip list.
            "transcribe": lambda *a, **k: (_ for _ in ()).throw(AssertionError("transcribe")),
            "schedule_post": lambda *a, **k: (_ for _ in ()).throw(AssertionError("post")),
        }
    )
    try:
        out = pipeline.run_pipeline(dry_run=False)
    finally:
        restore()
    assert out["published"] == 0


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
