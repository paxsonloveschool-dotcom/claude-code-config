"""Tests for the branded image-card renderer. Skips cleanly if Pillow absent."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import PIL  # noqa: F401
    _HAS_PIL = True
except Exception:  # noqa: BLE001
    _HAS_PIL = False

from services.media import card  # noqa: E402  (import works without PIL)


def test_renders_png_with_expected_size():
    if not _HAS_PIL:
        print("  SKIP test_renders_png_with_expected_size (no Pillow)")
        return
    from PIL import Image

    with tempfile.TemporaryDirectory() as d:
        out = str(Path(d) / "card.png")
        ret = card.render_card("Spring is here — book your tune-up today!", out,
                               brand_name="HP Landscaping", theme="green")
        assert ret == out
        assert Path(out).exists()
        with Image.open(out) as im:
            assert im.format == "PNG"
            assert im.size == (1080, 1350)


def test_long_text_still_fits_and_renders():
    if not _HAS_PIL:
        print("  SKIP test_long_text_still_fits_and_renders (no Pillow)")
        return
    from PIL import Image

    long_text = ("Water damage emergency? Every minute counts. " * 12).strip()
    with tempfile.TemporaryDirectory() as d:
        out = str(Path(d) / "long.png")
        card.render_card(long_text, out, brand_name="Restore", theme="blue")
        with Image.open(out) as im:
            assert im.size == (1080, 1350)  # font auto-shrank to fit


def test_custom_size_and_colors():
    if not _HAS_PIL:
        print("  SKIP test_custom_size_and_colors (no Pillow)")
        return
    from PIL import Image

    with tempfile.TemporaryDirectory() as d:
        out = str(Path(d) / "sq.png")
        card.render_card("Hello", out, size=(1080, 1080), bg="#000000", fg="#ffffff")
        with Image.open(out) as im:
            assert im.size == (1080, 1080)


def test_creates_missing_output_dir():
    if not _HAS_PIL:
        print("  SKIP test_creates_missing_output_dir (no Pillow)")
        return
    with tempfile.TemporaryDirectory() as d:
        out = str(Path(d) / "nested" / "deep" / "card.png")
        card.render_card("x", out)
        assert Path(out).exists()


def _run():
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  PASS {name}")
            passed += 1
    print(f"\n{passed} tests passed.")


if __name__ == "__main__":
    _run()
