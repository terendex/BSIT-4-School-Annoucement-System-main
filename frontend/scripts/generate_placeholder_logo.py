
"""Draws a placeholder seal at public/logo.png.

Replace public/logo.png with the real Saint Louis College seal; this script
only exists so the site has a working logo and OG fallback before you do.
Run: python frontend/scripts/generate_placeholder_logo.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

NAVY = (31, 42, 107)
SIZE = 1200
OUT = Path(__file__).resolve().parent.parent / "public" / "logo.png"


def font(size, bold=True):
    for name in (("arialbd.ttf", "arial.ttf") if bold else ("arial.ttf",)):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def centered(draw, y, text, f, fill=NAVY, spacing=0):
    if spacing:
        widths = [draw.textlength(ch, font=f) for ch in text]
        total = sum(widths) + spacing * (len(text) - 1)
        x = (SIZE - total) / 2
        for ch, w in zip(text, widths):
            draw.text((x, y), ch, font=f, fill=fill)
            x += w + spacing
        return
    w = draw.textlength(text, font=f)
    draw.text(((SIZE - w) / 2, y), text, font=f, fill=fill)


def main():
    image = Image.new("RGB", (SIZE, SIZE), "white")
    draw = ImageDraw.Draw(image)

    draw.ellipse([20, 20, SIZE - 20, SIZE - 20], outline=NAVY, width=16)
    draw.ellipse([115, 115, SIZE - 115, SIZE - 115], outline=NAVY, width=8)

    # Shield
    left, right, top, shoulder, tip = 430, 770, 330, 640, 830
    draw.polygon(
        [(left, top), (right, top), (right, shoulder), (600, tip), (left, shoulder)],
        fill=NAVY,
    )
    centered(draw, 415, "SLC", font(150), fill="white")

    centered(draw, 175, "SAINT LOUIS COLLEGE", font(64), spacing=2)
    centered(draw, 858, "WISDOM  BUILDS", font(52), spacing=3)
    centered(draw, 928, "1964", font(46))
    centered(draw, 995, "City of San Fernando, La Union", font(38, bold=False))

    image.save(OUT, "PNG")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
