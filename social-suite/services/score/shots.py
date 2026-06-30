"""Scene/shot splitting for the bulk clip pipeline — free, dependency-light.

Phase 1 of the bulk pipeline: turn a raw video into a list of *shots* (the
camera takes between hard cuts), which Phase 2 scores and Phase 3 assembles.

The default detector shells out to **ffmpeg's scene filter** so it needs no
extra packages (ffmpeg is already installed on the runner). If PySceneDetect is
available it's used instead for sharper boundaries — but everything degrades
gracefully to ffmpeg, so this runs for $0 today.

Pure + Dropbox-free so it's unit-testable offline:

    from services.score.shots import detect_shots
    shots = detect_shots("/path/clip.mp4")     # -> [{"i":0,"start":0.0,"end":4.2,"dur":4.2}, ...]

Post-processing guarantees the shots are *usable*: contiguous coverage of the
whole video, no shot shorter than ``min_shot`` (merged into a neighbour) and
none longer than ``max_shot`` (split into even sub-shots), so a long static pan
still yields clip-sized candidates.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess

FFMPEG = os.getenv("FFMPEG_BINARY", "ffmpeg")
FFPROBE = os.getenv("FFPROBE_BINARY", "ffprobe")


def _have(binary: str) -> bool:
    return shutil.which(binary) is not None


def probe_duration(path: str) -> float:
    """Video duration in seconds via ffprobe (0.0 if it can't be read)."""
    try:
        r = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, check=True)
        return max(0.0, float(r.stdout.strip()))
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        return 0.0


def _ffmpeg_scene_cuts(path: str, threshold: float) -> list[float]:
    """Scene-change timestamps (seconds) from ffmpeg's ``scene`` filter.

    Runs a decode-only pass and parses ``pts_time`` out of ``showinfo`` on
    stderr. No extra dependencies — just ffmpeg.
    """
    cmd = [FFMPEG, "-i", path, "-filter:v",
           f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    cuts: list[float] = []
    for m in re.finditer(r"pts_time:([0-9]+\.?[0-9]*)", proc.stderr or ""):
        try:
            cuts.append(float(m.group(1)))
        except ValueError:
            continue
    return sorted(set(cuts))


def _scenedetect_cuts(path: str, threshold: float) -> list[float] | None:
    """Scene-change timestamps via PySceneDetect if it's installed, else None.

    ``threshold`` (0..1 for ffmpeg) is mapped to ContentDetector's ~0..100 scale.
    """
    try:
        from scenedetect import detect, ContentDetector  # lazy/optional
    except Exception:  # noqa: BLE001 — not installed: fall back to ffmpeg
        return None
    try:
        scenes = detect(path, ContentDetector(threshold=max(5.0, threshold * 100)))
    except Exception:  # noqa: BLE001 — any detector hiccup -> ffmpeg fallback
        return None
    # scenes is a list of (start, end) timecodes; collect the internal cut points.
    cuts = [s.get_seconds() for s, _e in scenes]
    return sorted({round(c, 3) for c in cuts if c and c > 0})


def _coalesce(bounds: list[float], dur: float, min_shot: float,
              max_shot: float) -> list[dict]:
    """Turn raw cut points into usable shots over ``[0, dur]``.

    Merges shots shorter than ``min_shot`` into the previous one, then splits any
    shot longer than ``max_shot`` into even sub-shots. Returns contiguous shots.
    """
    # Build initial [start, end] pairs from 0 .. cuts .. dur.
    pts = [0.0] + [c for c in bounds if 0.0 < c < dur] + [dur]
    pts = sorted(set(round(p, 3) for p in pts))
    pairs = [[pts[i], pts[i + 1]] for i in range(len(pts) - 1) if pts[i + 1] > pts[i]]

    # Merge too-short shots forward into their predecessor (or successor if first).
    merged: list[list[float]] = []
    for a, b in pairs:
        if b - a < min_shot and merged:
            merged[-1][1] = b
        elif b - a < min_shot and not merged:
            merged.append([a, b])  # hold; may merge with the next
        else:
            if merged and (merged[-1][1] - merged[-1][0]) < min_shot:
                merged[-1][1] = b   # absorb the held short opener
            else:
                merged.append([a, b])

    # Split too-long shots into even chunks near the target ceiling.
    out: list[dict] = []
    idx = 0
    for a, b in merged:
        span = b - a
        if span <= max_shot:
            out.append({"i": idx, "start": round(a, 2), "end": round(b, 2),
                        "dur": round(span, 2)})
            idx += 1
            continue
        n = max(2, -(-int(span * 1000) // int(max_shot * 1000)))  # ceil(span/max_shot)
        step = span / n
        for k in range(n):
            s = a + k * step
            e = b if k == n - 1 else a + (k + 1) * step
            out.append({"i": idx, "start": round(s, 2), "end": round(e, 2),
                        "dur": round(e - s, 2)})
            idx += 1
    return out


def detect_shots(path: str, *, threshold: float = 0.3, min_shot: float = 0.7,
                 max_shot: float = 6.0) -> list[dict]:
    """Split ``path`` into shots. See module docstring for guarantees.

    Returns a list of ``{"i","start","end","dur"}`` covering ``[0, duration]``.
    A video with no detectable internal cuts returns sensible whole/​split shots.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    dur = probe_duration(path)
    if dur <= 0:
        return []
    cuts = _scenedetect_cuts(path, threshold)
    detector = "scenedetect"
    if cuts is None:
        if not _have(FFMPEG):
            raise RuntimeError("ffmpeg not found and PySceneDetect unavailable")
        cuts = _ffmpeg_scene_cuts(path, threshold)
        detector = "ffmpeg"
    shots = _coalesce(cuts, dur, min_shot, max_shot)
    detect_shots.last_detector = detector  # bulk driver records which detector ran
    return shots


detect_shots.last_detector = "ffmpeg"
