"""Visual scoring brain for silent b-roll — free, PIL+ffmpeg, no API keys.

Phase 2 of the bulk pipeline. Phase 1 split each video into shots; this scores
how *postable* each shot is so the best can be auto-picked and ranked, even with
no speech to go on (the transcript brain can't help silent work footage).

Each shot is sampled to a few frames (ffmpeg) and rated on cheap, robust signals
computed with Pillow only — **no numpy/opencv required**, so it runs on the same
slim deps as CI:

* **sharpness** — edge energy (in-focus, crisp detail beats a blurry pan)
* **exposure** — luma not crushed/blown
* **motion**   — some movement is alive; a frozen or shaky shot is penalised
* **colorfulness** — lush, saturated frames (green lawns, blue pools) read better

A pluggable :class:`Scorer` lets a stronger judge (OpenCLIP now, a paid vision/LLM
model later) re-rank without touching the pipeline — see :data:`SCORERS`. The CLIP
judge is optional (needs the ``clip`` extra); everything works for $0 without it.

    from services.score.visual import score_shot, combine
    m = score_shot("clip.mp4", 3.0, 8.0)     # {'sharpness':.., 'fire_score':..}

``combine`` is pure (no PIL) and unit-tested; frame work is lazy + ffmpeg-guarded.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

FFMPEG = os.getenv("FFMPEG_BINARY", "ffmpeg")

# Default weights for the blended fire_score. ``clip`` is only present when a
# CLIP-style judge ran; when absent its weight is redistributed across the rest.
WEIGHTS = {
    "sharpness": 0.34,
    "exposure": 0.20,
    "motion": 0.16,
    "colorfulness": 0.10,
    "clip": 0.20,
}


def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else float(x)


def combine(metrics: dict, weights: dict | None = None) -> float:
    """Blend normalised 0..1 ``metrics`` into a 0..100 ``fire_score`` (pure).

    Only metrics present in both ``metrics`` and ``weights`` count; missing ones
    (e.g. ``clip`` when the CLIP judge didn't run) have their weight redistributed
    proportionally, so scores stay comparable whether or not CLIP was used.
    """
    weights = weights or WEIGHTS
    present = {k: weights[k] for k in weights if k in metrics and metrics[k] is not None}
    total_w = sum(present.values())
    if total_w <= 0:
        return 0.0
    score = sum((w / total_w) * _clamp01(metrics[k]) for k, w in present.items())
    return round(100.0 * _clamp01(score), 1)


# ---- frame sampling (ffmpeg) ----------------------------------------------
def _extract_frames(video: str, a: float, b: float, n: int, tmp: str) -> list:
    """Sample up to ``n`` evenly-spaced RGB frames from ``[a,b]`` as PIL images."""
    from PIL import Image  # lazy (cards extra)

    dur = max(0.1, b - a)
    fps = max(0.5, n / dur)
    out = os.path.join(tmp, "f%03d.png")
    subprocess.run(
        [FFMPEG, "-y", "-ss", f"{a:.3f}", "-t", f"{dur:.3f}", "-i", video,
         "-vf", f"scale=320:-2,fps={fps:.4f}", "-frames:v", str(n), out],
        check=False, capture_output=True)
    imgs = []
    for name in sorted(os.listdir(tmp)):
        if name.endswith(".png"):
            try:
                imgs.append(Image.open(os.path.join(tmp, name)).convert("RGB"))
            except Exception:  # noqa: BLE001 — skip an unreadable frame
                continue
    return imgs[:n]


def _frame_metrics(imgs: list) -> dict:
    """Raw, then shaped 0..1 metrics from sampled frames (Pillow only)."""
    from PIL import ImageChops, ImageFilter, ImageStat  # lazy

    if not imgs:
        return {"sharpness": 0.0, "exposure": 0.0, "motion": 0.0, "colorfulness": 0.0}

    grays = [im.convert("L") for im in imgs]

    # sharpness: mean edge energy across frames (FIND_EDGES then mean luma).
    edges = [ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).mean[0] for g in grays]
    sharp_raw = sum(edges) / len(edges)
    sharpness = _clamp01(sharp_raw / 40.0)

    # exposure: closeness of mean luma to a pleasant ~120.
    luma = sum(ImageStat.Stat(g).mean[0] for g in grays) / len(grays)
    exposure = _clamp01(1.0 - abs(luma - 120.0) / 120.0)

    # motion: mean abs diff between consecutive frames, shaped to favour
    # moderate movement (alive but not shaky/chaotic).
    if len(grays) >= 2:
        diffs = [ImageStat.Stat(ImageChops.difference(grays[i], grays[i + 1])).mean[0]
                 for i in range(len(grays) - 1)]
        motion_raw = sum(diffs) / len(diffs)
    else:
        motion_raw = 0.0
    if motion_raw <= 12.0:
        motion = _clamp01(motion_raw / 12.0)
    else:
        motion = _clamp01(1.0 - (motion_raw - 12.0) / 40.0)

    # colorfulness: average per-frame channel spread (vivid > washed out).
    colors = []
    for im in imgs:
        st = ImageStat.Stat(im)
        colors.append(sum(st.stddev) / 3.0)
    colorfulness = _clamp01((sum(colors) / len(colors)) / 60.0)

    return {"sharpness": round(sharpness, 4), "exposure": round(exposure, 4),
            "motion": round(motion, 4), "colorfulness": round(colorfulness, 4)}


# ---- pluggable scorers (Phase 5 upgrade hook) ------------------------------
class HeuristicScorer:
    """Default $0 judge: the PIL frame metrics above."""

    name = "heuristic"

    def score(self, video: str, a: float, b: float, samples: int = 5) -> dict:
        if not shutil.which(FFMPEG):
            raise RuntimeError("ffmpeg not found")
        with tempfile.TemporaryDirectory() as tmp:
            imgs = _extract_frames(video, a, b, samples, tmp)
            return _frame_metrics(imgs)


def _clip_scorer():
    """Return an OpenCLIP judge if the optional ``clip`` extra is installed, else None."""
    try:
        from services.score.clip_judge import ClipScorer  # lazy/optional
    except Exception:  # noqa: BLE001
        return None
    try:
        return ClipScorer()
    except Exception:  # noqa: BLE001
        return None


# Registry so a stronger/paid judge can be slotted in by name (env SCORER).
SCORERS = {"heuristic": HeuristicScorer}


def get_scorer(name: str | None = None):
    name = (name or os.getenv("SCORER", "heuristic")).strip().lower()
    cls = SCORERS.get(name, HeuristicScorer)
    return cls()


def score_shot(video: str, a: float, b: float, *, samples: int = 5,
               use_clip: bool | None = None) -> dict:
    """Score one shot ``[a,b]`` → metrics + blended ``fire_score`` (0..100).

    Always computes the heuristic metrics; if a CLIP judge is available (and
    ``use_clip`` isn't False) its good-vs-bad score is folded in via ``combine``.
    """
    metrics = HeuristicScorer().score(video, a, b, samples=samples)
    if use_clip is None:
        use_clip = os.getenv("USE_CLIP", "").strip().lower() in ("1", "true", "yes")
    if use_clip:
        cj = _clip_scorer()
        if cj is not None:
            try:
                metrics["clip"] = _clamp01(cj.score(video, a, b, samples=samples)
                                           .get("clip", 0.5))
            except Exception:  # noqa: BLE001 — CLIP optional; never break scoring
                pass
    metrics["fire_score"] = combine(metrics)
    return metrics
