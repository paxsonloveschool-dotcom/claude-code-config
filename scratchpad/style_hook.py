#!/usr/bin/env python3
# Hook-first caption engine: timed ALL-CAPS chunks that pop in (fade), hold, pop
# out — Hormozi style. Word-based layout with explicit gaps (ffmpeg drawtext trims
# leading spaces). Accent words get a highlight color. Heavy black stroke (plain)
# or filled karaoke boxes (box mode) for muted legibility. Auto-fits to width.
#
# Usage: style_hook.py IN.mp4 OUT.mp4 events.json [accent] [font] [mode]
#   accent : color name (yellow|green|white|red|cyan|orange) or 0xRRGGBB. default yellow
#   font   : shortname (bigshoulders|boldonse|bricolage|outfit|worksans) or a path
#   mode   : plain (stroke) | box (filled karaoke boxes). default plain
# events.json = [ {"start":0,"end":1.4,"text":"...","accent":"WORD","y":0.72,
#                  "size":0.085,"hook":true}, ... ]
import sys, json, subprocess
from PIL import ImageFont

inp, outp, evpath = sys.argv[1], sys.argv[2], sys.argv[3]
accent_arg = sys.argv[4] if len(sys.argv) > 4 else "yellow"
font_arg   = sys.argv[5] if len(sys.argv) > 5 else "bigshoulders"
mode       = sys.argv[6] if len(sys.argv) > 6 else "plain"

FDIR = "/mnt/skills/examples/canvas-design/canvas-fonts/"
FONTS = {
    "bigshoulders": FDIR + "BigShoulders-Bold.ttf",
    "boldonse":     FDIR + "Boldonse-Regular.ttf",
    "bricolage":    FDIR + "BricolageGrotesque-Bold.ttf",
    "outfit":       FDIR + "Outfit-Bold.ttf",
    "worksans":     FDIR + "WorkSans-Bold.ttf",
}
COLORS = {
    "yellow": "0xF5D020", "green": "0x20B040", "white": "0xFFFFFF",
    "red": "0xF23A2F", "cyan": "0x28E0D0", "orange": "0xFF7A1A", "lime": "0xB6FF3C",
    "amber": "0xFFB020", "coral": "0xFF6B4A",  # best pops over green/earth footage
}
FONT = FONTS.get(font_arg.lower(), font_arg if "/" in font_arg else FONTS["bigshoulders"])
ACCENT = COLORS.get(accent_arg.lower(), accent_arg if accent_arg.startswith("0x") else COLORS["yellow"])
BOXACC = ACCENT            # accent-word box color in box mode
BOXBG  = "black@0.82"      # normal-word box color in box mode

r = subprocess.run(["ffprobe","-v","error","-select_streams","v:0",
                    "-show_entries","stream=width,height","-show_entries","format=duration",
                    "-of","json", inp], capture_output=True, text=True)
j = json.loads(r.stdout)
W, H = int(j["streams"][0]["width"]), int(j["streams"][0]["height"])
events = json.load(open(evpath))

def esc(t):
    return t.replace("\\","").replace(":","\\:").replace("'","’").replace("%","\\%")

def measure(font, s):
    return font.getlength(s)  # advance width incl spaces

nodes, prev = [], "0:v"
FI, FO = 0.14, 0.18
MAXW = W * 0.94
for k, ev in enumerate(events):
    # keepcase=True renders text as written (POV/casual look); default is ALL CAPS
    txt = ev["text"] if ev.get("keepcase") else ev["text"].upper()
    hook = ev.get("hook", False)
    yf = ev.get("y", 0.30 if hook else 0.72)
    sf = ev.get("size", 0.11 if hook else 0.085)
    sz = int(W * sf)
    font = ImageFont.truetype(FONT, sz)
    full = measure(font, txt)
    if full > MAXW:
        sz = max(24, int(sz * MAXW / full)); font = ImageFont.truetype(FONT, sz)
    accent = (ev.get("accent") or "").strip()
    if not ev.get("keepcase"):
        accent = accent.upper()
    start, end = float(ev["start"]), float(ev["end"])
    toutf = round(end + FO, 3); tin = round(start + FI, 3)
    fin  = f"if(lt(t\\,{start})\\,0\\,if(lt(t\\,{tin})\\,(t-{start})/{FI}\\,1))"
    fout = f"if(lt(t\\,{end})\\,1\\,if(lt(t\\,{toutf})\\,({toutf}-t)/{FO}\\,0))"
    alpha = f"({fin})*({fout})"
    sh = max(6, int(W * 0.006))

    tokens = txt.split()
    acc = accent.split()
    astart = -1
    if acc:
        for s in range(len(tokens) - len(acc) + 1):
            if tokens[s:s + len(acc)] == acc:
                astart = s; break
    is_acc = [astart >= 0 and astart <= idx < astart + len(acc) for idx in range(len(tokens))]
    space = measure(font, " ")
    wws = [measure(font, t) for t in tokens]
    boxbw = int(sz * 0.16)
    # in box mode each word carries its own padded box → widen the gap a touch
    gap = space + (boxbw * 1.4 if mode == "box" else 0)
    total = sum(wws) + gap * (len(tokens) - 1)
    x = (W - total) / 2.0
    y = f"(h*{yf})-({sz}*0.5)"
    for wi, (tok, wd, acc_hit) in enumerate(zip(tokens, wws, is_acc)):
        if mode == "box":
            col = "black" if acc_hit else "white"
            box = f":box=1:boxcolor={BOXACC if acc_hit else BOXBG}:boxborderw={boxbw}"
            stroke = ""
        else:
            col = ACCENT if acc_hit else "white"
            box = ""
            stroke = f":borderw={sh}:bordercolor=black@0.98:shadowcolor=black@0.9:shadowx={sh//2}:shadowy={sh//2}"
        dt = (f"drawtext=fontfile={FONT}:text='{esc(tok)}':fontcolor={col}:fontsize={sz}:"
              f"x={int(x)}:y={y}{box}{stroke}:alpha='{alpha}'")
        out = f"v{k}_{wi}"
        nodes.append(f"[{prev}]{dt}[{out}]")
        prev = out
        x += wd + gap

fc = ";".join(nodes)
subprocess.run(["ffmpeg","-nostdin","-loglevel","error","-y","-i",inp,
                "-filter_complex", fc, "-map", f"[{prev}]", "-map", "0:a?",
                "-c:v","libx264","-preset","veryfast","-crf","18","-pix_fmt","yuv420p",
                "-c:a","aac", outp], check=True)
print("OK", outp, "|", font_arg, accent_arg, mode)
