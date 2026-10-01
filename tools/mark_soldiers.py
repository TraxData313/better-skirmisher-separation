"""Draw red X / green tick marks on soldiers in a screenshot.

Usage:
    python tools/mark_soldiers.py IMAGE MARKS.json [-o OUT.jpg] [--quality 92] [--scale 1.0]

MARKS.json is a list of marks in IMAGE pixel coordinates:
    [{"x": 600, "y": 690, "kind": "x",    "size": 60},
     {"x": 825, "y": 480, "kind": "tick", "size": 60}, ...]
  kind  "x" (red cross, wrong formation) or "tick" (green check, right formation)
  size  overall width/height of the mark in pixels (default 60)
  Optional per mark: "color": [r, g, b] to override the default colour.
  Extra keys (e.g. "id", "note") are ignored.

Each mark is drawn with thick round-capped strokes and a thin dark outline so it
reads on sand and on purple shields. Marks are drawn 4x supersampled on a small
patch and downscaled (antialiased), then alpha-composited onto the image.
Default output: "<image name> marked.jpg" next to the marks file.
"""
import argparse
import json
import os

from PIL import Image, ImageDraw

SS = 4  # supersampling factor
COLORS = {"x": (230, 25, 25), "tick": (40, 215, 60)}
OUTLINE = (15, 15, 15, 235)


def _stroke(draw, pts, width, fill):
    draw.line(pts, fill=fill, width=width, joint="curve")
    r = width / 2
    for x, y in (pts[0], pts[-1]):
        draw.ellipse([x - r, y - r, x + r, y + r], fill=fill)


def mark_patch(kind, size, color=None):
    """Return an RGBA patch (size+pad square) with the mark centred on it."""
    color = tuple(color or COLORS[kind]) + (255,)
    w = max(3.0, size * 0.13)           # main stroke width
    o = max(1.5, size * 0.035)          # outline thickness each side
    pad = int(w + o) + 2
    full = int(size + 2 * pad)
    big = Image.new("RGBA", (full * SS, full * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    s = size * SS
    p = pad * SS
    if kind == "x":
        strokes = [[(p, p), (p + s, p + s)], [(p + s, p), (p, p + s)]]
    elif kind == "tick":
        # short left leg down to the vertex, long right leg up
        strokes = [[(p, p + s * 0.55), (p + s * 0.36, p + s * 0.92), (p + s, p + s * 0.05)]]
    else:
        raise ValueError(f"unknown kind {kind!r}")
    for st in strokes:
        _stroke(d, st, int(round((w + 2 * o) * SS)), OUTLINE)
    for st in strokes:
        _stroke(d, st, int(round(w * SS)), color)
    return big.resize((full, full), Image.LANCZOS)


def draw_marks(img, marks, scale=1.0):
    img = img.convert("RGB")
    for m in marks:
        size = float(m.get("size", 60)) * scale
        patch = mark_patch(m["kind"], size, m.get("color"))
        x = int(round(m["x"] - patch.width / 2))
        y = int(round(m["y"] - patch.height / 2))
        img.paste(patch, (x, y), patch)  # alpha as mask; works off-edge too
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("marks")
    ap.add_argument("-o", "--out")
    ap.add_argument("--quality", type=int, default=92)
    ap.add_argument("--scale", type=float, default=1.0, help="multiply every mark size")
    a = ap.parse_args()

    with open(a.marks, encoding="utf-8") as f:
        marks = json.load(f)
    out = a.out or os.path.join(
        os.path.dirname(os.path.abspath(a.marks)),
        os.path.splitext(os.path.basename(a.image))[0] + " marked.jpg")
    img = draw_marks(Image.open(a.image), marks, a.scale)
    if out.lower().endswith((".jpg", ".jpeg")):
        img.save(out, quality=a.quality, subsampling=0)
    else:
        img.save(out)
    n_x = sum(m["kind"] == "x" for m in marks)
    print(f"{out}: {len(marks)} marks ({n_x} x, {len(marks) - n_x} tick)")


if __name__ == "__main__":
    main()
