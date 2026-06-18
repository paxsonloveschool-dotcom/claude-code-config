"""Render a post's text into a branded image — an Instagram-ready quote card.

Instagram (unlike Facebook) requires an image/video at a public URL. For
text-first posts that have no photo, this turns the caption into a clean
branded card so the post can still go to IG. Pillow is a lazy/optional import
(the ``cards`` extra), so importing this module never forces the dependency.

Typical use::

    from services.media.card import render_card
    render_card("Spring is here — book your tune-up!", "out.png",
                brand_name="HP Landscaping", theme="green")

The rendered PNG is committed to the repo (or any host) and its public URL goes
into the post's ``media_url``; the platform then fetches it server-side.
"""

from __future__ import annotations

import os

# A few simple brand themes (background, text, accent). Pick with ``theme=`` or
# pass explicit colors. Defaults read well at a glance on a phone feed.
THEMES = {
    "green": {"bg": "#0f5132", "fg": "#ffffff", "accent": "#a3d9b1"},   # landscaping
    "blue": {"bg": "#0b3d66", "fg": "#ffffff", "accent": "#9ec9e8"},    # restoration
    "dark": {"bg": "#111827", "fg": "#ffffff", "accent": "#9ca3af"},
    "light": {"bg": "#f8fafc", "fg": "#0f172a", "accent": "#475569"},
}

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
)


def _load_font(size: int):
    """A bold scalable font: a real TTF if we can find one, else Pillow's
    built-in scalable default (Pillow >= 10)."""
    from PIL import ImageFont  # lazy

    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    """Greedy word-wrap so each line fits ``max_width`` pixels."""
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def render_card(
    text: str,
    out_path: str,
    *,
    brand_name: str | None = None,
    theme: str = "green",
    size: tuple[int, int] = (1080, 1350),
    bg: str | None = None,
    fg: str | None = None,
    accent: str | None = None,
    max_font_size: int = 84,
    min_font_size: int = 36,
) -> str:
    """Render ``text`` as a centered branded card PNG at ``out_path``.

    The font size auto-shrinks (between ``min`` and ``max``) until the wrapped
    text fits the card with comfortable margins. ``brand_name`` is drawn small
    at the bottom. Returns ``out_path``.
    """
    from PIL import Image, ImageDraw  # lazy

    palette = THEMES.get(theme, THEMES["green"])
    bg = bg or palette["bg"]
    fg = fg or palette["fg"]
    accent = accent or palette["accent"]

    w, h = size
    margin = int(w * 0.10)
    max_text_w = w - 2 * margin
    # Leave room at the bottom for the brand name.
    max_text_h = h - 2 * margin - (90 if brand_name else 0)

    img = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(img)

    # Shrink the font until the wrapped block fits both width and height.
    font_size = max_font_size
    while font_size >= min_font_size:
        font = _load_font(font_size)
        lines = _wrap(draw, text, font, max_text_w)
        line_h = int(font_size * 1.25)
        block_h = line_h * len(lines)
        widest = max((draw.textlength(ln, font=font) for ln in lines), default=0)
        if block_h <= max_text_h and widest <= max_text_w:
            break
        font_size -= 6
    else:
        font = _load_font(min_font_size)
        lines = _wrap(draw, text, font, max_text_w)
        line_h = int(min_font_size * 1.25)
        block_h = line_h * len(lines)

    # Vertically center the text block.
    y = (h - block_h) // 2
    if brand_name:
        y -= 30
    for ln in lines:
        lw = draw.textlength(ln, font=font)
        draw.text(((w - lw) // 2, y), ln, font=font, fill=fg)
        y += line_h

    if brand_name:
        bn_font = _load_font(40)
        label = brand_name.upper()
        lw = draw.textlength(label, font=bn_font)
        draw.text(((w - lw) // 2, h - margin - 10), label, font=bn_font, fill=accent)

    out_dir = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(out_dir, exist_ok=True)
    img.save(out_path, format="PNG")
    return out_path


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Render a branded quote-card PNG.")
    parser.add_argument("text", help="The caption/quote to render.")
    parser.add_argument("out_path", help="Output PNG path.")
    parser.add_argument("--brand", dest="brand_name", default=None, help="Brand name (footer).")
    parser.add_argument("--theme", default="green", choices=sorted(THEMES), help="Color theme.")
    parser.add_argument("--square", action="store_true", help="1080x1080 instead of 1080x1350.")
    args = parser.parse_args(argv)

    size = (1080, 1080) if args.square else (1080, 1350)
    out = render_card(args.text, args.out_path, brand_name=args.brand_name,
                      theme=args.theme, size=size)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
