"""Auto-clip a long-form video into vertical (9:16) shorts — OpusClip-style.

Detects the most clip-worthy moments in a long video and reframes each into a
vertical short suitable for TikTok / Reels / Shorts.

TODO(impl): fill in with ClipsAI or ShortGPT.
    - ClipsAI: transcribe -> `ClipFinder` to detect moments -> `MediaEditor`
      resize/crop to 9:16 (face-tracked reframing).
    - ShortGPT: reuse its engine/editing patterns for the reframe + render.
    - ffmpeg does the actual cut + crop; honor CLIP_MIN/MAX_SECONDS and
      CLIP_ASPECT_RATIO; write outputs to CLIP_OUTPUT_DIR.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Clip:
    """One generated vertical short.

    Attributes:
        source_path: Path to the original long-form video.
        output_path: Path to the rendered 9:16 clip.
        start_seconds: Start offset within the source.
        end_seconds: End offset within the source.
        aspect_ratio: Output aspect ratio (e.g. "9:16").
        score: Optional virality/quality score in [0, 1].
        title: Optional working title for the moment.
    """

    source_path: str
    output_path: str
    start_seconds: float
    end_seconds: float
    aspect_ratio: str = "9:16"
    score: float | None = None
    title: str | None = None


def clip(video_path: str) -> list[Clip]:
    """Cut ``video_path`` into a list of 9:16 vertical shorts.

    Args:
        video_path: Local path to the long-form source video.

    Returns:
        Zero or more ``Clip`` objects, ordered best-first by score when scored.

    TODO(impl): ClipsAI / ShortGPT — moment detection + reframe + render.
    """
    _ = os.getenv("CLIP_ASPECT_RATIO", "9:16")
    _ = os.getenv("CLIP_OUTPUT_DIR", "./media/clips")
    raise NotImplementedError("Plug in ClipsAI/ShortGPT clip detection + 9:16 reframe.")
