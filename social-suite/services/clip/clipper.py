"""Auto-clip a long-form video into vertical (9:16) shorts — OpusClip-style.

Detects the most clip-worthy moments in a long video and reframes each into a
vertical short suitable for TikTok / Reels / Shorts.

Harvests the MIT ``ai-youtube-shorts-generator`` approach (RESEARCH.md):
    1. Transcribe the source (reuse ``services.caption.transcribe.transcribe``)
       to get word-level segments.
    2. Select highlight ranges from the transcript. Default heuristic groups
       consecutive segments into windows that satisfy the duration bounds; an
       optional LLM scorer (lazy Anthropic, ``claude-opus-4-8``) can re-rank
       them when ``CLIP_USE_LLM=1`` is set.
    3. For each range, shell out to ffmpeg to cut ``[start, end]`` and reframe
       to vertical 9:16 (scale-to-cover + centered crop).

Heavy deps stay lazy: ``transcribe`` imports faster-whisper only when called,
and the LLM scorer imports ``anthropic`` only when ``CLIP_USE_LLM=1``. ffmpeg is
invoked as a subprocess (never linked) to stay clear of its GPL build.

``select_highlights`` and ``build_ffmpeg_cmd`` are pure functions, so the
selection logic and the ffmpeg command shape are testable without a real
encoder, model, or network.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

# ``Segment`` is only needed for typing; import lazily/under TYPE_CHECKING so
# this module never drags in the caption stack at import time.
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from services.caption.transcribe import Segment

# Anthropic model used by the optional LLM highlight scorer (RESEARCH.md).
LLM_MODEL = "claude-opus-4-8"


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


def select_highlights(
    segments: "list[Segment]",
    max_clips: int = 3,
    min_seconds: float = 15.0,
    max_seconds: float = 60.0,
) -> list[tuple[float, float]]:
    """Pick highlight ``(start, end)`` ranges from transcript segments.

    Pure function — no env reads, no I/O, no model. Greedily groups consecutive
    segments into non-overlapping windows: a window grows until adding the next
    segment would exceed ``max_seconds``, and is emitted once it reaches
    ``min_seconds``. Windows are returned in source order, capped at
    ``max_clips``.

    Args:
        segments: Ordered transcript segments (from ``transcribe``).
        max_clips: Maximum number of ranges to return.
        min_seconds: Minimum acceptable clip length.
        max_seconds: Maximum acceptable clip length.

    Returns:
        Ordered, non-overlapping ``(start_seconds, end_seconds)`` tuples, each
        with ``min_seconds <= (end - start) <= max_seconds``.
    """
    if max_clips <= 0 or not segments:
        return []
    if min_seconds > max_seconds:
        raise ValueError("min_seconds must be <= max_seconds")

    # Keep only well-formed, time-ordered segments.
    ordered = [
        s
        for s in segments
        if float(s.end_seconds) > float(s.start_seconds)
    ]
    ordered.sort(key=lambda s: float(s.start_seconds))

    ranges: list[tuple[float, float]] = []
    win_start: float | None = None
    win_end: float | None = None

    for seg in ordered:
        s = float(seg.start_seconds)
        e = float(seg.end_seconds)
        if win_start is None:
            win_start, win_end = s, e
            continue

        # Would extending the window blow the max? Close it first if it's long
        # enough, otherwise drop the partial window and restart here.
        if e - win_start > max_seconds:
            if (win_end - win_start) >= min_seconds:
                ranges.append((win_start, win_end))
                if len(ranges) >= max_clips:
                    return ranges
            win_start, win_end = s, e
        else:
            win_end = e
            if (win_end - win_start) >= min_seconds:
                # Emit a full window as soon as it satisfies the minimum so we
                # don't greedily merge the whole transcript into one clip.
                ranges.append((win_start, win_end))
                if len(ranges) >= max_clips:
                    return ranges
                win_start, win_end = None, None

    # Trailing window that reached the minimum but never got flushed.
    if (
        win_start is not None
        and win_end is not None
        and (win_end - win_start) >= min_seconds
        and len(ranges) < max_clips
    ):
        ranges.append((win_start, win_end))

    return ranges[:max_clips]


def _score_highlights_llm(
    segments: "list[Segment]",
    ranges: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Re-rank ``ranges`` best-first using Claude (lazy Anthropic import).

    Only invoked when ``CLIP_USE_LLM=1``. On any failure (missing key, network,
    bad output) it returns ``ranges`` unchanged so the caller stays offline-safe.
    """
    try:
        import json

        from anthropic import Anthropic  # lazy: heavy/optional dep
    except Exception:  # noqa: BLE001 - anthropic not installed
        return ranges

    def _text_for(start: float, end: float) -> str:
        return " ".join(
            (s.text or "").strip()
            for s in segments
            if float(s.start_seconds) >= start and float(s.end_seconds) <= end
        ).strip()

    candidates = [
        {"index": i, "start": rng[0], "end": rng[1], "transcript": _text_for(*rng)}
        for i, rng in enumerate(ranges)
    ]
    prompt = (
        "You are a short-form video editor. Score each candidate clip 0-1 for "
        "how likely it is to go viral as a vertical short, then return ONLY a "
        "JSON array of objects {\"index\": int, \"score\": float}, best first.\n"
        + json.dumps(candidates)
    )

    try:
        client = Anthropic()
        resp = client.messages.create(
            model=LLM_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(
            getattr(block, "text", "") for block in resp.content
        ).strip()
        scored = json.loads(raw)
        order = [int(item["index"]) for item in scored]
        reranked = [ranges[i] for i in order if 0 <= i < len(ranges)]
        # Append any ranges the model dropped so we never lose candidates.
        for i, rng in enumerate(ranges):
            if i not in order:
                reranked.append(rng)
        return reranked or ranges
    except Exception:  # noqa: BLE001 - any model/parse/network failure
        return ranges


def build_ffmpeg_cmd(
    src: str,
    start: float,
    end: float,
    out_path: str,
    width: int = 1080,
    height: int = 1920,
) -> list[str]:
    """Build the ffmpeg command that cuts ``[start, end]`` and reframes to 9:16.

    Pure function — no env reads, no I/O. The filter scales the source to
    *cover* the target box (preserving aspect, so one axis overflows) then
    center-crops to exactly ``width x height``:

        scale=W:H:force_original_aspect_ratio=increase,crop=W:H

    ``-ss`` / ``-to`` select the segment; audio is re-encoded (AAC) so the cut
    is clean at arbitrary timestamps.

    Args:
        src: Source video path.
        start: Cut start (seconds).
        end: Cut end (seconds).
        out_path: Output clip path.
        width: Target width (default 1080).
        height: Target height (default 1920 => 9:16).

    Returns:
        The argv list for ``subprocess.run`` (ffmpeg binary at argv[0]).
    """
    ffmpeg = os.getenv("FFMPEG_BINARY", "ffmpeg")
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height}"
    )
    return [
        ffmpeg,
        "-y",
        "-ss",
        f"{float(start):.3f}",
        "-to",
        f"{float(end):.3f}",
        "-i",
        src,
        "-vf",
        vf,
        "-c:a",
        "aac",
        out_path,
    ]


def clip(video_path: str) -> list[Clip]:
    """Cut ``video_path`` into a list of 9:16 vertical shorts.

    Transcribes the source, selects highlight ranges (heuristic by default, or
    LLM-reranked when ``CLIP_USE_LLM=1``), then cuts + reframes each range with
    ffmpeg. Honors ``FFMPEG_BINARY``, writes to ``CLIP_OUTPUT_DIR`` (default
    ``./media/clips``), and respects ``CLIP_MAX_CLIPS`` / ``CLIP_MIN_SECONDS`` /
    ``CLIP_MAX_SECONDS``.

    Args:
        video_path: Local path to the long-form source video.

    Returns:
        Zero or more ``Clip`` objects in source order (best-first when LLM
        scoring re-ranks them).
    """
    # Lazy: pulls in faster-whisper only when actually called.
    from services.caption.transcribe import transcribe

    aspect_ratio = os.getenv("CLIP_ASPECT_RATIO", "9:16")
    out_dir = os.getenv("CLIP_OUTPUT_DIR", "./media/clips")
    max_clips = int(os.getenv("CLIP_MAX_CLIPS", "3"))
    min_seconds = float(os.getenv("CLIP_MIN_SECONDS", "15"))
    max_seconds = float(os.getenv("CLIP_MAX_SECONDS", "60"))

    segments = transcribe(video_path)
    ranges = select_highlights(
        segments,
        max_clips=max_clips,
        min_seconds=min_seconds,
        max_seconds=max_seconds,
    )
    if os.getenv("CLIP_USE_LLM") == "1":
        ranges = _score_highlights_llm(segments, ranges)

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    stem = Path(video_path).stem

    clips: list[Clip] = []
    for i, (start, end) in enumerate(ranges):
        out_path = str(Path(out_dir) / f"{stem}_clip{i + 1}.mp4")
        cmd = build_ffmpeg_cmd(video_path, start, end, out_path)
        subprocess.run(cmd, check=True)
        clips.append(
            Clip(
                source_path=video_path,
                output_path=out_path,
                start_seconds=start,
                end_seconds=end,
                aspect_ratio=aspect_ratio,
                title=f"{stem} clip {i + 1}",
            )
        )
    return clips
