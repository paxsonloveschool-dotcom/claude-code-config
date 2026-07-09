#!/usr/bin/env python3
# Hook-first caption engine: timed ALL-CAPS chunks (BigShoulders) that pop in with
# a quick scale/fade, hold ~600-900ms, and pop out — Hormozi style. One word per
# chunk can be an accent (brand green / yellow highlight). Heavy black stroke so it
# reads over any footage, muted. Positioned lower-middle third by default; the hook
# line sits higher/centered.
#
# Usage: style_hook.py IN.mp4 OUT.mp4 events.json
# events.json = [ {"start":0.0,"end":1.4,"text":"THIS WAS A MUD PIT","accent":"MUD PIT",
#                  "y":0.72,"size":0.11,"hook":true}, ... ]
#   start/end   : seconds the chunk is visible (fade handled inside)
#   text        : the caption (auto-uppercased)
#   accent      : optional substring rendered in the accent color (must appear in text)
#   y           : vertical center as a fraction of height (default 0.72)
#   size        : font size as a fraction of width (default 0.085; hook ~0.11)
#   hook        : optional; if true, defaults to bigger + higher (y 0.30, size 0.11)
import sys, json, subprocess
from PIL import ImageFont

inp, outp, evpath = sys.argv[1], sys.argv[2], sys.argv[3]
FONT   = "/mnt/skills/examples/canvas-design/canvas-fonts/BigShoulders-Bold.ttf"
GREEN  = "0x20B040"
YELLOW = "0xF5D020"
ACCENT = YELLOW  # yellow highlight tests best for the key word; swap to GREEN for brand

r = subprocess.run(["ffprobe","-v","error","-select_streams","v:0",
                    "-show_entries","stream=width,height","-show_entries","format=duration",
                    "-of","json", inp], capture_output=True, text=True)
j = json.loads(r.stdout)
W, H = int(j["streams"][0]["width"]), int(j["streams"][0]["height"])

events = json.load(open(evpath))

def esc(t):
    return t.replace("\\","").replace(":","\\:").replace("'","’").replace("%","\\%")

def measure(font, s):
    # advance width (includes leading/trailing spaces); getbbox() would drop them
    return font.getlength(s)

nodes, prev = [], "0:v"
FI, FO = 0.14, 0.18  # quick pop in / out
MAXW = W * 0.94       # keep text inside the frame with a small margin
for k, ev in enumerate(events):
    txt = ev["text"].upper()
    hook = ev.get("hook", False)
    yf = ev.get("y", 0.30 if hook else 0.72)
    sf = ev.get("size", 0.11 if hook else 0.085)
    sz = int(W * sf)
    font = ImageFont.truetype(FONT, sz)
    # auto-fit: shrink so the whole line stays on screen
    full = measure(font, txt)
    if full > MAXW:
        sz = max(24, int(sz * MAXW / full))
        font = ImageFont.truetype(FONT, sz)
    accent = (ev.get("accent") or "").upper().strip()
    start, end = float(ev["start"]), float(ev["end"])
    toutf = round(end + FO, 3)
    tin   = round(start + FI, 3)
    fin  = f"if(lt(t\\,{start})\\,0\\,if(lt(t\\,{tin})\\,(t-{start})/{FI}\\,1))"
    fout = f"if(lt(t\\,{end})\\,1\\,if(lt(t\\,{toutf})\\,({toutf}-t)/{FO}\\,0))"
    alpha = f"({fin})*({fout})"
    sh = max(6, int(W * 0.006))  # heavy stroke for muted legibility

    # Word-based layout: draw each WORD separately with an explicit space gap
    # (ffmpeg drawtext trims leading spaces, so we never bake spaces into a drawn
    # string). Words inside the accent phrase get the highlight color.
    tokens = txt.split()
    acc = accent.split()
    astart = -1
    if acc:
        for s in range(len(tokens) - len(acc) + 1):
            if tokens[s:s + len(acc)] == acc:
                astart = s
                break
    colors = [ACCENT if (astart >= 0 and astart <= idx < astart + len(acc)) else "white"
              for idx in range(len(tokens))]
    space = measure(font, " ")
    wws = [measure(font, t) for t in tokens]
    total = sum(wws) + space * (len(tokens) - 1)
    x = (W - total) / 2.0
    y = f"(h*{yf})-({sz}*0.5)"
    for wi, (tok, col, wd) in enumerate(zip(tokens, colors, wws)):
        dt = (f"drawtext=fontfile={FONT}:text='{esc(tok)}':fontcolor={col}:fontsize={sz}:"
              f"x={int(x)}:y={y}:borderw={sh}:bordercolor=black@0.98:"
              f"shadowcolor=black@0.9:shadowx={sh//2}:shadowy={sh//2}:alpha='{alpha}'")
        out = f"v{k}_{wi}"
        nodes.append(f"[{prev}]{dt}[{out}]")
        prev = out
        x += wd + space

fc = ";".join(nodes)
subprocess.run(["ffmpeg","-nostdin","-loglevel","error","-y","-i",inp,
                "-filter_complex", fc, "-map", f"[{prev}]", "-map", "0:a?",
                "-c:v","libx264","-preset","veryfast","-crf","18","-pix_fmt","yuv420p",
                "-c:a","aac", outp], check=True)
print("OK", outp)
