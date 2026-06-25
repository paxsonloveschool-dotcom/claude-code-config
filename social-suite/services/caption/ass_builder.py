"""Build ASS subtitle files with word-by-word (karaoke) highlighting.

Pure-Python, no external dependencies — turns word-level transcript
``Segment``s into an ASS subtitle script that ffmpeg/libass can burn into a
video. Each word is timed with an ASS karaoke tag (``\\kf``) so it highlights
exactly when spoken (the TikTok/Reels look).

This module is intentionally dependency-free so it is fully unit-testable
without ffmpeg or any media files. ``caption/burn.py`` calls it, writes the
result to disk, and shells out to ffmpeg for the actual burn-in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .transcribe import Segment


def _fmt_time(seconds: float) -> str:
    """Format seconds as an ASS timestamp ``H:MM:SS.cs`` (centisecond precision)."""
    if seconds < 0:
        seconds = 0.0
    cs_total = int(round(seconds * 100))
    cs = cs_total % 100
    s_total = cs_total // 100
    s = s_total % 60
    m = (s_total // 60) % 60
    h = s_total // 3600
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _escape(text: str) -> str:
    """Escape characters that are special in ASS dialogue text."""
    return (
        text.replace("\\", "\\\\")
        .replace("{", "(")
        .replace("}", ")")
        .replace("\n", " ")
        .strip()
    )


def build_style(
    font: str = "Arial",
    font_size: int = 64,
    primary_colour: str = "&H00FFFFFF",   # white (highlighted/sung text)
    secondary_colour: str = "&H00AAAAAA", # grey (not-yet-spoken karaoke fill)
    outline_colour: str = "&H00000000",   # black outline
    outline: int = 3,
    shadow: int = 0,
    alignment: int = 2,                    # 2 = bottom-center
    margin_v: int = 240,                   # sit above the platform UI / bottom edge
) -> str:
    """Return the ``[V4+ Styles]`` block with a single style named ``Caption``."""
    fmt = (
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
        "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
        "MarginL, MarginR, MarginV, Encoding"
    )
    style = (
        f"Style: Caption,{font},{font_size},{primary_colour},{secondary_colour},"
        f"{outline_colour},&H64000000,-1,0,0,0,100,100,0,0,1,{outline},{shadow},"
        f"{alignment},40,40,{margin_v},1"
    )
    return "[V4+ Styles]\n" + fmt + "\n" + style + "\n"


def _karaoke_text(segment: "Segment") -> str:
    """Build the karaoke-tagged dialogue body for one segment.

    Uses ``\\kf<centiseconds>`` per word (smooth left-to-right fill). Gaps
    between words are absorbed with a plain ``\\k`` hold so timing stays aligned
    to speech. Falls back to plain text when the segment has no word timings.
    """
    if not segment.words:
        return _escape(segment.text)

    parts: list[str] = []
    prev_end = segment.start_seconds
    for word in segment.words:
        word_text = _escape(word.text)
        if not word_text:
            continue
        # Clamp: tolerate missing/zero/out-of-order timings without emitting a
        # negative \k hold or a zero/negative \kf duration (both -> invalid ASS).
        start = max(word.start_seconds, prev_end)
        end = max(word.end_seconds, start)
        gap = start - prev_end
        if gap > 0.02:
            parts.append(f"{{\\k{int(round(gap * 100))}}}")
        dur_cs = max(1, int(round((end - start) * 100)))
        parts.append(f"{{\\kf{dur_cs}}}{word_text} ")
        prev_end = end
    if not parts:
        # Every word was empty/escaped away — fall back to the segment text.
        return _escape(segment.text)
    return "".join(parts).rstrip()


def build_ass(
    segments: "list[Segment]",
    *,
    video_width: int = 1080,
    video_height: int = 1920,
    font: str = "Arial",
    font_size: int = 64,
) -> str:
    """Render ``segments`` into a complete ASS subtitle script (as a string).

    Args:
        segments: Word-level transcript segments from ``transcribe``.
        video_width/height: Target resolution (9:16 vertical by default).
        font/font_size: Caption styling.

    Returns:
        The full ASS file contents, ready to write to disk and pass to
        ``ffmpeg -vf "ass=<file>"``.
    """
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 0\n"          # smart wrap so long lines don't run off-frame
        "ScaledBorderAndShadow: yes\n"
        f"PlayResX: {video_width}\n"
        f"PlayResY: {video_height}\n\n"
    )
    styles = build_style(font=font, font_size=font_size) + "\n"
    events_header = (
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )
    lines: list[str] = []
    for seg in segments:
        body = _karaoke_text(seg)
        if not body:
            # Skip empty/blank segments — an empty Dialogue body is useless and
            # an all-whitespace one renders nothing.
            continue
        start = _fmt_time(seg.start_seconds)
        # Clamp end >= start so a zero/negative-duration segment never produces
        # a Dialogue line whose End precedes its Start (invalid ASS).
        end = _fmt_time(max(seg.end_seconds, seg.start_seconds))
        lines.append(f"Dialogue: 0,{start},{end},Caption,,0,0,0,,{body}")
    body = ("\n".join(lines) + "\n") if lines else ""
    return header + styles + events_header + body
