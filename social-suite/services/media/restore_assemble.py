"""Restore end-card — the R assembles itself, then contact info. Logo colours
are used as-is (exact left->right blue fade sampled from the logo).

    python3 services/media/restore_assemble.py            # render + 4K encode

Renders 1080x1920 frames then exports 2160x3840 (true 4K) with the slam audio.
"""
from __future__ import annotations

import math
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from services.media.outro import make_audio  # reuse the audio sting

W, H = 1080, 1920
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
R_PNG = os.path.join(ROOT, "content", "brand", "restore-R-white.png")
OUT_DIR = os.path.join(ROOT, "content", "brand", "outro", "restore", "assemble")
FRAMES = os.path.join(OUT_DIR, "frames")

# Exact logo gradient corners (sampled): left light-blue -> right navy.
TL, TR = (84, 167, 211), (8, 23, 122)
BL, BR = (87, 174, 215), (2, 9, 114)
WHITE = (248, 250, 252)

MARK_CY = int(H * 0.35)
K = 8                      # number of strips the R assembles from
FONTS = ["/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def font(sz):
    for p in FONTS:
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default(size=sz)


def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def ease_out(t):
    return 1 - (1 - clamp01(t)) ** 3


def ease_out_back(t):
    t = clamp01(t)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def build_bg():
    """Bilinear blue gradient matching the logo, dithered + soft vignette."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    u, v = xx / W, yy / H
    tl, tr, bl, br = (np.array(c, np.float32) for c in (TL, TR, BL, BR))
    top = tl[None, None] * (1 - u[..., None]) + tr[None, None] * u[..., None]
    bot = bl[None, None] * (1 - u[..., None]) + br[None, None] * u[..., None]
    arr = top * (1 - v[..., None]) + bot * v[..., None]
    rv = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    arr *= (1 - np.clip(rv - 0.75, 0, 1)[..., None] * 0.25)
    arr += (np.random.default_rng(7).random((H, W, 3)).astype(np.float32) - 0.5) * 1.6
    arr = np.clip(arr, 0, 255)
    out = np.dstack([arr, np.full((H, W), 255, np.float32)]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def build_info():
    img = Image.new("RGBA", (W, 360), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, y = W // 2, 20
    lines = [("979-213-6848", 74, WHITE, 3),
             ("restoremarketingco@gmail.com", 46, (215, 235, 255), 0),
             ("RESTOREMARKETINGCO.COM", 40, WHITE, 0)]
    for text, sz, col, stroke in lines:
        f = font(sz)
        bb = d.textbbox((0, 0), text, font=f, stroke_width=stroke)
        d.text((cx - (bb[2] - bb[0]) // 2 - bb[0], y - bb[1]), text, font=f,
               fill=col, stroke_width=stroke, stroke_fill=(6, 12, 40))
        y += sz + 22
    return img


def _glow(layer, radius, strength):
    a = layer.split()[-1].filter(ImageFilter.GaussianBlur(radius))
    g = Image.new("RGBA", layer.size, (210, 235, 255, 0))
    arr = (np.asarray(a, np.float32) * strength).clip(0, 255).astype(np.uint8)
    g.putalpha(Image.fromarray(arr))
    return g


def render(seconds=3.0, fps=30):
    os.makedirs(FRAMES, exist_ok=True)
    for f in os.listdir(FRAMES):
        os.remove(os.path.join(FRAMES, f))
    bg = build_bg()
    info = build_info()

    # scaled R + its strips
    R = Image.open(R_PNG).convert("RGBA")
    D = 884
    R = R.resize((D, D), Image.LANCZOS)
    fx0, fy0 = W // 2 - D // 2, MARK_CY - D // 2
    sw = D / K
    strips = []
    for i in range(K):
        x0 = int(round(i * sw))
        x1 = D if i == K - 1 else int(round((i + 1) * sw))
        strips.append((x0, R.crop((x0, 0, x1, D))))

    n = int(round(seconds * fps))
    print(f"rendering {n} assemble frames")
    for fi in range(n):
        t = fi / fps
        frame = bg.copy()

        # assembled-alpha layer (for glow + shine), built from strips in place
        assembled = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for i, (x0, strip) in enumerate(strips):
            t0 = 0.10 + i * 0.055
            p = ease_out_back((t - t0) / 0.55)
            p = clamp01(p)
            a = ease_out((t - t0) / 0.40)
            # start fanned out horizontally + alternating vertical, converge in
            fan = (i - (K - 1) / 2) * 150
            dx = int(fan * (1 - p))
            dy = int(((-1) ** i) * 120 * (1 - p))
            px = fx0 + x0 + dx
            py = fy0 + dy
            if a <= 0:
                continue
            s = strip
            if a < 1:
                arr = (np.asarray(s.split()[-1], np.float32) * a).astype(np.uint8)
                s = s.copy(); s.putalpha(Image.fromarray(arr))
            assembled.alpha_composite(s, (px, py))

        # glow under the assembled R (breathes after assembly)
        breathe = 0.6 + 0.4 * math.sin(t * 3.0)
        gstr = 0.7 + 0.3 * breathe
        frame.alpha_composite(_glow(assembled, 26, gstr))
        frame.alpha_composite(assembled)

        # assembly flash (~when it locks)
        lock = math.exp(-((t - 0.95) ** 2) / (2 * 0.07 ** 2))
        if lock > 0.02:
            fl = Image.new("RGBA", (W, H), (235, 245, 255, 0))
            fl.putalpha(Image.fromarray(
                (np.asarray(assembled.split()[-1], np.float32) * 0.6 * lock)
                .astype(np.uint8)))
            frame.alpha_composite(fl)

        # shine sweep across the locked R (1.0 -> 1.7)
        sp = (t - 1.0) / 0.7
        if 0 < sp < 1:
            sweep = Image.new("L", (W, H), 0)
            ds = ImageDraw.Draw(sweep)
            sx = int(-200 + sp * (W + 400))
            for k in range(-90, 91):
                al = int(200 * math.exp(-(k ** 2) / (2 * 34 ** 2)))
                ds.line((sx + k - 160, 0, sx + k + 160, H), fill=al, width=3)
            band = Image.new("RGBA", (W, H), (255, 255, 255, 0))
            comb = np.minimum(np.asarray(sweep, np.float32),
                              np.asarray(assembled.split()[-1], np.float32))
            band.putalpha(Image.fromarray(comb.astype(np.uint8)))
            frame.alpha_composite(band)

        # accent underline + contact info
        u = ease_out((t - 1.25) / 0.4)
        if u > 0:
            half = int(W * 0.32 * u)
            ln = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(ln).rectangle(
                (W // 2 - half, int(H * 0.60) - 3, W // 2 + half, int(H * 0.60) + 3),
                fill=(225, 240, 255, 255))
            frame.alpha_composite(_glow(ln, 10, 0.9))
            frame.alpha_composite(ln)
        ia = ease_out((t - 1.45) / 0.5)
        if ia > 0:
            a2 = (np.asarray(info.split()[-1], np.float32) * ia).astype(np.uint8)
            ic = info.copy(); ic.putalpha(Image.fromarray(a2))
            frame.alpha_composite(ic, (0, int(H * 0.64) + int(30 * (1 - ia))))

        frame.convert("RGB").save(os.path.join(FRAMES, f"f{fi:04d}.png"))
    print("frames done")
    return n, fps


def encode(n, fps, seconds=3.0):
    wav = os.path.join(OUT_DIR, "sting.wav")
    make_audio(seconds, wav)
    out4k = os.path.join(OUT_DIR, "restore-assemble-4k.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-framerate", str(fps), "-i",
         os.path.join(FRAMES, "f%04d.png"), "-i", wav,
         "-vf", "scale=2160:3840:flags=lanczos,unsharp=3:3:0.4:3:3:0.0,format=yuv420p",
         "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out4k],
        check=True, capture_output=True)
    print(f"wrote {out4k}")
    return out4k


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    n, fps = render()
    encode(n, fps)
    print("DONE")
