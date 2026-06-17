"""Transcribe a video into word-level transcript segments.

Produces segments with start/end timing and per-word timestamps so the burn
stage can animate captions karaoke-style.

Backend: ``faster-whisper`` (CTranslate2 Whisper) run with
``word_timestamps=True`` for per-word timing. Honors ``WHISPER_MODEL`` /
``WHISPER_DEVICE`` / ``WHISPER_LANGUAGE`` from the environment. faster-whisper
reads audio straight from the video via its bundled ffmpeg/av, so no separate
extraction step is required.

The ``faster_whisper`` package is imported lazily inside ``transcribe`` so this
module imports cleanly without the (heavy) dependency installed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Word:
    """A single word with timing (for karaoke-style animation).

    Attributes:
        text: The word.
        start_seconds: Word start time.
        end_seconds: Word end time.
    """

    text: str
    start_seconds: float
    end_seconds: float


@dataclass
class Segment:
    """A transcript segment (a line/phrase of captions).

    Attributes:
        text: Full segment text.
        start_seconds: Segment start time.
        end_seconds: Segment end time.
        words: Optional per-word timings; empty if the backend is segment-only.
    """

    text: str
    start_seconds: float
    end_seconds: float
    words: list[Word] = field(default_factory=list)


def _build_model():
    """Construct a faster-whisper ``WhisperModel`` from env config."""
    from faster_whisper import WhisperModel  # lazy: heavy dep

    model_size = os.getenv("WHISPER_MODEL", "large-v3")
    device = os.getenv("WHISPER_DEVICE", "cpu")
    # int8 is the right default for CPU; float16 is typical on GPU.
    compute_type = os.getenv(
        "WHISPER_COMPUTE_TYPE", "int8" if device == "cpu" else "float16"
    )
    return WhisperModel(model_size, device=device, compute_type=compute_type)


def transcribe(video_path: str) -> list[Segment]:
    """Transcribe ``video_path`` into word-level segments.

    Args:
        video_path: Local path to the (clipped) video to transcribe.

    Returns:
        Ordered list of ``Segment`` objects spanning the video.
    """
    model = _build_model()

    language = os.getenv("WHISPER_LANGUAGE", "auto")
    kwargs: dict = {"word_timestamps": True}
    if language and language != "auto":
        kwargs["language"] = language

    raw_segments, _info = model.transcribe(video_path, **kwargs)

    segments: list[Segment] = []
    for seg in raw_segments:
        words: list[Word] = []
        for w in getattr(seg, "words", None) or []:
            words.append(
                Word(
                    text=getattr(w, "word", "") or "",
                    start_seconds=float(getattr(w, "start", 0.0) or 0.0),
                    end_seconds=float(getattr(w, "end", 0.0) or 0.0),
                )
            )
        segments.append(
            Segment(
                text=(getattr(seg, "text", "") or "").strip(),
                start_seconds=float(getattr(seg, "start", 0.0) or 0.0),
                end_seconds=float(getattr(seg, "end", 0.0) or 0.0),
                words=words,
            )
        )
    return segments
