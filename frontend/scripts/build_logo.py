"""Rebuild public/logo.png, the favicons and the link-preview images from the
Terendex logo in brand/.

The source is already clean artwork on a transparent background, so there is
nothing to de-noise here - the work is trimming it to its own edges, sizing it
for each place it appears, and drawing the introduction card around it.

Output size must stay in step with LOGO_WIDTH / LOGO_HEIGHT in
src/lib/config.ts, which are sent as og:image:width / og:image:height.

Run: python frontend/scripts/build_logo.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "brand" / "terendex.png"
OUT = ROOT / "public" / "logo.png"
SIZE = 800  # keep in step with LOGO_WIDTH/LOGO_HEIGHT in src/lib/config.ts
ICON_DIR = ROOT / "public"

# The mark sits in a square with this much of the square left as air, so it
# never touches the edge of the round plate the header draws behind it.
PADDING = 0.06

# The palette, copied from src/lib/poster/theme.ts - which in turn takes it
# from this logo, so the card and a generated poster read as one publication.
PURPLE = (76, 42, 123)
MUTED = (106, 90, 128)
GOLD = (201, 162, 39)
WHITE = (255, 255, 255)

# The wings are fine at 180px and mush at 16, so the small icons get their
# edges put back afterwards.
FAVICON_SHARPEN = 130

# What Messenger draws when the site's own link is shared, rather than one
# announcement's. The wording must stay in step with SITE_NAME / SITE_INTRO /
# DEPLOYED_SITE_URL in src/lib/config.ts - this is that same introduction,
# drawn rather than written.
INTRO_EYEBROW = "SAINT LOUIS COLLEGE - CITY OF SAN FERNANDO, LA UNION"
INTRO_TITLE = "Terendex's Announcement Services"
INTRO_BODY = (
    "Exam schedules, class suspensions, events and requirements for BSIT "
    "students - posted the moment they are announced."
)
INTRO_FOOTER = "bsit-4-school-annoucement-system-ma.vercel.app"

# Segoe UI is what the site and the poster maker ask for first; the fallbacks
# are only so this script still runs somewhere other than Windows.
BOLD_FONTS = ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf")
REGULAR_FONTS = ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf")


def main():
    mark = square_mark(SIZE)
    mark.save(OUT, "PNG", optimize=True)
    print(f"wrote {OUT} ({SIZE}x{SIZE}, {OUT.stat().st_size / 1024:.0f} KB)")

    build_favicons(mark)
    build_og_fallback(mark)
    build_og_intro(mark)


def square_mark(size):
    """The logo trimmed to its own edges and centred in a transparent square.

    The artwork is wider than it is tall and carries uneven empty margins, so
    centring the *file* leaves the bird sitting off-centre in the header's
    round plate. Centring what is actually drawn fixes that once, here, rather
    than with a nudge in every stylesheet that places it.
    """
    art = Image.open(SRC).convert("RGBA")
    art = art.crop(art.getbbox())

    inner = round(size * (1 - PADDING * 2))
    art.thumbnail((inner, inner), Image.LANCZOS)

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(art, ((size - art.width) // 2, (size - art.height) // 2))
    return canvas


def build_favicons(mark):
    """Write the favicons from the mark.

    A tab icon is 16px and the wings are the first thing to disappear at that
    size, so rather than a plain resize each small size is unsharp-masked
    afterwards - which keeps the silhouette readable instead of averaging the
    feathers into a grey smudge.
    """

    def icon(size):
        im = mark.resize((size, size), Image.LANCZOS)
        return im.filter(
            ImageFilter.UnsharpMask(radius=1, percent=FAVICON_SHARPEN, threshold=0)
        )

    png32 = ICON_DIR / "favicon-32.png"
    icon(32).save(png32, "PNG", optimize=True)

    # Large enough that the mark reads properly; no sharpening needed. Apple
    # squares off and opaques the icon anyway, so it is given a white ground
    # rather than letting the platform pick one.
    png180 = ICON_DIR / "apple-touch-icon.png"
    on_white(mark.resize((180, 180), Image.LANCZOS)).save(png180, "PNG", optimize=True)

    # Each size rendered and tuned separately, rather than letting the ICO
    # writer downscale one bitmap for all of them.
    ico = ICON_DIR / "favicon.ico"
    icon(48).save(ico, "ICO", sizes=[(16, 16), (32, 32), (48, 48)])

    for path in (ico, png32, png180):
        print(f"wrote {path.name} ({path.stat().st_size / 1024:.1f} KB)")


def on_white(image):
    """Flatten a transparent mark onto white, for the places that need opaque."""
    ground = Image.new("RGB", image.size, WHITE)
    ground.paste(image, (0, 0), image)
    return ground


def build_og_fallback(mark):
    """Write the link-preview image used when an announcement has no photo.

    Facebook and Messenger crop to about 1.91:1, so a square logo would lose
    its top and bottom. This centres it on a 1200x630 canvas instead, which is
    the shape they expect.
    """
    W, H = 1200, 630
    canvas = Image.new("RGB", (W, H), WHITE)
    badge = mark.copy()
    badge.thumbnail((int(H * 0.82), int(H * 0.82)), Image.LANCZOS)
    canvas.paste(badge, ((W - badge.width) // 2, (H - badge.height) // 2), badge)

    out = ICON_DIR / "og-default.png"
    canvas.quantize(colors=128, method=Image.MEDIANCUT).save(out, "PNG", optimize=True)
    print(f"wrote {out.name} ({W}x{H}, {out.stat().st_size / 1024:.0f} KB)")


def build_og_intro(mark):
    """Write the link preview for the site's own address.

    Sharing the site itself arrived as the bare logo - the same picture an
    announcement with no photo gets, which said nothing about what was behind
    the link. This draws the introduction instead: who the site is for and
    what is posted on it, readable in the chat without opening anything.

    It is the poster maker's page laid out by hand - the same 1200x630 canvas,
    the same purple rules top and bottom, the same palette - so a generated
    poster and this card sit in a thread as one design.
    """
    W, H = 1200, 630
    FRAME_TOP, FRAME_BOTTOM = 14, 18  # the rules every poster is framed with
    canvas = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, W, FRAME_TOP), fill=PURPLE)
    draw.rectangle((0, H - FRAME_BOTTOM, W, H), fill=PURPLE)

    badge = mark.copy()
    badge.thumbnail((330, 330), Image.LANCZOS)
    badge_x = 82
    canvas.paste(badge, (badge_x, (H - badge.height) // 2), badge)

    left = badge_x + badge.width + 44
    width = (W - 82) - left

    eyebrow_font = load_font(BOLD_FONTS, 21)
    title_font = load_font(BOLD_FONTS, 58)
    body_font = load_font(REGULAR_FONTS, 28)
    footer_font = load_font(REGULAR_FONTS, 22)

    title_lines = wrap_text(draw, INTRO_TITLE, title_font, width)
    body_lines = wrap_text(draw, INTRO_BODY, body_font, width)

    TITLE_LEADING, BODY_LEADING = 68, 40
    RULE_W, RULE_H = 64, 6
    # Measured before anything is drawn, so the block sits on the canvas's
    # centre line whatever the wrapping turns out to be.
    block = (
        26 + 28
        + len(title_lines) * TITLE_LEADING + 24
        + RULE_H + 28
        + len(body_lines) * BODY_LEADING + 30
        + 26
    )
    y = (H - block) // 2

    draw_tracked(draw, (left, y), INTRO_EYEBROW, eyebrow_font, MUTED, 1.6)
    y += 26 + 28

    for line in title_lines:
        draw.text((left, y), line, font=title_font, fill=PURPLE, anchor="la")
        y += TITLE_LEADING
    y += 24

    draw.rectangle((left, y, left + RULE_W, y + RULE_H), fill=GOLD)
    y += RULE_H + 28

    for line in body_lines:
        draw.text((left, y), line, font=body_font, fill=MUTED, anchor="la")
        y += BODY_LEADING
    y += 30

    draw.text((left, y), INTRO_FOOTER, font=footer_font, fill=PURPLE, anchor="la")

    out = ICON_DIR / "og-intro.png"
    # More colours than a flat logo needs: this one carries antialiased type
    # and a gold rule, and 64 bands the letter edges.
    canvas.quantize(colors=128, method=Image.MEDIANCUT).save(out, "PNG", optimize=True)
    print(f"wrote {out.name} ({W}x{H}, {out.stat().st_size / 1024:.0f} KB)")


def load_font(names, size):
    """The first of `names` the machine actually has, at `size`."""
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap_text(draw, text, font, max_width):
    """Greedy word wrap - the card carries two or three lines, not prose."""
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if line and draw.textlength(candidate, font=font) > max_width:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    return lines


def draw_tracked(draw, xy, text, font, fill, tracking):
    """Letter-spaced caps for the eyebrow, which Pillow has no setting for."""
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=font, fill=fill, anchor="la")
        x += draw.textlength(char, font=font) + tracking


if __name__ == "__main__":
    main()
