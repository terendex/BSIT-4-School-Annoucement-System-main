"""Rebuild public/logo.png from the original seal in brand/.

The source is a photo/scan, so it is cleaned to a true navy-on-white ramp:
that removes JPEG noise, sharpens the edges, and cuts the file size by more
than half. Output size must stay in step with LOGO_WIDTH / LOGO_HEIGHT in
src/lib/config.ts, which are sent as og:image:width / og:image:height.

Run: python frontend/scripts/build_logo.py
"""
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "brand" / "slclogo.jpg"
OUT = ROOT / "public" / "logo.png"
SIZE = 800  # keep in step with LOGO_WIDTH/LOGO_HEIGHT in src/lib/config.ts
NAVY = (31, 42, 107)
WHITE = (255, 255, 255)


def main():
    src = Image.open(SRC).convert("RGB")
    src.thumbnail((SIZE, SIZE), Image.LANCZOS)

    # Centre on a square white canvas; the seal is circular so the padding
    # is invisible, and a square reads well as an Open Graph fallback.
    canvas = Image.new("RGB", (SIZE, SIZE), WHITE)
    canvas.paste(src, ((SIZE - src.width) // 2, (SIZE - src.height) // 2))

    gray = ImageOps.autocontrast(canvas.convert("L"), cutoff=0.5)
    clean = Image.composite(
        Image.new("RGB", canvas.size, WHITE),
        Image.new("RGB", canvas.size, NAVY),
        gray,
    )
    clean.quantize(colors=32, method=Image.MEDIANCUT).save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT} ({SIZE}x{SIZE}, {OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
