"""Multiple HP Landscaping end-card (outro) STYLES — pick your vibe.

Each style is a ~3s 9:16 1080x1920 sting that lands on the same lockup (cross+HP
mark + LANDSCAPING wordmark + contact block) but gets there with a different
look/motion, grounded in 2026 logo-sting trends:

  neon      green neon glow + light-sweep + impact bloom        (the original)
  ember     organic green embers drift up, burst on the lockup  (luxury/organic)
  glitch    RGB-split digital boot-up, scanlines, hard lock      (techy/aggressive)
  chrome    metallic mark, god-rays + specular sweep, premium    (luxury b-roll)
  slam      diagonal swipe + shake + motion-blur streak slam     (sport/broadcast)

    python3 services/media/outro_styles.py            # render ALL styles
    python3 services/media/outro_styles.py --style glitch --seconds 3

Outputs to content/brand/outro/<style>/hp-outro-<style>.mp4 (+ silent + poster).
Logo is drawn crisp; drop a transparent PNG at content/brand/hp-logo.transparent.png.
"""
from __future__ import annotations

import argparse
import math
import os
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from services.media.outro import (
    W, H, GREEN, GREEN_HI, BLACK, WHITE, font, _rgb_env,
    clamp01, ease_out, ease_out_back, seg,
    build_mark, build_info, add_glow, set_alpha, paste_centered,
)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_DIR = os.path.join(ROOT, "content", "brand", "outro")
MARK_CY = int(H * 0.35)
INFO_Y = int(H * 0.66)


# ---------------------------------------------------------------- shared bits
def ease_in_out(t):
    t = clamp01(t)
    return 3 * t * t - 2 * t * t * t


def base_dark(green_pool=1.0, cx=0.5, cy=0.40):
    """Backdrop. Pure black by default (logo is the hero); set OUTRO_BG1 (+ optional
    OUTRO_BG2) to fill the card with a brand colour / diagonal gradient instead."""
    bg1 = _rgb_env("OUTRO_BG1", None)
    bg2 = _rgb_env("OUTRO_BG2", None)
    if not bg1:
        return Image.new("RGBA", (W, H), (0, 0, 0, 255))
    if not bg2:
        return Image.new("RGBA", (W, H), tuple(bg1) + (255,))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    tdiag = ((xx / W) + (yy / H)) / 2.0          # 0 at top-left -> 1 at bottom-right
    c1 = np.array(bg1, np.float32)
    c2 = np.array(bg2, np.float32)
    arr = c1[None, None, :] * (1 - tdiag[..., None]) + c2[None, None, :] * tdiag[..., None]
    out = np.dstack([arr, np.full((H, W), 255, np.float32)]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def info_rise(frame, info, t, a=1.25, b=1.85):
    ia = ease_out(seg(t, a, b))
    if ia > 0:
        frame.alpha_composite(set_alpha(info, ia), (0, INFO_Y + int(40 * (1 - ia))))


def accent_wipe(frame, t, a=1.05, b=1.55, y=None, color=GREEN):
    u = ease_out(seg(t, a, b))
    if u <= 0:
        return
    y = y or int(H * 0.62)
    half = int((W * 0.34) * u)
    line = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(line).rectangle((W // 2 - half, y - 4, W // 2 + half, y + 4),
                                   fill=color + (255,))
    frame.alpha_composite(add_glow(line, GREEN_HI, 14, 0.9))
    frame.alpha_composite(line)


def mark_layers(mark, scale):
    mw, mh = int(mark.width * scale), int(mark.height * scale)
    return mark.resize((mw, mh), Image.LANCZOS)


# --------------------------------------------------------------- style: NEON
def f_neon(t, seconds, ctx):
    bg, mark, mark_glow, info = ctx["bg"], ctx["mark"], ctx["glow"], ctx["info"]
    frame = bg.copy()
    m = seg(t, 0.0, 0.65)
    m_scale = 0.62 + 0.40 * ease_out_back(m)
    m_alpha = ease_out(seg(t, 0.0, 0.40))
    bs = 0.78
    impact = math.exp(-((t - 0.62) ** 2) / (2 * 0.06 ** 2))
    breathe = 0.5 + 0.5 * math.sin(t * 3.2)
    paste_centered(frame, mark_glow, MARK_CY, bs * m_scale,
                   min(1, m_alpha * (0.45 + 0.55 * impact + 0.18 * breathe)))
    paste_centered(frame, mark, MARK_CY, bs * m_scale, m_alpha)
    _light_sweep(frame, mark, bs, t, 0.55, 1.25)
    if impact > 0.02:
        fl = Image.new("L", (W, H), 0)
        ImageDraw.Draw(fl).ellipse((W*0.12, H*0.18, W*0.88, H*0.62), fill=int(120*impact))
        flash = Image.new("RGBA", (W, H), GREEN_HI + (0,))
        flash.putalpha(fl.filter(ImageFilter.GaussianBlur(120)))
        frame.alpha_composite(flash)
    accent_wipe(frame, t)
    info_rise(frame, info, t)
    return frame


def _light_sweep(frame, mark, bs, t, a, b):
    s = seg(t, a, b)
    if not (0 < s < 1):
        return
    sweep = Image.new("L", (W, H), 0)
    ds = ImageDraw.Draw(sweep)
    sx = int(-300 + s * (W + 600))
    for k in range(-120, 121):
        al = int(180 * math.exp(-(k ** 2) / (2 * 45 ** 2)))
        ds.line((sx + k - 200, 0, sx + k + 200, H), fill=al, width=3)
    band = Image.new("RGBA", (W, H), GREEN_HI + (0,))
    full = Image.new("L", (W, H), 0)
    ms = mark_layers(mark, bs)
    full.paste(ms.split()[-1], (W // 2 - ms.width // 2, MARK_CY - ms.height // 2))
    comb = np.minimum(np.asarray(sweep, np.float32), np.asarray(full, np.float32))
    band.putalpha(Image.fromarray(comb.astype(np.uint8)))
    frame.alpha_composite(band)


# -------------------------------------------------------------- style: EMBER
def _ember_field(n_particles=220, seed=7):
    rng = np.random.default_rng(seed)
    return dict(
        x=rng.uniform(0, W, n_particles),
        y=rng.uniform(0, H, n_particles),
        spd=rng.uniform(18, 70, n_particles),
        sway=rng.uniform(8, 30, n_particles),
        phase=rng.uniform(0, 6.28, n_particles),
        size=rng.uniform(1.5, 5.5, n_particles),
        warm=rng.uniform(0, 1, n_particles),
    )


def f_ember(t, seconds, ctx):
    bg, mark, mark_glow, info = ctx["bg"], ctx["mark"], ctx["glow"], ctx["info"]
    p = ctx["embers"]
    frame = bg.copy()
    # drifting embers (behind + in front)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dl = ImageDraw.Draw(layer)
    impact = math.exp(-((t - 0.55) ** 2) / (2 * 0.07 ** 2))
    for i in range(len(p["x"])):
        yy = (p["y"][i] - p["spd"][i] * t) % H
        xx = p["x"][i] + math.sin(p["phase"][i] + t * 1.4) * p["sway"][i]
        # burst push outward at impact
        if impact > 0.05:
            dx = xx - W / 2
            dyv = yy - MARK_CY
            d = math.hypot(dx, dyv) + 1e-3
            push = impact * 90
            xx += dx / d * push
            yy += dyv / d * push
        flick = 0.6 + 0.4 * math.sin(t * 8 + p["phase"][i])
        warm = p["warm"][i]
        col = (int(120 + 90 * warm), int(200 - 40 * warm), int(70 - 40 * warm))
        a = int(150 * flick)
        r = p["size"][i] * (1 + 0.6 * impact)
        dl.ellipse((xx - r, yy - r, xx + r, yy + r), fill=col + (a,))
    layer = layer.filter(ImageFilter.GaussianBlur(1.2))
    glow_layer = layer.filter(ImageFilter.GaussianBlur(9))
    frame.alpha_composite(glow_layer)
    frame.alpha_composite(layer)
    # mark: gentle scale-in + warm glow swell
    m_alpha = ease_out(seg(t, 0.15, 0.7))
    m_scale = 0.86 + 0.14 * ease_out(seg(t, 0.15, 0.85))
    bs = 0.78
    paste_centered(frame, mark_glow, MARK_CY, bs * m_scale,
                   min(1, m_alpha * (0.5 + 0.7 * impact)))
    paste_centered(frame, mark, MARK_CY, bs * m_scale, m_alpha)
    accent_wipe(frame, t, 1.0, 1.55)
    info_rise(frame, info, t, 1.2, 1.85)
    return frame


# ------------------------------------------------------------- style: GLITCH
def f_glitch(t, seconds, ctx):
    bg, mark, info = ctx["bg"], ctx["mark"], ctx["info"]
    frame = bg.copy()
    bs = 0.78
    settle = seg(t, 0.0, 0.85)        # boot-up settles by 0.85s
    glitch_amt = (1 - ease_out(settle))
    flicker = 0.4 + 0.6 * abs(math.sin(t * 30))
    m_alpha = 0.2 + 0.8 * ease_out(seg(t, 0.0, 0.5))
    if settle < 1:
        m_alpha *= (0.5 + 0.5 * flicker)

    ml = mark_layers(mark, bs)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas.alpha_composite(set_alpha(ml, m_alpha),
                           (W // 2 - ml.width // 2, MARK_CY - ml.height // 2))
    # RGB split scaled by remaining glitch
    dx = int(18 * glitch_amt * (1 if int(t * 60) % 2 else -1))
    from PIL import ImageChops
    r, g, b, a = canvas.split()
    canvas = Image.merge("RGBA", (
        ImageChops.offset(r, dx, 0), g, ImageChops.offset(b, -dx, 0), a))

    # horizontal slice displacement during glitch
    if glitch_amt > 0.05:
        arr = np.asarray(canvas).copy()
        rng = np.random.default_rng(int(t * 120))
        for _ in range(int(8 * glitch_amt)):
            y0 = rng.integers(0, H - 40)
            hgt = rng.integers(8, 40)
            sh = rng.integers(-40, 40)
            arr[y0:y0 + hgt] = np.roll(arr[y0:y0 + hgt], sh, axis=1)
        canvas = Image.fromarray(arr)

    frame.alpha_composite(add_glow(canvas, GREEN_HI, 22, 0.5 + 0.5 * glitch_amt))
    frame.alpha_composite(canvas)

    # scanlines
    scan = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds = ImageDraw.Draw(scan)
    for y in range(0, H, 4):
        ds.line((0, y, W, y), fill=(0, 0, 0, 40))
    frame.alpha_composite(scan)

    # occasional full-width glitch bar
    if glitch_amt > 0.1 and int(t * 30) % 5 == 0:
        gb = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        yb = int((math.sin(t * 50) * 0.5 + 0.5) * H)
        ImageDraw.Draw(gb).rectangle((0, yb, W, yb + 6), fill=GREEN_HI + (140,))
        frame.alpha_composite(gb)

    accent_wipe(frame, t, 0.9, 1.4)
    info_rise(frame, info, t, 1.15, 1.8)
    return frame


# ------------------------------------------------------------- style: CHROME
def _chrome_mark(mark):
    """Map a metallic vertical gradient (silver->green->dark) onto the mark."""
    h = mark.height
    grad = np.zeros((h, 1, 3), np.float32)
    for y in range(h):
        v = y / h
        band = 0.5 + 0.5 * math.sin(v * math.pi * 3)
        grad[y, 0] = (
            120 + 120 * band + 40 * (1 - v),
            150 + 90 * band,
            90 + 60 * band,
        )
    grad = np.clip(grad, 0, 255).repeat(mark.width, axis=1).astype(np.uint8)
    metal = Image.fromarray(grad, "RGB").convert("RGBA")
    metal.putalpha(mark.split()[-1])
    return metal


def f_chrome(t, seconds, ctx):
    mark, info = ctx["mark"], ctx["info"]
    chrome = ctx["chrome"]
    frame = base_dark(green_pool=0.5).copy()
    bs = 0.78
    # god-rays from behind the mark
    ray = ease_out(seg(t, 0.1, 0.9))
    if ray > 0:
        rays = Image.new("L", (W, H), 0)
        dr = ImageDraw.Draw(rays)
        cx, cy = W // 2, MARK_CY
        for ang in range(0, 360, 12):
            a = math.radians(ang + t * 18)
            x2 = cx + math.cos(a) * H
            y2 = cy + math.sin(a) * H
            dr.line((cx, cy, x2, y2), fill=int(60 * ray), width=14)
        rays = rays.filter(ImageFilter.GaussianBlur(26))
        rl = Image.new("RGBA", (W, H), GREEN_HI + (0,))
        rl.putalpha(rays)
        frame.alpha_composite(rl)

    m_alpha = ease_out(seg(t, 0.1, 0.7))
    m_scale = 0.9 + 0.1 * ease_in_out(seg(t, 0.1, 1.0))
    cl = mark_layers(chrome, bs * m_scale)
    frame.alpha_composite(add_glow(cl, GREEN_HI, 30,
                                   0.6 * m_alpha + 0.4),
                          (W // 2 - cl.width // 2, MARK_CY - cl.height // 2))
    frame.alpha_composite(set_alpha(cl, m_alpha),
                          (W // 2 - cl.width // 2, MARK_CY - cl.height // 2))
    # specular highlight sweep
    _light_sweep(frame, mark, bs, t, 0.5, 1.4)
    # lens-flare streak passing through
    fp = seg(t, 0.55, 1.1)
    if 0 < fp < 1:
        fx = int(W * 0.1 + fp * W * 0.8)
        fl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dfl = ImageDraw.Draw(fl)
        dfl.line((fx, MARK_CY, fx, MARK_CY), fill=WHITE + (0,))
        dfl.ellipse((fx - 60, MARK_CY - 6, fx + 60, MARK_CY + 6),
                    fill=(255, 255, 255, 180))
        dfl.line((0, MARK_CY, W, MARK_CY), fill=(200, 255, 200, 50), width=2)
        frame.alpha_composite(fl.filter(ImageFilter.GaussianBlur(3)))
    accent_wipe(frame, t, 1.0, 1.55)
    info_rise(frame, info, t, 1.25, 1.9)
    return frame


# --------------------------------------------------------------- style: SLAM
SLAM_GREEN = _rgb_env("OUTRO_SLAM_RGB", (130, 232, 60))     # hot accent for slam fx
SLAM_HI = _rgb_env("OUTRO_SLAM_RGB_HI", (188, 255, 118))


def _tint(layer, color):
    out = Image.new("RGBA", layer.size, color + (0,))
    out.putalpha(layer.split()[-1])
    return out


def _frame_shake(frame, t):
    """Kick the whole frame for a few frames right after impact."""
    land = seg(t, 0.50, 0.74)
    amp = (1 - land) * 24 if 0.50 < t < 0.74 else 0
    if amp < 0.6:
        return frame
    sx = int(math.sin(t * 130) * amp)
    sy = int(math.cos(t * 110) * amp)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    canvas.alpha_composite(frame, (sx, sy))
    return canvas


def f_slam(t, seconds, ctx):
    mark, info = ctx["mark"], ctx["info"]
    frame = base_dark().copy()
    bs = 1.55

    # diagonal swipe bars wiping across early
    sw = ease_in_out(seg(t, 0.0, 0.45))
    if sw < 1:
        bar = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        db = ImageDraw.Draw(bar)
        off = int((sw) * (W + H) * 1.4 - H)
        db.polygon([(off, 0), (off + 260, 0), (off + 260 - H, H), (off - H, H)],
                   fill=SLAM_GREEN + (255,))
        db.polygon([(off + 300, 0), (off + 330, 0), (off + 330 - H, H),
                    (off + 300 - H, H)], fill=WHITE + (220,))
        frame.alpha_composite(bar)

    m = seg(t, 0.18, 0.5)
    if t < 0.18:
        return _frame_shake(_slam_overlays(frame, t, info), t)
    m_scale = bs * (1.6 - 0.6 * ease_out_back(m))      # 1.6x -> ~1.0
    m_alpha = ease_out(seg(t, 0.18, 0.34))
    ml = mark_layers(mark, m_scale)
    mx = W // 2 - ml.width // 2
    my = MARK_CY - ml.height // 2

    # radial speed lines bursting outward on impact
    imp = math.exp(-((t - 0.50) ** 2) / (2 * 0.055 ** 2))
    if imp > 0.03:
        sl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dsl = ImageDraw.Draw(sl)
        for ang in range(0, 360, 9):
            a = math.radians(ang)
            r0, r1 = 110, 110 + W * 0.65 * imp
            dsl.line((W/2 + math.cos(a)*r0, MARK_CY + math.sin(a)*r0,
                      W/2 + math.cos(a)*r1, MARK_CY + math.sin(a)*r1),
                     fill=SLAM_HI + (int(190 * imp),), width=3)
        frame.alpha_composite(sl.filter(ImageFilter.GaussianBlur(1)))

    # motion-blur ghost trail while still flying in
    if m < 1:
        for off in range(1, 7):
            frame.alpha_composite(set_alpha(ml, 0.10), (mx, my + off * 14))

    frame.alpha_composite(add_glow(ml, SLAM_HI, 28, 0.85 * m_alpha + 0.5 * imp),
                          (mx, my))
    frame.alpha_composite(set_alpha(ml, m_alpha), (mx, my))
    # white impact flash ON the logo at landing
    if imp > 0.05:
        frame.alpha_composite(set_alpha(_tint(ml, (255, 255, 255)), 0.8 * imp),
                              (mx, my))

    # double shock ring
    for delay, mul, w in ((0.50, 0.70, 9), (0.56, 1.0, 5)):
        ring = seg(t, delay, delay + 0.34)
        if 0 < ring < 1:
            rr = int(ring * W * mul)
            rl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(rl).ellipse(
                (W//2 - rr, MARK_CY - rr, W//2 + rr, MARK_CY + rr),
                outline=SLAM_HI + (int(210 * (1 - ring)),), width=w)
            frame.alpha_composite(rl.filter(ImageFilter.GaussianBlur(2)))

    return _frame_shake(_slam_overlays(frame, t, info), t)


def _slam_overlays(frame, t, info):
    # diagonal accent bar above the contact block
    u = ease_out(seg(t, 0.8, 1.2))
    if u > 0:
        bar = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        db = ImageDraw.Draw(bar)
        y = int(H * 0.62)
        half = int(W * 0.4 * u)
        db.polygon([(W//2 - half, y - 6), (W//2 + half, y - 6),
                    (W//2 + half + 14, y + 6), (W//2 - half + 14, y + 6)],
                   fill=SLAM_GREEN + (255,))
        frame.alpha_composite(add_glow(bar, SLAM_HI, 12, 0.9))
        frame.alpha_composite(bar)
    info_rise(frame, info, t, 1.05, 1.6)
    return frame


# ------------------------------------------------------------------- drivers
STYLES = {
    "neon": f_neon,
    "ember": f_ember,
    "glitch": f_glitch,
    "chrome": f_chrome,
    "slam": f_slam,
}


def _audio(style, seconds, path):
    sr = 48000
    n = int(seconds * sr)
    t = np.linspace(0, seconds, n, endpoint=False)
    out = np.zeros(n, np.float32)
    hit_at = {"neon": 0.60, "ember": 0.55, "glitch": 0.82,
              "chrome": 0.70, "slam": 0.50}[style]

    # whoosh / riser into the hit
    noise = np.convolve(np.random.randn(n), np.ones(80) / 80, mode="same")
    swell = np.clip(t / hit_at, 0, 1) ** 2 * (t < hit_at + 0.02)
    out += noise.astype(np.float32) * swell * (0.6 if style != "chrome" else 0.4)

    # boom
    hit = t - hit_at
    env = np.exp(-np.clip(hit, 0, None) * (12 if style == "slam" else 8)) * (hit >= 0)
    out += (np.sin(2*np.pi*58*t) * 0.9 + np.sin(2*np.pi*92*t) * 0.4) * env

    if style == "glitch":  # digital stutter zaps before the lock
        for ti in (0.15, 0.3, 0.45, 0.6):
            z = np.exp(-np.clip(t - ti, 0, None) * 40) * (t >= ti)
            out += np.sign(np.sin(2*np.pi*1200*t)) * z * 0.15
    if style in ("chrome", "neon", "ember"):  # shimmer tail
        tail = np.exp(-np.clip(t - (hit_at + 0.05), 0, None) * 2.2) * (t >= hit_at)
        out += (np.sin(2*np.pi*880*t) + np.sin(2*np.pi*1320*t)) * tail * 0.05
    if style == "slam":  # sub drop
        sub = np.exp(-np.clip(t - hit_at, 0, None) * 5) * (t >= hit_at)
        out += np.sin(2*np.pi*(120 - 70*np.clip((t-hit_at)/0.4,0,1))*t) * sub * 0.5

    fade = np.ones(n, np.float32)
    fi, fo = int(0.01*sr), int(0.25*sr)
    fade[:fi] = np.linspace(0, 1, fi)
    fade[-fo:] = np.linspace(1, 0, fo)
    out *= fade
    out = np.tanh(out * 1.4)
    out = (out / max(1e-6, np.max(np.abs(out))) * 0.92 * 32767).astype(np.int16)
    with wave.open(path, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(out.tobytes())


def render_style(style, seconds, fps):
    fn = STYLES[style]
    # Output stem is brand-overridable so one generator serves every brand
    # without clobbering another brand's files (default keeps HP's names).
    name = os.getenv("OUTRO_NAME", "hp-outro")
    sub = os.getenv("OUTRO_SUBDIR", "")
    sdir = os.path.join(OUT_DIR, sub, style) if sub else os.path.join(OUT_DIR, style)
    fdir = os.path.join(sdir, "frames")
    os.makedirs(fdir, exist_ok=True)
    for f in os.listdir(fdir):
        os.remove(os.path.join(fdir, f))

    mark = build_mark()
    info = build_info()
    ctx = {
        "mark": mark,
        "glow": add_glow(mark, GREEN_HI, 40, 1.0),
        "info": info,
        "bg": base_dark(green_pool=1.0 if style != "glitch" else 0.6),
        "embers": _ember_field() if style == "ember" else None,
        "chrome": _chrome_mark(mark) if style == "chrome" else None,
    }
    n = int(round(seconds * fps))
    print(f"[{style}] rendering {n} frames")
    for i in range(n):
        frame = fn(i / fps, seconds, ctx)
        frame.convert("RGB").save(os.path.join(fdir, f"f{i:04d}.png"))

    silent = os.path.join(sdir, f"{name}-{style}-silent.mp4")
    withaud = os.path.join(sdir, f"{name}-{style}.mp4")
    wav = os.path.join(sdir, "sting.wav")
    subprocess.run(["ffmpeg", "-y", "-framerate", str(fps), "-i",
                    os.path.join(fdir, "f%04d.png"), "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-crf", "16", "-preset", "slow",
                    "-movflags", "+faststart", silent],
                   check=True, capture_output=True)
    _audio(style, seconds, wav)
    subprocess.run(["ffmpeg", "-y", "-i", silent, "-i", wav, "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest",
                    "-movflags", "+faststart", withaud],
                   check=True, capture_output=True)
    Image.open(os.path.join(fdir, f"f{n-1:04d}.png")).save(
        os.path.join(sdir, f"{name}-{style}-poster.jpg"), quality=92)
    print(f"[{style}] -> {withaud}")
    return withaud


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--style", choices=list(STYLES) + ["all"], default="all")
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--fps", type=int, default=30)
    a = ap.parse_args()
    styles = list(STYLES) if a.style == "all" else [a.style]
    for s in styles:
        render_style(s, a.seconds, a.fps)
    print("DONE", styles)


if __name__ == "__main__":
    raise SystemExit(main())
