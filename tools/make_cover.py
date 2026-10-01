"""Builds the BEFORE / AFTER cover image from two screenshots.

    python tools\\make_cover.py [before] [after] [options]

Defaults: docs\\before.* and docs\\after.* (any image extension), output docs\\cover.png for the README
plus docs\\cover.jpg for the Steam Workshop preview (always kept under 1 MB).

Landscape screenshots go side by side, portrait ones are stacked; both are scaled to the same height
(or width). By default each panel is centre-cropped so the whole cover comes out 16:9, which is what
the Workshop preview shows best; --focus moves the crop, --no-crop keeps the full screenshots.

Needs Pillow (pip install pillow).
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")
STEAM_LIMIT = 1024 * 1024  # Steam Workshop preview image limit, 1 MB
DIVIDER = (235, 225, 200)  # warm off-white
TITLE = "Better Skirmisher Separation"


def find_default(stem: str) -> Path:
    for ext in IMAGE_EXTS:
        p = DOCS / f"{stem}{ext}"
        if p.exists():
            return p
    sys.exit(f"No docs\\{stem}.* found - pass the screenshot path explicitly.")


def load_font(size: int) -> ImageFont.ImageFont:
    for name in ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def crop_to_aspect(img: Image.Image, aspect: float, focus: float) -> Image.Image:
    """Crop img to width/height == aspect, keeping the point at `focus` (0..1 along the cut axis)."""
    w, h = img.size
    if w / h > aspect:  # too wide: trim the sides
        nw = round(h * aspect)
        x = round((w - nw) * focus)
        return img.crop((x, 0, x + nw, h))
    nh = round(w / aspect)  # too tall: trim top/bottom
    y = round((h - nh) * focus)
    return img.crop((0, y, w, y + nh))


def label(canvas: Image.Image, box: tuple[int, int, int, int], text: str, top: bool) -> None:
    """Big clean label on a semi-transparent dark band across the panel."""
    x0, y0, x1, y1 = box
    pw, ph = x1 - x0, y1 - y0
    font = load_font(max(24, round(min(pw, ph * 1.6) * 0.085)))
    band_h = round(font.size * 1.7)
    by = y0 if top else y1 - band_h
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rectangle((x0, by, x1, by + band_h), fill=(0, 0, 0, 140))
    tw = d.textlength(text, font=font)
    d.text((x0 + (pw - tw) / 2, by + band_h / 2), text, font=font, anchor="lm",
           fill=(255, 255, 255, 255), stroke_width=max(1, font.size // 30), stroke_fill=(0, 0, 0, 200))
    canvas.alpha_composite(overlay)


def title_strip(canvas: Image.Image, text: str) -> None:
    w, h = canvas.size
    font = load_font(max(16, round(h * 0.035)))
    band_h = round(font.size * 1.8)
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    tw = d.textlength(text, font=font)
    pad = font.size
    bw = tw + 2 * pad
    bx = (w - bw) / 2
    d.rounded_rectangle((bx, h - band_h - pad // 2, bx + bw, h - pad // 2), radius=band_h // 3, fill=(0, 0, 0, 150))
    d.text((w / 2, h - pad // 2 - band_h / 2), text, font=font, anchor="mm", fill=(235, 225, 200, 255))
    canvas.alpha_composite(overlay)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build docs\\cover.png (+ cover.jpg) from BEFORE / AFTER screenshots.")
    ap.add_argument("before", nargs="?", help="before screenshot (default docs\\before.*)")
    ap.add_argument("after", nargs="?", help="after screenshot (default docs\\after.*)")
    ap.add_argument("-o", "--out", default=str(DOCS / "cover.png"), help="output PNG (a .jpg is written beside it)")
    ap.add_argument("--width", type=int, default=1920, help="output width in pixels (default 1920)")
    ap.add_argument("--layout", choices=("auto", "side", "stack"), default="auto",
                    help="auto = side by side for landscape shots, stacked for portrait")
    ap.add_argument("--no-crop", action="store_true", help="keep the full screenshots (cover will not be 16:9)")
    ap.add_argument("--focus", type=float, default=0.5, help="crop position 0..1 (0 = left/top, default centre)")
    ap.add_argument("--labels", nargs=2, default=("BEFORE", "AFTER"), metavar=("L1", "L2"))
    ap.add_argument("--no-title", action="store_true", help=f'leave out the small "{TITLE}" title')
    a = ap.parse_args()

    before = Image.open(a.before or find_default("before")).convert("RGB")
    after = Image.open(a.after or find_default("after")).convert("RGB")

    portrait = (before.width / before.height + after.width / after.height) / 2 < 1
    side = a.layout == "side" or (a.layout == "auto" and not portrait)
    div = max(2, a.width // 400)  # thin divider

    if side:
        if not a.no_crop:  # two panels of 8:9 make a 16:9 cover
            before, after = (crop_to_aspect(i, 8 / 9, a.focus) for i in (before, after))
        ph = before.height  # same height
        before = before.resize((round(before.width * ph / before.height), ph), Image.LANCZOS)
        after = after.resize((round(after.width * ph / after.height), ph), Image.LANCZOS)
        full_w = before.width + div + after.width
        scale = a.width / full_w
        h = round(ph * scale)
        bw = round(before.width * scale)
        aw = a.width - bw - div
        canvas = Image.new("RGBA", (a.width, h), DIVIDER + (255,))
        canvas.paste(before.resize((bw, h), Image.LANCZOS), (0, 0))
        canvas.paste(after.resize((aw, h), Image.LANCZOS), (bw + div, 0))
        boxes = [(0, 0, bw, h), (bw + div, 0, a.width, h)]
    else:
        if not a.no_crop:  # two stacked 32:9 bands make a 16:9 cover
            before, after = (crop_to_aspect(i, 32 / 9, a.focus) for i in (before, after))
        w = a.width
        bh = round(before.height * w / before.width)
        ah = round(after.height * w / after.width)
        canvas = Image.new("RGBA", (w, bh + div + ah), DIVIDER + (255,))
        canvas.paste(before.resize((w, bh), Image.LANCZOS), (0, 0))
        canvas.paste(after.resize((w, ah), Image.LANCZOS), (0, bh + div))
        boxes = [(0, 0, w, bh), (0, bh + div, w, bh + div + ah)]

    for box, text in zip(boxes, a.labels):
        label(canvas, box, text, top=True)
    if not a.no_title:
        title_strip(canvas, TITLE)

    rgb = canvas.convert("RGB")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rgb.save(out, optimize=True)
    print(f"{out}  {rgb.width}x{rgb.height}  {out.stat().st_size // 1024} KB")

    # Steam preview: JPG, stepping quality (then size) down until it fits under 1 MB.
    jpg = out.with_suffix(".jpg")
    img = rgb
    while True:
        for q in (92, 88, 84, 80, 75, 70):
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=q, optimize=True, progressive=True)
            if buf.tell() < STEAM_LIMIT:
                jpg.write_bytes(buf.getvalue())
                print(f"{jpg}  {img.width}x{img.height}  {buf.tell() // 1024} KB (q{q}, Steam preview)")
                return
        img = img.resize((round(img.width * 0.85), round(img.height * 0.85)), Image.LANCZOS)


if __name__ == "__main__":
    main()
