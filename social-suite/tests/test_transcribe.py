"""Tests for faster-whisper transcription mapping (no model, no install needed).

We inject a fake ``faster_whisper`` module whose ``WhisperModel.transcribe``
yields fake segments/words, then assert they map into ``Segment``/``Word`` and
that ``word_timestamps=True`` (and env config) are passed through.
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.caption import transcribe as T  # noqa: E402
from services.caption.transcribe import Segment, Word, transcribe  # noqa: E402


class _FakeWord:
    def __init__(self, word, start, end):
        self.word = word
        self.start = start
        self.end = end


class _FakeSegment:
    def __init__(self, text, start, end, words):
        self.text = text
        self.start = start
        self.end = end
        self.words = words


class _FakeInfo:
    language = "en"


class _FakeModel:
    instances: list = []

    def __init__(self, model_size, device="cpu", compute_type="int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.transcribe_kwargs = None
        self.transcribe_path = None
        _FakeModel.instances.append(self)

    def transcribe(self, video_path, **kwargs):
        self.transcribe_path = video_path
        self.transcribe_kwargs = kwargs

        def _gen():
            yield _FakeSegment(
                " hey there ",
                0.0,
                1.5,
                [_FakeWord("hey", 0.0, 0.4), _FakeWord("there", 0.5, 0.9)],
            )
            yield _FakeSegment("done", 2.0, 3.0, [])

        return _gen(), _FakeInfo()


def _install_fake_fw():
    mod = types.ModuleType("faster_whisper")
    mod.WhisperModel = _FakeModel
    sys.modules["faster_whisper"] = mod
    _FakeModel.instances = []
    return mod


def test_maps_segments_and_words():
    _install_fake_fw()
    os.environ["WHISPER_MODEL"] = "small"
    os.environ["WHISPER_DEVICE"] = "cpu"
    os.environ["WHISPER_LANGUAGE"] = "auto"

    segs = transcribe("/tmp/clip.mp4")

    assert len(segs) == 2
    assert all(isinstance(s, Segment) for s in segs)

    s0 = segs[0]
    assert s0.text == "hey there"  # stripped
    assert s0.start_seconds == 0.0 and s0.end_seconds == 1.5
    assert len(s0.words) == 2
    assert all(isinstance(w, Word) for w in s0.words)
    assert s0.words[0].text == "hey"
    assert s0.words[0].start_seconds == 0.0 and s0.words[0].end_seconds == 0.4
    assert s0.words[1].text == "there"

    # Segment with no words maps to empty list.
    assert segs[1].text == "done"
    assert segs[1].words == []


def test_passes_word_timestamps_and_env():
    _install_fake_fw()
    os.environ["WHISPER_MODEL"] = "medium"
    os.environ["WHISPER_DEVICE"] = "cpu"
    os.environ["WHISPER_LANGUAGE"] = "es"

    transcribe("/tmp/x.mp4")
    model = _FakeModel.instances[-1]

    assert model.model_size == "medium"
    assert model.device == "cpu"
    assert model.compute_type == "int8"  # cpu default
    assert model.transcribe_kwargs["word_timestamps"] is True
    # Explicit language passed when not "auto".
    assert model.transcribe_kwargs["language"] == "es"
    assert model.transcribe_path == "/tmp/x.mp4"


def test_auto_language_omitted():
    _install_fake_fw()
    os.environ["WHISPER_LANGUAGE"] = "auto"
    os.environ["WHISPER_DEVICE"] = "cpu"
    transcribe("/tmp/x.mp4")
    model = _FakeModel.instances[-1]
    assert "language" not in model.transcribe_kwargs


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
