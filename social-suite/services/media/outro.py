"""Render HP Landscaping's animated end-card (outro sting) for social videos.

Produces a ~3s 1080x1920 (9:16) clip: dark cinematic backdrop, the cross+HP
mark slamming in with an impact flash + light-sweep, the LANDSCAPING wordmark,
a green accent wipe, and the contact block (phone / web / serving Texas).

Outputs both a version WITH a synthesized audio sting and a SILENT version
(so it can ride on top of clips that already have their own audio).

    python3 services/media/outro.py            # render everything
    python3 services/media/outro.py --seconds 3 --fps 30

Drop the official transparent logo PNG at LOGO_OVERRIDE to use it instead of
the drawn mark.
"""
from __future__ import annotations

import argparse
import math
import os
import struct
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---- brand -----------------------------------------------------------------
W, H = 1080, 1920
GREEN = (104, 196, 52)        # HP grass green
GREEN_HI = (158, 230, 96)     # brighter green for glows/sweep
BLACK = (8, 10, 9)
WHITE = (244, 248, 244)
PHONE = "(979) 777-8851"
WEB = "HPLANDSCAPINGLLC.COM"
AREA = "SERVING TEXAS"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_DIR = os.path.join(ROOT, "content", "brand", "outro")
FRAME_DIR = os.path.join(OUT_DIR, "frames")
LOGO_OVERRIDE = os.path.join(ROOT, "content", "brand", "hp-logo.transparent.png")

FONTS = [
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONTS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


# ---- easing ----------------------------------------------------------------
def clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def ease_out(t: float) -> float:
    t = clamp01(t)
    return 1 - (1 - t) ** 3


def ease_out_back(t: float) -> float:
    t = clamp01(t)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def seg(t: float, a: float, b: float) -> float:
    """Normalize global time t to 0..1 across the window [a,b]."""
    return clamp01((t - a) / (b - a))


# ---- the cross + HP mark (drawn crisp, then reused) -------------------------
def build_mark() -> Image.Image:
    """A clean cross+HP monogram + LANDSCAPING banner, transparent, ~900px."""
    if os.path.exists(LOGO_OVERRIDE):
        return Image.open(LOGO_OVERRIDE).convert("RGBA")

    S = 4  # supersample
    cw, ch = 760 * S, 900 * S
    img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cw // 2

    def outlined_rect(box, fill, outline, ow):
        d.rectangle(box, fill=outline)
        x0, y0, x1, y1 = box
        d.rectangle((x0 + ow, y0 + ow, x1 - ow, y1 - ow), fill=fill)

    # --- Latin cross (black with green edge), rising above the letters
    ow = 10 * S
    bar_w = 70 * S
    v_x0, v_x1 = cx - bar_w // 2, cx + bar_w // 2
    v_y0, v_y1 = 30 * S, 430 * S
    h_y0, h_y1 = 150 * S, 150 * S + bar_w
    h_x0, h_x1 = cx - 150 * S, cx + 150 * S
    outlined_rect((v_x0, v_y0, v_x1, v_y1), BLACK, GREEN, ow)
    outlined_rect((h_x0, h_y0, h_x1, h_y1), BLACK, GREEN, ow)

    # --- HP letters (green, heavy, black stroke), flanking the cross stem
    hp = font(360 * S)
    stroke = 14 * S
    # H on the left, P on the right, hugging the cross
    for ch_, dx in (("H", -150 * S), ("P", 150 * S)):
        bb = d.textbbox((0, 0), ch_, font=hp, stroke_width=stroke)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        d.text((cx + dx - tw // 2 - bb[0], 470 * S - bb[1]), ch_, font=hp,
               fill=GREEN, stroke_width=stroke, stroke_fill=BLACK)

    # --- LANDSCAPING banner (black bar, white tracked letters)
    by0, by1 = 820 * S, 892 * S
    d.rectangle((cx - 330 * S, by0, cx + 330 * S, by1), fill=BLACK)
    lf = font(60 * S)
    txt = "L A N D S C A P I N G"
    bb = d.textbbox((0, 0), txt, font=lf)
    tw = bb[2] - bb[0]
    d.text((cx - tw // 2 - bb[0], (by0 + by1) // 2 - (bb[3] - bb[1]) // 2 - bb[1]),
           txt, font=lf, fill=WHITE)

    return img.resize((cw // S, ch // S), Image.LANCZOS)


# ---- static background -----------------------------------------------------
def build_background() -> Image.Image:
    """Near-black backdrop with a green radial glow + bottom grass gradient +
    faint diagonal sheen."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    # base vertical gradient (dark green-black -> black)
    base = np.zeros((H, W, 3), np.float32)
    g = (1 - yy / H)
    base[..., 0] = 3 + 3 * g
    base[..., 1] = 6 + 12 * g
    base[..., 2] = 4 + 5 * g
    # radial green glow — tight pool behind the mark, not a full wash
    cx, cy = W * 0.5, H * 0.40
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    glow = np.clip(1 - r / (W * 0.60), 0, 1) ** 2.4
    base[..., 0] += glow * 14
    base[..., 1] += glow * 42
    base[..., 2] += glow * 12
    # bottom green grass-light band
    band = np.clip((yy - H * 0.82) / (H * 0.18), 0, 1) ** 1.7
    base[..., 1] += band * 16
    base[..., 0] += band * 4
    # diagonal sheen
    sheen = (np.sin((xx + yy) / 260.0) * 0.5 + 0.5) * 3
    base += sheen[..., None] * np.array([0.3, 1.0, 0.4])
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB")
    # vignette
    vig = Image.new("L", (W, H), 0)
    dv = ImageDraw.Draw(vig)
    dv.ellipse((-W * 0.35, -H * 0.2, W * 1.35, H * 1.2), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(180))
    dark = Image.new("RGB", (W, H), (0, 0, 0))
    img = Image.composite(img, dark, vig)
    return img.convert("RGBA")


def add_glow(layer: Image.Image, color, radius: int, strength: float) -> Image.Image:
    """Return a colored glow image derived from layer's alpha."""
    a = layer.split()[-1]
    glow = Image.new("RGBA", layer.size, color + (0,))
    glow.putalpha(a.filter(ImageFilter.GaussianBlur(radius)))
    if strength != 1.0:
        ga = np.asarray(glow.split()[-1], np.float32) * strength
        glow.putalpha(Image.fromarray(np.clip(ga, 0, 255).astype(np.uint8)))
    return glow


def set_alpha(img: Image.Image, mul: float) -> Image.Image:
    a = np.asarray(img.split()[-1], np.float32) * clamp01(mul)
    out = img.copy()
    out.putalpha(Image.fromarray(a.astype(np.uint8)))
    return out


def paste_centered(base, layer, cy, scale=1.0, alpha=1.0):
    if scale != 1.0:
        nw, nh = max(1, int(layer.width * scale)), max(1, int(layer.height * scale))
        layer = layer.resize((nw, nh), Image.LANCZOS)
    if alpha < 1.0:
        layer = set_alpha(layer, alpha)
    base.alpha_composite(layer, (W // 2 - layer.width // 2, int(cy) - layer.height // 2))


# ---- contact / info block --------------------------------------------------
def build_info() -> Image.Image:
    img = Image.new("RGBA", (W, 420), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = W // 2

    big = font(74)
    bb = d.textbbox((0, 0), PHONE, font=big, stroke_width=3)
    tw = bb[2] - bb[0]
    # small phone glyph
    d.text((cx - tw // 2 - bb[0], 40 - bb[1]), PHONE, font=big, fill=WHITE,
           stroke_width=3, stroke_fill=BLACK)

    sub = font(46)
    line2 = f"{WEB}"
    bb = d.textbbox((0, 0), line2, font=sub)
    d.text((cx - (bb[2] - bb[0]) // 2 - bb[0], 150), line2, font=sub, fill=GREEN_HI)

    tag = font(40)
    bb = d.textbbox((0, 0), AREA, font=tag)
    d.text((cx - (bb[2] - bb[0]) // 2 - bb[0], 230), AREA, font=tag, fill=WHITE)
    return img


# ---- main render -----------------------------------------------------------
def render(seconds: float, fps: int) -> None:
    os.makedirs(FRAME_DIR, exist_ok=True)
    for f in os.listdir(FRAME_DIR):
        os.remove(os.path.join(FRAME_DIR, f))

    bg = build_background()
    mark = build_mark()
    mark_glow = add_glow(mark, GREEN_HI, 40, 1.0)
    info = build_info()

    mark_cy = int(H * 0.40)
    n = int(round(seconds * fps))
    print(f"rendering {n} frames @ {fps}fps -> {seconds}s")

    for i in range(n):
        t = i / fps
        frame = bg.copy()

        # subtle background breathing zoom
        z = 1.0 + 0.04 * ease_out(seg(t, 0, seconds))
        if z != 1.0:
            zw, zh = int(W * z), int(H * z)
            bgz = bg.resize((zw, zh), Image.LANCZOS).crop(
                ((zw - W) // 2, (zh - H) // 2, (zw - W) // 2 + W, (zh - H) // 2 + H))
            frame = bgz.copy()

        # --- mark slam-in (0.0 -> 0.65) with overshoot
        m = seg(t, 0.0, 0.65)
        m_scale = 0.62 + 0.40 * ease_out_back(m)        # ~0.62 -> ~1.02 -> 1.0
        m_alpha = ease_out(seg(t, 0.0, 0.40))
        base_scale = 0.78
        # glow pulse strongest on impact, then steady breathing
        impact = math.exp(-((t - 0.62) ** 2) / (2 * 0.06 ** 2))
        breathe = 0.5 + 0.5 * math.sin(t * 3.2)
        glow_a = m_alpha * (0.45 + 0.55 * impact + 0.18 * breathe)
        paste_centered(frame, mark_glow, mark_cy, base_scale * m_scale, min(1, glow_a))
        paste_centered(frame, mark, mark_cy, base_scale * m_scale, m_alpha)

        # --- light sweep across the mark (0.55 -> 1.25)
        s = seg(t, 0.55, 1.25)
        if 0 < s < 1:
            sweep = Image.new("L", (W, H), 0)
            ds = ImageDraw.Draw(sweep)
            sx = int(-300 + s * (W + 600))
            for k in range(-120, 121):
                a = int(180 * math.exp(-(k ** 2) / (2 * 45 ** 2)))
                ds.line((sx + k - 200, 0, sx + k + 200, H), fill=a, width=3)
            band = Image.new("RGBA", (W, H), GREEN_HI + (0,))
            mark_alpha_full = Image.new("L", (W, H), 0)
            mw = int(mark.width * base_scale)
            mh = int(mark.height * base_scale)
            ms = mark.resize((mw, mh), Image.LANCZOS).split()[-1]
            mark_alpha_full.paste(ms, (W // 2 - mw // 2, mark_cy - mh // 2))
            comb = np.minimum(np.asarray(sweep, np.float32),
                              np.asarray(mark_alpha_full, np.float32))
            band.putalpha(Image.fromarray(comb.astype(np.uint8)))
            frame.alpha_composite(band)

        # --- impact flash (brief, subtle green bloom from center on landing)
        if impact > 0.02:
            fl = Image.new("L", (W, H), 0)
            dfl = ImageDraw.Draw(fl)
            dfl.ellipse((W * 0.12, H * 0.18, W * 0.88, H * 0.62),
                        fill=int(120 * impact))
            fl = fl.filter(ImageFilter.GaussianBlur(120))
            flash = Image.new("RGBA", (W, H), GREEN_HI + (0,))
            flash.putalpha(fl)
            frame.alpha_composite(flash)

        # --- accent underline wipe (1.05 -> 1.55)
        u = ease_out(seg(t, 1.05, 1.55))
        if u > 0:
            uy = int(H * 0.62)
            half = int((W * 0.34) * u)
            line = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            dl = ImageDraw.Draw(line)
            dl.rectangle((W // 2 - half, uy - 4, W // 2 + half, uy + 4), fill=GREEN + (255,))
            line = line.filter(ImageFilter.GaussianBlur(1))
            glowln = add_glow(line, GREEN_HI, 14, 0.9)
            frame.alpha_composite(glowln)
            frame.alpha_composite(line)

        # --- info block rise + fade (1.25 -> 1.85)
        ia = ease_out(seg(t, 1.25, 1.85))
        if ia > 0:
            rise = int(40 * (1 - ia))
            frame.alpha_composite(set_alpha(info, ia),
                                  (0, int(H * 0.66) + rise))

        frame.convert("RGB").save(os.path.join(FRAME_DIR, f"f{i:04d}.png"))

    print("frames done")


def make_audio(seconds: float, path: str) -> None:
    """Synthesize a punchy whoosh -> boom -> shimmer sting."""
    sr = 48000
    n = int(seconds * sr)
    t = np.linspace(0, seconds, n, endpoint=False)
    out = np.zeros(n, np.float32)

    # rising whoosh (filtered noise swelling into the hit)
    noise = np.random.randn(n).astype(np.float32)
    swell = np.clip((t - 0.0) / 0.6, 0, 1) ** 2 * (t < 0.62)
    # crude lowpass via cumulative smoothing
    k = 80
    nf = np.convolve(noise, np.ones(k) / k, mode="same")
    out += nf * swell * 0.5

    # boom impact at 0.6s (low sine with fast decay)
    hit = t - 0.60
    env = np.exp(-np.clip(hit, 0, None) * 9.0) * (hit >= 0)
    boom = np.sin(2 * np.pi * 60 * t) * env * 0.9
    boom += np.sin(2 * np.pi * 90 * t) * env * 0.4
    out += boom

    # shimmer tail (soft high green-room sparkle)
    tail = np.exp(-np.clip(t - 0.65, 0, None) * 2.2) * (t >= 0.6)
    shimmer = (np.sin(2 * np.pi * 880 * t) + np.sin(2 * np.pi * 1320 * t)) * tail * 0.05
    out += shimmer

    # master fade in/out + soft clip
    fade = np.ones(n, np.float32)
    fi = int(0.01 * sr)
    fo = int(0.25 * sr)
    fade[:fi] = np.linspace(0, 1, fi)
    fade[-fo:] = np.linspace(1, 0, fo)
    out *= fade
    out = np.tanh(out * 1.4)
    out = (out / max(1e-6, np.max(np.abs(out))) * 0.92 * 32767).astype(np.int16)

    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(out.tobytes())
    print(f"wrote {path}")


def encode(seconds: float, fps: int) -> None:
    silent = os.path.join(OUT_DIR, "hp-outro-silent.mp4")
    withaud = os.path.join(OUT_DIR, "hp-outro.mp4")
    wav = os.path.join(OUT_DIR, "sting.wav")

    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(fps), "-i",
        os.path.join(FRAME_DIR, "f%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16",
        "-preset", "slow", "-movflags", "+faststart", silent,
    ], check=True, capture_output=True)
    print(f"wrote {silent}")

    make_audio(seconds, wav)
    subprocess.run([
        "ffmpeg", "-y", "-i", silent, "-i", wav,
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
        "-movflags", "+faststart", withaud,
    ], check=True, capture_output=True)
    print(f"wrote {withaud}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--fps", type=int, default=30)
    a = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    render(a.seconds, a.fps)
    encode(a.seconds, a.fps)
    # poster frame for thumbnails
    Image.open(os.path.join(FRAME_DIR, f"f{int(a.seconds*a.fps)-1:04d}.png")).save(
        os.path.join(OUT_DIR, "hp-outro-poster.jpg"), quality=92)
    print("DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
