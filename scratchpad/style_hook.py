#!/usr/bin/env python3
# Hook caption engine v2 — renders each caption to a PNG with PIL (self-consistent
# kerning + per-word accent color + heavy black stroke), then overlays it PERFECTLY
# centered with ffmpeg (x=(W-w)/2) and a quick fade in/out. Fixes the off-center /
# loose-spacing drift of the old drawtext word-by-word layout.
#
# Usage: style_hook.py IN.mp4 OUT.mp4 events.json [accent] [font] [mode]
#   accent: color name (yellow|amber|coral|green|white|red|cyan) or 0xRRGGBB (default coral)
#   font  : shortname (bigshoulders|boldonse|bricolage|outfit|worksans) or a path
#   mode  : plain (default). (box reserved)
# events.json = [ {"start":0,"end":1.6,"text":"...","accent":"WORD","y":0.72,
#                  "size":0.085,"hook":true,"keepcase":false}, ... ]
import sys, json, subprocess, os
from PIL import Image, ImageFont, ImageDraw

inp, outp, evpath = sys.argv[1], sys.argv[2], sys.argv[3]
accent_arg = sys.argv[4] if len(sys.argv) > 4 else "coral"
font_arg   = sys.argv[5] if len(sys.argv) > 5 else "bigshoulders"

FDIR = "/mnt/skills/examples/canvas-design/canvas-fonts/"
FONTS = {"bigshoulders": FDIR + "BigShoulders-Bold.ttf", "boldonse": FDIR + "Boldonse-Regular.ttf",
         "bricolage": FDIR + "BricolageGrotesque-Bold.ttf", "outfit": FDIR + "Outfit-Bold.ttf",
         "worksans": FDIR + "WorkSans-Bold.ttf"}
COLORS = {"yellow": "#F5D020", "amber": "#FFB020", "coral": "#FF6B4A", "green": "#20B040",
          "white": "#FFFFFF", "red": "#F23A2F", "cyan": "#28E0D0", "orange": "#FF7A1A", "lime": "#B6FF3C"}
FONT = FONTS.get(font_arg.lower(), font_arg if "/" in font_arg else FONTS["bigshoulders"])
ACCENT = COLORS.get(accent_arg.lower(), accent_arg if accent_arg.startswith("#") else COLORS["coral"])

r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                    "stream=width,height", "-of", "json", inp], capture_output=True, text=True)
j = json.loads(r.stdout)
W, H = int(j["streams"][0]["width"]), int(j["streams"][0]["height"])
events = json.load(open(evpath))

work = os.path.join(os.path.dirname(os.path.abspath(outp)) or ".", "_caps")
os.makedirs(work, exist_ok=True)
MAXW = W * 0.92

def render_png(ev, idx):
    txt = ev["text"] if ev.get("keepcase") else ev["text"].upper()
    sf = ev.get("size", 0.11 if ev.get("hook") else 0.085)
    sz = int(W * sf)
    font = ImageFont.truetype(FONT, sz)
    if font.getlength(txt) > MAXW:                       # auto-fit to width
        sz = max(24, int(sz * MAXW / font.getlength(txt)))
        font = ImageFont.truetype(FONT, sz)
    accent = (ev.get("accent") or "")
    if not ev.get("keepcase"):
        accent = accent.upper()
    # prefix / accent / suffix by character index (keeps natural kerning + spaces)
    if accent and accent in txt:
        i = txt.index(accent)
        parts = [(txt[:i], "#FFFFFF"), (accent, ACCENT), (txt[i + len(accent):], "#FFFFFF")]
    else:
        parts = [(txt, "#FFFFFF")]
    parts = [(t, c) for t, c in parts if t != ""]
    stroke = max(6, int(W * 0.0065))
    total = font.getlength(txt)
    asc, desc = font.getmetrics()
    pad = stroke * 2 + 8
    img = Image.new("RGBA", (int(total) + pad * 2, asc + desc + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x = float(pad)
    for t, col in parts:
        d.text((x, pad), t, font=font, fill=col, stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
        x += font.getlength(t)
    p = os.path.join(work, f"cap{idx}.png")
    img.save(p)
    return p

FI, FO = 0.08, 0.10   # snap on, hold fully solid, quick clean fade to fully gone
inputs, filt, prev = ["-i", inp], [], "[0:v]"
for i, ev in enumerate(events):
    png = render_png(ev, i)
    start, end = float(ev["start"]), float(ev["end"])
    yf = ev.get("y", 0.30 if ev.get("hook") else 0.72)
    dur = end - start + FO + 0.05
    inputs += ["-loop", "1", "-itsoffset", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", png]
    idx = i + 1
    cap = f"[c{i}]"
    filt.append(f"[{idx}:v]format=rgba,fade=t=in:st={start:.3f}:d={FI}:alpha=1,"
                f"fade=t=out:st={end:.3f}:d={FO}:alpha=1{cap}")
    out = f"[v{i}]"
    filt.append(f"{prev}{cap}overlay=x=(W-w)/2:y=H*{yf}-h/2:eval=init{out}")
    prev = out

fc = ";".join(filt)
subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", *inputs,
                "-filter_complex", fc, "-map", prev, "-map", "0:a?",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "aac", outp], check=True)
print("OK", outp, "|", font_arg, accent_arg)
