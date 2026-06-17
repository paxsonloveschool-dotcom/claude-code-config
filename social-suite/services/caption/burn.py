"""Burn animated captions/text into a video.

Renders transcript segments as styled, animated captions and burns them into the
pixels (so they survive re-encoding and platform players).

TODO(impl): fill in with ffmpeg + libass.
    - Generate an ASS subtitle file from the segments. For karaoke/word-by-word
      animation, emit per-word `\\k` timing tags using Segment.words.
    - Burn with: ffmpeg -i in.mp4 -vf "ass=subs.ass" -c:a copy out.mp4
    - Honor CAPTION_FONT / CAPTION_FONT_SIZE / CAPTION_STYLE; write to
      CAPTION_OUTPUT_DIR; use FFMPEG_BINARY.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .transcribe import Segment


def burn_captions(video_path: str, segments: "list[Segment]") -> str:
    """Burn animated captions onto ``video_path``.

    Args:
        video_path: Path to the clip to caption.
        segments: Word-level transcript segments from ``transcribe``.

    Returns:
        Path to the new video with captions burned in.

    TODO(impl): ffmpeg + libass — build ASS (karaoke \\k tags) then burn.
    """
    _ = os.getenv("FFMPEG_BINARY", "ffmpeg")
    _ = os.getenv("CAPTION_STYLE", "karaoke")
    _ = os.getenv("CAPTION_OUTPUT_DIR", "./media/captioned")
    raise NotImplementedError("Render ASS captions and burn with ffmpeg/libass.")
