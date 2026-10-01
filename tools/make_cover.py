r"""Builds the BEFORE / AFTER cover image from two screenshots.

    python tools\make_cover.py [before] [after] [options]

Defaults: docs\before.* and docs\after.* (any image extension), output docs\cover.jpg - used both by
the README and as the Steam Workshop preview (always kept under 1 MB). --png also writes a lossless
docs\cover.png beside it (not committed: a photo as PNG is ~2.7 MB).

Landscape screenshots go side by side, portrait ones are stacked; both are scaled to the same height
(or width). By default each panel is centre-cropped so the whole cover comes out 16:9, which is what
the Workshop preview shows best; --focus moves the crop, --no-crop keeps the full screenshots.
--crop X0 Y0 X1 Y1 first cuts the same region (source pixels) out of both screenshots, so the cover
shows the part that changed instead of two shrunken full frames; --captions adds a line under each.
--layout stack --no-crop puts BEFORE on top of AFTER at the --crop aspect; --label-pos tl/tr puts each
label (and its caption) in a small corner tag instead of a band across the panel; --tag-scale resizes it.

The published docs\cover.jpg was built with (screenshots\ is gitignored, the raw shots stay local):

    python tools\make_cover.py "screenshots\A1 Before marked.jpg" "screenshots\A2 After marked.jpg" --crop 100 130 3380 1300 --layout stack --no-crop --label-pos tr --tag-scale 0.6 --width 1920 --no-title

(3440x1440 shots of the same desert battle, marked by tools\mark_soldiers.py: red X = soldier in the
wrong formation, green tick = right one. The crop keeps both blocks - infantry left, Throwing Weapons
right; BEFORE has 11 + 12 = 23 X, AFTER none. Pair B of the screenshots is not used.)

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


def corner_tag(canvas: Image.Image, box: tuple[int, int, int, int], text: str, sub: str | None, right: bool,
               scale: float = 1.0) -> None:
    """Label (+ optional caption line under it) in a dark rounded tag in a top corner of the panel, so
    the middle of the shot - the troops - stays uncovered."""
    x0, y0, x1, y1 = box
    pw = x1 - x0
    font = load_font(max(24, round(pw * 0.062 * scale)))
    sfont = load_font(max(14, round(font.size * 0.42)))
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    pad = round(font.size * 0.4)
    tw = d.textlength(text, font=font)
    sw = d.textlength(sub, font=sfont) if sub else 0
    bw = max(tw, sw) + 2 * pad
    bh = round(font.size * 1.15) + (round(sfont.size * 1.4) if sub else 0) + pad
    m = round(font.size * 0.3)
    bx = x1 - m - bw if right else x0 + m
    by = y0 + m
    d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=pad, fill=(0, 0, 0, 165))
    d.text((bx + pad, by + pad * 0.6), text, font=font, anchor="la", fill=(255, 255, 255, 255))
    if sub:
        d.text((bx + pad, by + pad * 0.6 + font.size * 1.15), sub, font=sfont, anchor="la", fill=DIVIDER + (255,))
    canvas.alpha_composite(overlay)


def caption(canvas: Image.Image, box: tuple[int, int, int, int], text: str) -> None:
    """Smaller line at the bottom of the panel on a dark fade (also hides HUD bits in the corner)."""
    x0, y0, x1, y1 = box
    pw, ph = x1 - x0, y1 - y0
    font = load_font(max(16, round(pw * 0.052)))
    fade_h = round(font.size * 3.2)
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for i in range(fade_h):  # transparent -> dark, bottom-heavy
        a = round(215 * min(1.0, (i / fade_h) * 1.6) ** 1.4)
        d.line((x0, y1 - fade_h + i, x1 - 1, y1 - fade_h + i), fill=(0, 0, 0, a))
    tw = d.textlength(text, font=font)
    d.text((x0 + (pw - tw) / 2, y1 - font.size * 1.05), text, font=font, anchor="lm",
           fill=(235, 225, 200, 255), stroke_width=max(1, font.size // 28), stroke_fill=(0, 0, 0, 220))
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
    ap = argparse.ArgumentParser(description="Build docs\\cover.jpg (+ optional .png) from BEFORE / AFTER screenshots.")
    ap.add_argument("before", nargs="?", help="before screenshot (default docs\\before.*)")
    ap.add_argument("after", nargs="?", help="after screenshot (default docs\\after.*)")
    ap.add_argument("-o", "--out", default=str(DOCS / "cover.jpg"), help="output JPG (default docs\\cover.jpg)")
    ap.add_argument("--png", action="store_true", help="also write a lossless .png beside the .jpg")
    ap.add_argument("--width", type=int, default=1920, help="output width in pixels (default 1920)")
    ap.add_argument("--layout", choices=("auto", "side", "stack"), default="auto",
                    help="auto = side by side for landscape shots, stacked for portrait")
    ap.add_argument("--no-crop", action="store_true", help="keep the full screenshots (cover will not be 16:9)")
    ap.add_argument("--focus", type=float, default=0.5, help="crop position 0..1 (0 = left/top, default centre)")
    ap.add_argument("--crop", type=int, nargs=4, metavar=("X0", "Y0", "X1", "Y1"),
                    help="cut this region (source pixels) out of both screenshots first")
    ap.add_argument("--captions", nargs=2, metavar=("C1", "C2"), help="small line at the bottom of each panel")
    ap.add_argument("--labels", nargs=2, default=("BEFORE", "AFTER"), metavar=("L1", "L2"))
    ap.add_argument("--label-pos", choices=("band", "tl", "tr"), default="band",
                    help="band = full-width band on top of each panel (default); tl / tr = compact tag in the "
                         "top-left / top-right corner, with the --captions line inside the tag")
    ap.add_argument("--tag-scale", type=float, default=1.0,
                    help="size of the corner tags relative to the default (e.g. 0.7 on a wide panel)")
    ap.add_argument("--no-title", action="store_true", help=f'leave out the small "{TITLE}" title')
    a = ap.parse_args()

    before = Image.open(a.before or find_default("before")).convert("RGB")
    after = Image.open(a.after or find_default("after")).convert("RGB")

    if a.crop:
        before, after = before.crop(tuple(a.crop)), after.crop(tuple(a.crop))

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

    if a.label_pos != "band":
        subs = a.captions or (None, None)
        for box, text, sub in zip(boxes, a.labels, subs):
            corner_tag(canvas, box, text, sub, right=a.label_pos == "tr", scale=a.tag_scale)
    else:
        for box, text in zip(boxes, a.labels):
            label(canvas, box, text, top=True)
    if a.captions and a.label_pos == "band":
        for box, text in zip(boxes, a.captions):
            caption(canvas, box, text)
    if not a.no_title:
        title_strip(canvas, TITLE)

    rgb = canvas.convert("RGB")
    jpg = Path(a.out).with_suffix(".jpg")
    jpg.parent.mkdir(parents=True, exist_ok=True)
    if a.png:
        png = jpg.with_suffix(".png")
        rgb.save(png, optimize=True)
        print(f"{png}  {rgb.width}x{rgb.height}  {png.stat().st_size // 1024} KB")

    # Steam preview: JPG, stepping quality (then size) down until it fits under 1 MB.
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
