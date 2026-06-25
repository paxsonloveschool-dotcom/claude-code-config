"""Restore end-card — the R animates in, then contact info. Logo colours used
as-is (exact left->right blue fade sampled from the logo). Several entrance
styles via --mode:

  strips  vertical strips scatter then converge          (the original)
  halves  left & right halves slide together
  tiles   a grid of blocks flies in and assembles
  focus   the R racks into focus (blur+scale -> sharp)
  build   the R builds bottom-to-top behind a glowing edge

    python3 services/media/restore_assemble.py --mode tiles
    python3 services/media/restore_assemble.py --all      # render every mode

Renders 1080x1920 frames then exports 2160x3840 (true 4K) with the slam audio.
"""
from __future__ import annotations

import argparse
import math
import os
import subprocess

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from services.media.outro import make_audio

W, H = 1080, 1920
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
R_PNG = os.path.join(ROOT, "content", "brand", "restore-R-white.png")
BASE_OUT = os.path.join(ROOT, "content", "brand", "outro", "restore")

TL, TR = (84, 167, 211), (8, 23, 122)
BL, BR = (87, 174, 215), (2, 9, 114)
WHITE = (248, 250, 252)
MARK_CY = int(H * 0.35)
MODES = ("strips", "halves", "tiles", "focus", "build")
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


def _fade(img, a):
    if a >= 1:
        return img
    arr = (np.asarray(img.split()[-1], np.float32) * clamp01(a)).astype(np.uint8)
    o = img.copy()
    o.putalpha(Image.fromarray(arr))
    return o


def build_bg():
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


# ---- the R entrance, per mode -> returns a full-frame RGBA layer ------------
def r_layer(t, mode, R, fx0, fy0, D, rng_dirs):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    if mode == "strips":
        K = 8
        sw = D / K
        for i in range(K):
            x0 = int(round(i * sw))
            x1 = D if i == K - 1 else int(round((i + 1) * sw))
            t0 = 0.10 + i * 0.055
            p = clamp01(ease_out_back((t - t0) / 0.55))
            a = ease_out((t - t0) / 0.40)
            if a <= 0:
                continue
            dx = int((i - (K - 1) / 2) * 150 * (1 - p))
            dy = int(((-1) ** i) * 120 * (1 - p))
            layer.alpha_composite(_fade(R.crop((x0, 0, x1, D)), a),
                                  (fx0 + x0 + dx, fy0 + dy))

    elif mode == "halves":
        for half, sx in (("L", 0), ("R", D // 2)):
            piece = R.crop((sx, 0, sx + D // 2, D))
            p = clamp01(ease_out_back((t - 0.14) / 0.6))
            a = ease_out((t - 0.14) / 0.42)
            if a <= 0:
                continue
            sign = -1 if half == "L" else 1
            dx = int(sign * W * 0.55 * (1 - p))
            layer.alpha_composite(_fade(piece, a), (fx0 + sx + dx, fy0))

    elif mode == "tiles":
        G = 6
        tw, th = D / G, D / G
        for r in range(G):
            for c in range(G):
                x0, y0 = int(c * tw), int(r * th)
                x1 = D if c == G - 1 else int((c + 1) * tw)
                y1 = D if r == G - 1 else int((r + 1) * th)
                dist = math.hypot(c - (G - 1) / 2, r - (G - 1) / 2)
                t0 = 0.08 + dist * 0.07
                p = clamp01(ease_out_back((t - t0) / 0.5))
                a = ease_out((t - t0) / 0.36)
                if a <= 0:
                    continue
                dx, dy = rng_dirs[r * G + c]
                ox, oy = int(dx * (1 - p)), int(dy * (1 - p))
                layer.alpha_composite(_fade(R.crop((x0, y0, x1, y1)), a),
                                      (fx0 + x0 + ox, fy0 + y0 + oy))

    elif mode == "focus":
        p = ease_out((t - 0.1) / 0.85)
        if p > 0:
            scale = 1.45 - 0.45 * p
            blur = 20 * (1 - p)
            sz = max(1, int(D * scale))
            rs = R.resize((sz, sz), Image.LANCZOS)
            if blur > 0.4:
                rs = rs.filter(ImageFilter.GaussianBlur(blur))
            rs = _fade(rs, p)
            layer.alpha_composite(rs, (W // 2 - sz // 2, MARK_CY - sz // 2))

    elif mode == "build":
        p = ease_out((t - 0.1) / 0.95)
        if p > 0:
            reveal_y = int(D * (1 - p))
            mask = Image.new("L", (D, D), 0)
            ImageDraw.Draw(mask).rectangle((0, reveal_y, D, D), fill=255)
            mask = mask.filter(ImageFilter.GaussianBlur(7))
            rl = R.copy()
            rl.putalpha(ImageChops.multiply(R.split()[-1], mask))
            layer.alpha_composite(rl, (fx0, fy0))
            # glowing leading edge
            if 0 < p < 1:
                edge = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                ey = fy0 + reveal_y
                ImageDraw.Draw(edge).rectangle((fx0, ey - 5, fx0 + D, ey + 5),
                                               fill=(235, 245, 255, 200))
                # restrict the glowing edge line to the R's columns
                colmask = Image.new("L", (W, H), 0)
                colmask.paste(R.split()[-1], (fx0, fy0))
                edge.putalpha(ImageChops.multiply(edge.split()[-1], colmask))
                layer.alpha_composite(edge.filter(ImageFilter.GaussianBlur(3)))

    return layer


def render(mode, seconds=3.0, fps=30):
    out_dir = os.path.join(BASE_OUT, mode)
    frames = os.path.join(out_dir, "frames")
    os.makedirs(frames, exist_ok=True)
    for f in os.listdir(frames):
        os.remove(os.path.join(frames, f))

    bg = build_bg()
    info = build_info()
    R = Image.open(R_PNG).convert("RGBA").resize((884, 884), Image.LANCZOS)
    D = 884
    fx0, fy0 = W // 2 - D // 2, MARK_CY - D // 2
    rng = np.random.default_rng(42)
    rng_dirs = [(float(a), float(b)) for a, b in
                rng.uniform(-1, 1, (36, 2)) * 520]

    n = int(round(seconds * fps))
    print(f"[{mode}] rendering {n} frames")
    for fi in range(n):
        t = fi / fps
        frame = bg.copy()
        assembled = r_layer(t, mode, R, fx0, fy0, D, rng_dirs)

        breathe = 0.6 + 0.4 * math.sin(t * 3.0)
        frame.alpha_composite(_glow(assembled, 26, 0.7 + 0.3 * breathe))
        frame.alpha_composite(assembled)

        lock = math.exp(-((t - 1.0) ** 2) / (2 * 0.07 ** 2))
        if lock > 0.02:
            fl = Image.new("RGBA", (W, H), (235, 245, 255, 0))
            fl.putalpha(Image.fromarray(
                (np.asarray(assembled.split()[-1], np.float32) * 0.55 * lock)
                .astype(np.uint8)))
            frame.alpha_composite(fl)

        sp = (t - 1.05) / 0.7
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

        u = ease_out((t - 1.3) / 0.4)
        if u > 0:
            half = int(W * 0.32 * u)
            ln = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(ln).rectangle(
                (W // 2 - half, int(H * 0.60) - 3, W // 2 + half, int(H * 0.60) + 3),
                fill=(225, 240, 255, 255))
            frame.alpha_composite(_glow(ln, 10, 0.9))
            frame.alpha_composite(ln)
        ia = ease_out((t - 1.5) / 0.5)
        if ia > 0:
            ic = _fade(info, ia)
            frame.alpha_composite(ic, (0, int(H * 0.64) + int(30 * (1 - ia))))

        frame.convert("RGB").save(os.path.join(frames, f"f{fi:04d}.png"))
    print(f"[{mode}] frames done")
    return out_dir, frames, n, fps


def encode(mode, out_dir, frames, n, fps, seconds=3.0):
    wav = os.path.join(out_dir, "sting.wav")
    make_audio(seconds, wav)
    out4k = os.path.join(out_dir, f"restore-{mode}-4k.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-framerate", str(fps), "-i",
         os.path.join(frames, "f%04d.png"), "-i", wav,
         "-vf", "scale=2160:3840:flags=lanczos,unsharp=3:3:0.4:3:3:0.0,format=yuv420p",
         "-c:v", "libx264", "-crf", "18", "-preset", "slow", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", out4k],
        check=True, capture_output=True)
    print(f"[{mode}] -> {out4k}")
    return out4k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=MODES, default="strips")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    modes = MODES if a.all else [a.mode]
    for m in modes:
        out_dir, frames, n, fps = render(m)
        encode(m, out_dir, frames, n, fps)
    print("DONE", list(modes))


if __name__ == "__main__":
    raise SystemExit(main())
