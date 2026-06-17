"""Burn animated captions/text into a video.

Renders transcript segments as styled, word-by-word animated captions (via
``ass_builder``) and burns them into the pixels with ffmpeg/libass, so they
survive re-encoding and show in every platform player.

The ASS generation (``ass_builder.build_ass``) is pure Python and unit-tested;
only the final burn-in shells out to ffmpeg at runtime.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from .ass_builder import build_ass

if TYPE_CHECKING:
    from .transcribe import Segment


def write_ass(segments: "list[Segment]", out_path: str, **style) -> str:
    """Render ``segments`` to an ASS file at ``out_path``. Returns the path."""
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(build_ass(segments, **style), encoding="utf-8")
    return out_path


def burn_captions(video_path: str, segments: "list[Segment]") -> str:
    """Burn animated captions onto ``video_path``.

    Builds an ASS subtitle file from the word-level segments, then burns it in:
        ffmpeg -i in.mp4 -vf "ass=subs.ass" -c:a copy out.mp4

    Args:
        video_path: Path to the clip to caption.
        segments: Word-level transcript segments from ``transcribe``.

    Returns:
        Path to the new video with captions burned in.
    """
    ffmpeg = os.getenv("FFMPEG_BINARY", "ffmpeg")
    out_dir = os.getenv("CAPTION_OUTPUT_DIR", "./media/captioned")
    font = os.getenv("CAPTION_FONT", "Arial")
    font_size = int(os.getenv("CAPTION_FONT_SIZE", "64"))

    stem = Path(video_path).stem
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    ass_path = str(Path(out_dir) / f"{stem}.ass")
    out_path = str(Path(out_dir) / f"{stem}_captioned.mp4")

    write_ass(segments, ass_path, font=font, font_size=font_size)

    # libass needs the ASS path escaped for the filtergraph.
    safe = ass_path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    cmd = [
        ffmpeg, "-y", "-i", video_path,
        "-vf", f"ass={safe}",
        "-c:a", "copy",
        out_path,
    ]
    subprocess.run(cmd, check=True)
    return out_path
