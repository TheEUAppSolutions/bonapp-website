#!/usr/bin/env python3
"""Generate the two raster images the HTML references but that aren't app artwork:

    assets/img/apple-touch-icon.png   180x180, full-bleed (iOS applies its own mask)
    assets/img/og.png                 1200x630 social card

Run after fetch_assets.py, because the card composites real app icons.
Needs Pillow and rsvg-convert (both already used elsewhere on this machine).
"""
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "assets" / "img"

BG = (10, 10, 12)
INK = (250, 250, 250)
INK_2 = (140, 140, 150)
GRAD_A = (52, 211, 153)
GRAD_B = (4, 120, 87)

FONT_FILES = [
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Supplemental/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
]
# face names to try per weight, in order — indexes differ between macOS versions, so
# resolve by name rather than hardcoding a collection index
WEIGHTS = {
    "bold": ("Bold",),
    "medium": ("Medium", "Bold", "Regular"),
    "regular": ("Regular",),
}

# a full-bleed square version of the mark: iOS rounds the corners itself, so the
# rounded rect in mark.svg would leave a double-rounded edge on the home screen
TOUCH_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#34D399"/><stop offset="1" stop-color="#047857"/>
</linearGradient></defs>
<rect width="32" height="32" fill="url(#g)"/>
<path d="M11 10.5h6.5a3.3 3.3 0 0 1 0 6.6H11zM11 17.1h7.4a3.3 3.3 0 0 1 0 6.6H11z" fill="#fff"/>
<path d="M11 8.4v15.3" stroke="#fff" stroke-width="2.6" stroke-linecap="round"/></svg>
"""


def load_fonts():
    """Return font(size, weight) resolved from whichever system family is present."""
    for path in FONT_FILES:
        if not Path(path).exists():
            continue
        faces = {}
        for index in range(24):
            try:
                probe = ImageFont.truetype(path, 20, index=index)
            except Exception:
                break
            faces.setdefault(probe.getname()[1], index)
        if "Regular" not in faces:
            continue

        def at(size, weight="regular", _path=path, _faces=faces):
            for name in WEIGHTS[weight]:
                if name in _faces:
                    return ImageFont.truetype(_path, size, index=_faces[name])
            return ImageFont.truetype(_path, size, index=_faces["Regular"])

        return at

    print("! no usable system font found", file=sys.stderr)
    return lambda size, weight="regular": ImageFont.load_default()


def touch_icon():
    tmp = ROOT / "src" / ".touch.svg"
    tmp.write_text(TOUCH_SVG)
    out = IMG / "apple-touch-icon.png"
    subprocess.run(["rsvg-convert", "-w", "180", "-h", "180", str(tmp), "-o", str(out)],
                   check=True)
    tmp.unlink()
    print(f"  apple-touch-icon.png  180x180")


def rounded(img, radius):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.size[0] - 1, img.size[1] - 1],
                                           radius=radius, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


def og_card(apps, totals):
    W, H = 1200, 630
    pad = 72
    card = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(card)
    font = load_fonts()

    # brand mark: rasterise the real SVG rather than redrawing it by hand, so the
    # card can never drift from assets/img/mark.svg
    mark_png = ROOT / "src" / ".mark44.png"
    subprocess.run(["rsvg-convert", "-w", "44", "-h", "44", str(IMG / "mark.svg"),
                    "-o", str(mark_png)], check=True)
    mark = Image.open(mark_png).convert("RGBA")
    card.paste(mark, (pad, 58), mark)
    mark_png.unlink()

    draw.text((pad + 60, 68), "Bon App & T", font=font(23, "medium"), fill=INK)

    headline = font(66, "bold")
    draw.text((pad, 178), "Five apps.", font=headline, fill=INK)
    draw.text((pad, 256), "Forty thousand ratings.", font=headline, fill=INK_2)

    stats = (f"{totals['count']} apps  ·  {totals['ratings']:,} ratings  ·  "
             f"{totals['avg']:.2f} average")
    draw.text((pad, 372), stats, font=font(27, "regular"), fill=INK_2)

    # a row of real icons along the bottom
    size, gap, x, y = 104, 22, pad, 444
    for app in apps[:5]:
        path = IMG / "icons" / f"{app['slug']}.webp"
        if not path.exists():
            continue
        icon = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
        icon = rounded(icon, 21)
        card.paste(icon, (x, y), icon)
        x += size + gap
        if x + size > W - pad:
            break

    out = IMG / "og.png"
    card.save(out, "PNG", optimize=True)
    print(f"  og.png                {W}x{H}  {out.stat().st_size // 1024} KB")


def main():
    apps = json.loads((ROOT / "src" / "apps.json").read_text())
    ratings = sum(a["ratingCount"] for a in apps)
    totals = {
        "count": len(apps),
        "ratings": ratings,
        "avg": sum((a["rating"] or 0) * a["ratingCount"] for a in apps) / ratings,
    }
    touch_icon()
    og_card(apps, totals)


if __name__ == "__main__":
    main()
