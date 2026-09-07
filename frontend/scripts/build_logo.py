"""Rebuild public/logo.png and the favicons from the original seal in brand/.

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
ICON_DIR = ROOT / "public"
# How much of the seal the favicon keeps - just the central crest.
CREST_FRACTION = 0.30


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

    build_favicons(clean)


def build_favicons(seal):
    """Crop to the central shield for the favicon.

    The full seal has ring text that turns to mush at 16px, so the tab icon
    uses just the crest, with a little white margin so it does not touch the
    edges of the tab.
    """
    w, h = seal.size
    half = int(w * CREST_FRACTION / 2)
    crest = seal.crop((w // 2 - half, h // 2 - half, w // 2 + half, h // 2 + half))

    pad = int(crest.width * 0.08)
    padded = Image.new("RGB", (crest.width + pad * 2, crest.height + pad * 2), WHITE)
    padded.paste(crest, (pad, pad))

    png32 = ICON_DIR / "favicon-32.png"
    padded.resize((32, 32), Image.LANCZOS).save(png32, "PNG", optimize=True)

    png180 = ICON_DIR / "apple-touch-icon.png"
    padded.resize((180, 180), Image.LANCZOS).save(png180, "PNG", optimize=True)

    ico = ICON_DIR / "favicon.ico"
    padded.resize((64, 64), Image.LANCZOS).save(
        ico, "ICO", sizes=[(16, 16), (32, 32), (48, 48)]
    )

    for path in (ico, png32, png180):
        print(f"wrote {path.name} ({path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
