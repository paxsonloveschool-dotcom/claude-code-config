"""Reproduce the official HP Landscaping logo as a crisp transparent PNG.
Matches the uploaded asset: white-outlined black cross with a thin inscribed
cross, green HP monogram (black keyline), and a white LANDSCAPING box.
Designed to read on a pure-black background.
"""
import os
from PIL import Image, ImageDraw, ImageFont

S = 4
W, H = 600 * S, 730 * S
GREEN = (52, 192, 80)
BLACK = (8, 8, 8)
WHITE = (250, 250, 250)
CX = W // 2

img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

FONT = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"


def f(sz):
    return ImageFont.truetype(FONT, sz)


def cross(cx, vy0, vy1, hy0, hy1, hx0, hx1, bw, fill):
    d.rectangle((cx - bw // 2, vy0, cx + bw // 2, vy1), fill=fill)
    d.rectangle((hx0, hy0, hx1, hy1), fill=fill)


# --- cross: white border (outer) then black body then thin white inscribed
bw = 78 * S
vy0, vy1 = 36 * S, 446 * S
hy0, hy1 = 150 * S, 226 * S
hx0, hx1 = CX - 150 * S, CX + 150 * S
b = 12 * S        # white border thickness
# black outer keyline
cross(CX, vy0 - b - 4*S, vy1 + b + 4*S, hy0 - b - 4*S, hy1 + b + 4*S,
      hx0 - b - 4*S, hx1 + b + 4*S, bw + 2*(b+4*S), BLACK)
# white border
cross(CX, vy0 - b, vy1 + b, hy0 - b, hy1 + b, hx0 - b, hx1 + b, bw + 2*b, WHITE)
# black body
cross(CX, vy0, vy1, hy0, hy1, hx0, hx1, bw, BLACK)
# thin inscribed white cross (upper area)
iw = 12 * S
d.rectangle((CX - iw//2, vy0 + 16*S, CX + iw//2, hy1 - 14*S), fill=WHITE)
d.rectangle((hx0 + 30*S, (hy0+hy1)//2 - iw//2, hx1 - 30*S, (hy0+hy1)//2 + iw//2), fill=WHITE)

# --- HP letters: green fill, black keyline, flanking the stem
hp = f(330 * S)
stroke = 16 * S
for ch, dx in (("H", -150 * S), ("P", 150 * S)):
    bb = d.textbbox((0, 0), ch, font=hp, stroke_width=stroke)
    tw = bb[2] - bb[0]
    d.text((CX + dx - tw // 2 - bb[0], 250 * S - bb[1]), ch, font=hp,
           fill=GREEN, stroke_width=stroke, stroke_fill=BLACK)

# re-draw the cross stem over the HP gap so it reads between the letters
cross(CX, vy0 - b, vy1 + b, hy0 - b, hy1 + b, hx0 - b, hx1 + b, bw + 2*b, WHITE)
cross(CX, vy0, vy1, hy0, hy1, hx0, hx1, bw, BLACK)
d.rectangle((CX - iw//2, vy0 + 16*S, CX + iw//2, hy1 - 14*S), fill=WHITE)
d.rectangle((hx0 + 30*S, (hy0+hy1)//2 - iw//2, hx1 - 30*S, (hy0+hy1)//2 + iw//2), fill=WHITE)

# --- LANDSCAPING box: white fill, black outline, black letters
bx0, by0, bx1, by1 = CX - 215*S, 560*S, CX + 215*S, 648*S
d.rounded_rectangle((bx0-7*S, by0-7*S, bx1+7*S, by1+7*S), radius=10*S, fill=BLACK)
d.rounded_rectangle((bx0, by0, bx1, by1), radius=8*S, fill=WHITE)
lf = f(70 * S)
txt = "LANDSCAPING"
# letter-space it
spaced = " ".join(list(txt))
bb = d.textbbox((0, 0), spaced, font=lf)
while bb[2]-bb[0] > (bx1-bx0) - 30*S:
    lf = f(lf.size - 4*S)
    bb = d.textbbox((0, 0), spaced, font=lf)
d.text((CX - (bb[2]-bb[0])//2 - bb[0], (by0+by1)//2 - (bb[3]-bb[1])//2 - bb[1]),
       spaced, font=lf, fill=BLACK)

out = img.resize((W // S, H // S), Image.LANCZOS)
dst = os.path.join(os.path.dirname(__file__), "hp-logo.recreated.png")
out.save(dst)
# preview on black to verify readability
prev = Image.new("RGB", out.size, (0, 0, 0))
prev.paste(out, (0, 0), out)
prev.save(os.path.join(os.path.dirname(__file__), "_logo_on_black.png"))
print("saved", dst, out.size)
