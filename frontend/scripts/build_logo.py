"""Rebuild public/logo.png and the favicons from the original seal in brand/.

The source is a photo/scan, so it is cleaned to a true navy-on-white ramp:
that removes JPEG noise, sharpens the edges, and cuts the file size by more
than half. Output size must stay in step with LOGO_WIDTH / LOGO_HEIGHT in
src/lib/config.ts, which are sent as og:image:width / og:image:height.

Run: python frontend/scripts/build_logo.py
"""
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "brand" / "slclogo.jpg"
OUT = ROOT / "public" / "logo.png"
SIZE = 800  # keep in step with LOGO_WIDTH/LOGO_HEIGHT in src/lib/config.ts
NAVY = (31, 42, 107)
WHITE = (255, 255, 255)
ICON_DIR = ROOT / "public"
# Downscaling averages the seal's fine lines into grey mush, so each favicon
# size gets its contrast and edges restored afterwards.
FAVICON_CONTRAST = 1.7
FAVICON_SHARPEN = 180


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
    build_og_fallback(clean)


def build_favicons(seal):
    """Write the favicons from the full seal.

    The seal is detailed for a 16px tab icon, so rather than a plain resize
    each size is contrast-boosted and unsharp-masked afterwards - that keeps the
    outer ring and the shield readable instead of averaging them into a blob.
    """

    def icon(size):
        im = seal.resize((size, size), Image.LANCZOS)
        im = ImageEnhance.Contrast(im).enhance(FAVICON_CONTRAST)
        return im.filter(
            ImageFilter.UnsharpMask(radius=1, percent=FAVICON_SHARPEN, threshold=0)
        )

    png32 = ICON_DIR / "favicon-32.png"
    icon(32).save(png32, "PNG", optimize=True)

    # Large enough that the seal reads properly; no sharpening needed.
    png180 = ICON_DIR / "apple-touch-icon.png"
    seal.resize((180, 180), Image.LANCZOS).save(png180, "PNG", optimize=True)

    # Each size rendered and tuned separately, rather than letting the ICO
    # writer downscale one bitmap for all of them.
    ico = ICON_DIR / "favicon.ico"
    icon(48).save(ico, "ICO", sizes=[(16, 16), (32, 32), (48, 48)])

    for path in (ico, png32, png180):
        print(f"wrote {path.name} ({path.stat().st_size / 1024:.1f} KB)")



def build_og_fallback(seal):
    """Write the link-preview image used when an announcement has no photo.

    Facebook and Messenger crop to about 1.91:1, so the square seal would lose
    its top and bottom. This centres it on a 1200x630 canvas instead, which is
    the shape they expect.
    """
    W, H = 1200, 630
    canvas = Image.new("RGB", (W, H), WHITE)
    badge = seal.copy()
    badge.thumbnail((int(H * 0.82), int(H * 0.82)), Image.LANCZOS)
    canvas.paste(badge, ((W - badge.width) // 2, (H - badge.height) // 2))

    out = ICON_DIR / "og-default.png"
    canvas.quantize(colors=64, method=Image.MEDIANCUT).save(out, "PNG", optimize=True)
    print(f"wrote {out.name} ({W}x{H}, {out.stat().st_size / 1024:.0f} KB)")

if __name__ == "__main__":
    main()
