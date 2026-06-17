"""Transcribe a video into word-level transcript segments.

Produces segments with start/end timing and (ideally) per-word timestamps so the
burn stage can animate captions karaoke-style.

TODO(impl): fill in with faster-whisper or WhisperX.
    - faster-whisper: fast CTranslate2 Whisper backend (segment-level timing).
    - WhisperX: adds accurate word-level alignment (preferred for animation).
    - Extract audio from the video first (ffmpeg) if the backend needs a wav.
    - Honor WHISPER_MODEL / WHISPER_DEVICE / WHISPER_LANGUAGE.
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


def transcribe(video_path: str) -> list[Segment]:
    """Transcribe ``video_path`` into word-level segments.

    Args:
        video_path: Local path to the (clipped) video to transcribe.

    Returns:
        Ordered list of ``Segment`` objects spanning the video.

    TODO(impl): faster-whisper / WhisperX — transcribe + (word) alignment.
    """
    _ = os.getenv("WHISPER_MODEL", "large-v3")
    _ = os.getenv("WHISPER_DEVICE", "cpu")
    raise NotImplementedError("Plug in faster-whisper/WhisperX for word-level segments.")
