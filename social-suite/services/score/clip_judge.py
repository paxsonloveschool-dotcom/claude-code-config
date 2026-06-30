"""Optional OpenCLIP "is this shot fire?" judge (Phase 5 upgrade hook).

Free and local, but heavy — needs the ``clip`` extra (open_clip_torch + torch).
It's never required: ``visual.py`` imports this lazily and falls back to the
heuristic scorer if torch/open_clip aren't installed, so the pipeline runs for
$0 without it. Enable on the runner with ``USE_CLIP=1`` (+ the extra installed).

The judge scores each sampled frame's CLIP similarity to "good landscaping shot"
prompts vs "bad shot" prompts and returns a single 0..1 ``clip`` signal that
``combine`` folds into the fire_score. Swapping these prompts (or this whole
class via ``SCORERS``) is how taste gets tuned later — no pipeline rebuild.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

FFMPEG = os.getenv("FFMPEG_BINARY", "ffmpeg")

GOOD_PROMPTS = [
    "a clean finished landscaping project", "a beautiful manicured backyard",
    "a satisfying before and after yard transformation", "lush green healthy lawn",
    "professional hardscape patio and stonework", "a dramatic outdoor reveal",
]
BAD_PROMPTS = [
    "a blurry out of focus photo", "a boring empty shot",
    "people standing around doing nothing", "a messy cluttered job site",
    "a dark underexposed photo", "a shaky unusable clip",
]


class ClipScorer:
    """Lazy OpenCLIP judge. Constructing it loads the model (heavy)."""

    name = "clip"

    def __init__(self, model: str = "ViT-B-32", pretrained: str = "openai"):
        import open_clip  # lazy/optional (clip extra)
        import torch  # noqa: F401

        self._torch = __import__("torch")
        self._model, _, self._preprocess = open_clip.create_model_and_transforms(
            model, pretrained=pretrained)
        self._model.eval()
        tok = open_clip.get_tokenizer(model)
        with self._torch.no_grad():
            self._good = self._embed_text(tok(GOOD_PROMPTS))
            self._bad = self._embed_text(tok(BAD_PROMPTS))

    def _embed_text(self, tokens):
        feats = self._model.encode_text(tokens)
        return feats / feats.norm(dim=-1, keepdim=True)

    def _extract(self, video, a, b, n, tmp):
        from PIL import Image  # lazy
        dur = max(0.1, b - a)
        subprocess.run(
            [FFMPEG, "-y", "-ss", f"{a:.3f}", "-t", f"{dur:.3f}", "-i", video,
             "-vf", f"scale=320:-2,fps={max(0.5, n/dur):.4f}", "-frames:v", str(n),
             os.path.join(tmp, "f%03d.png")], check=False, capture_output=True)
        return [Image.open(os.path.join(tmp, x)).convert("RGB")
                for x in sorted(os.listdir(tmp)) if x.endswith(".png")][:n]

    def score(self, video: str, a: float, b: float, samples: int = 5) -> dict:
        if not shutil.which(FFMPEG):
            raise RuntimeError("ffmpeg not found")
        with tempfile.TemporaryDirectory() as tmp:
            imgs = self._extract(video, a, b, samples, tmp)
            if not imgs:
                return {"clip": 0.5}
            batch = self._torch.stack([self._preprocess(im) for im in imgs])
            with self._torch.no_grad():
                feats = self._model.encode_image(batch)
                feats = feats / feats.norm(dim=-1, keepdim=True)
                good = feats @ self._good.T  # (frames, good_prompts)
                bad = feats @ self._bad.T
                # mean best-good vs best-bad similarity, mapped to 0..1
                margin = good.max(dim=1).values.mean() - bad.max(dim=1).values.mean()
                clip = float((margin.item() + 0.3) / 0.6)
        return {"clip": max(0.0, min(1.0, clip))}
