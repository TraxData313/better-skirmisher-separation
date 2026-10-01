r"""Builds the square Steam Workshop / mod thumbnail (1024x1024, under 1 MB).

    python tools\make_thumbnail.py                 # v1 -> docs\thumbnail.jpg    (BEFORE | AFTER, big title)
    python tools\make_thumbnail.py --variant v2    # v2 -> docs\thumbnail_v2.jpg (the formation card with the
                                                   #   Throwing Weapons filter ticked, then BEFORE | AFTER)
    python tools\make_thumbnail.py --variant v3    # v3 -> docs\thumbnail_v3.jpg (v1 + the ringed Throwing filter
                                                   #   icon top centre, on the split line)

Style matches TrainingBattlesMod's preview_thumbnail (gold frame, Palatino small caps over a dark fade).
1. Cuts the Throwing Weapons block out of the unmarked screenshots "A1 Before" / "A2 After" and redraws
   their marks (screenshots\marks\*.marks.json) 2-2.3x bigger, so the red X's and green ticks still
   read on a 256 px Workshop tile. Panels go to screenshots\thumbnail build\ (gitignored, like all screenshots).
   v2 also cuts the Order of Battle card of formation 2 (Throwing Weapons filter ticked) out of "B1 Before"
   (identical in B2) plus a close-up of its filter icon, which the HTML rings and magnifies.
   v3 is v1's layout plus that filter icon alone (sand, border and neighbour icons removed), drawn on a dark disc. The "26 / <total>"
   count above the slider is painted out with the card's own background (the army total is not wanted in public images).
2. Renders tools\preview_thumbnail.html (v2/v3: preview_thumbnail_v2.html / _v3.html) with headless Edge (or Chrome) to a 1024x1024 PNG.
3. Saves docs\thumbnail.jpg, stepping JPEG quality down until it fits under 1 MB.

docs\cover.jpg (the stacked BEFORE/AFTER comparison) is separate - see make_cover.py.
Needs Pillow and Edge or Chrome.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
from mark_soldiers import draw_marks  # noqa: E402

SHOTS = REPO / "screenshots"
WORK = SHOTS / "thumbnail build"
STEAM_LIMIT = 1024 * 1024

# per variant: template, output, panel size (= .panel in the HTML) and
# (screenshot, marks, crop box in source pixels) - the Throwing Weapons block, same aspect as the panel
VARIANTS = {
    "v1": {
        "html": "preview_thumbnail.html", "out": "thumbnail.jpg", "panel": (512, 700), "mark_scale": 2.0,
        "panels": {
            "before": ("A1 Before.jpg", "A1 Before.marks.json", (1985, 300, 2935, 1599)),
            "after": ("A2 After.jpg", "A2 After.marks.json", (2000, 230, 2950, 1529)),
        },
    },
    "v2": {
        "html": "preview_thumbnail_v2.html", "out": "thumbnail_v2.jpg", "panel": (512, 390), "mark_scale": 2.3,
        "panels": {
            "before": ("A1 Before.jpg", "A1 Before.marks.json", (1960, 395, 3110, 1271)),
            "after": ("A2 After.jpg", "A2 After.marks.json", (1975, 365, 3125, 1241)),
        },
    },
}
VARIANTS["v3"] = {**VARIANTS["v1"], "html": "preview_thumbnail_v3.html", "out": "thumbnail_v3.jpg"}

# v2 setting card: formation 2 in the Order of Battle (3440x1440 shot), its Throwing Weapons icon,
# and where the HTML draws them (keep in sync with .card / .zoom in preview_thumbnail_v2.html)
CARD_SHOT = "B1 Before.jpg"
CARD_BOX = (14, 396, 426, 700)
ICON_BOX = (376, 524, 418, 566)        # square around the thrower icon + its green tick
ICON_CENTER = (397, 545)
CARD_BODY = (20, 426, 420, 694)        # the card body inside its gold border (tabs sit above it)
MAGENTA = (255, 0, 255)
# the "26 / <total>" label above the slider and its drop shadow, cloned over from the empty strip to its right
# (rows stop above the slider handle, which pokes up at x 167..181, and above the bar, which starts at y 497)
CARD_ERASE = [(164, 464, 182, 490), (182, 464, 250, 497)]
ERASE_SRC_X = 254
CARD_POS, CARD_SIZE = (58, 52), (548, 404)
RING = 92
ZOOM_CENTER, ZOOM_R = (821, 211), 145
# v3 badge: the icon alone (javelin tip to tick, clear of the card's gold border at x 415+ and the icons above/below),
# keyed onto the card's dark brown; drawn ICON_SIZE px wide (BADGE_SRC source px) inside the 150 px disc of _v3.html
BADGE_BOX = (378, 527, 413, 564)
BADGE_BG = (45, 24, 5)
BADGE_SRC, ICON_SIZE = 40, 140

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]


def make_panel(name: str, shot: str, marks: str, box: tuple[int, int, int, int], size: tuple[int, int],
               mark_scale: float) -> Path:
    img = Image.open(SHOTS / "originals" / shot).convert("RGB")
    with open(SHOTS / "marks" / marks, encoding="utf-8") as f:
        img = draw_marks(img, json.load(f), mark_scale)
    x0, y0, x1, y1 = box
    # crop may run past the bottom edge: pad with the image's own last rows instead of black
    if y1 > img.height:
        y0, y1 = y0 - (y1 - img.height), img.height
    panel = img.crop((x0, y0, x1, y1)).resize(size, Image.LANCZOS)
    out = WORK / f"thumb_{name}.jpg"
    panel.save(out, quality=94, subsampling=0)
    return out


def cut_card(img: Image.Image) -> Image.Image:
    """Makes the sand around the (semi-transparent) card transparent: a rounded rectangle for the card body,
    and below its top edge a flood fill from the edges for the tab row (the sword tab and the "2" badge)."""
    w, h = img.size
    body = CARD_BODY[0] - CARD_BOX[0], CARD_BODY[1] - CARD_BOX[1], CARD_BODY[2] - CARD_BOX[0], CARD_BODY[3] - CARD_BOX[1]
    alpha = Image.new("L", (w, h), 0)
    ImageDraw.Draw(alpha).rounded_rectangle(body, radius=10, fill=255)
    marked = img.copy()
    for x in range(0, w, 4):                       # seed every sand pixel along the top edge
        if marked.getpixel((x, 0)) != MAGENTA:
            ImageDraw.floodfill(marked, (x, 0), MAGENTA, thresh=60)
    diff = ImageChops.difference(marked, Image.new("RGB", (w, h), MAGENTA)).convert("L")
    tabs = diff.point(lambda v: 255 if v else 0)
    alpha.paste(tabs.crop((0, 0, w, body[1] + 6)), (0, 0))
    out = img.convert("RGBA")
    out.putalpha(alpha)
    return out


def erase_count(shot: Image.Image) -> Image.Image:
    """Paints out the slider's "26 / <total>" label by cloning the plain card background from the same rows."""
    out = shot.copy()
    for x0, y0, x1, y1 in CARD_ERASE:
        out.paste(shot.crop((ERASE_SRC_X, y0, ERASE_SRC_X + x1 - x0, y1)), (x0, y0))
    return out


def card_fill(html: str) -> str:
    """v2: writes the card + icon crops and fills the ring / leader-line positions into the template."""
    shot = erase_count(Image.open(SHOTS / "originals" / CARD_SHOT).convert("RGB"))
    card = WORK / "thumb_card.png"
    cut_card(shot.crop(CARD_BOX)).resize(CARD_SIZE, Image.LANCZOS).save(card)
    icon = WORK / "thumb_icon.png"
    shot.crop(ICON_BOX).resize((288, 288), Image.LANCZOS).filter(
        ImageFilter.UnsharpMask(radius=3, percent=120, threshold=2)).save(icon)

    k = CARD_SIZE[0] / (CARD_BOX[2] - CARD_BOX[0])
    cx = CARD_POS[0] + (ICON_CENTER[0] - CARD_BOX[0]) * k
    cy = CARD_POS[1] + (ICON_CENTER[1] - CARD_BOX[1]) * k
    # leader line: ring edge -> magnifier edge, along the line between their centres
    dx, dy = ZOOM_CENTER[0] - cx, ZOOM_CENTER[1] - cy
    dist = math.hypot(dx, dy)
    ux, uy = dx / dist, dy / dist
    x0, y0 = cx + ux * RING / 2, cy + uy * RING / 2
    length = dist - RING / 2 - ZOOM_R
    for key, val in {"CARD_IMG": card.as_uri(), "ICON_IMG": icon.as_uri(),
                     "RING_L": cx - RING / 2, "RING_T": cy - RING / 2,
                     "LEAD_X": x0, "LEAD_Y": y0 - 2.5, "LEAD_W": length,
                     "LEAD_A": math.degrees(math.atan2(dy, dx))}.items():
        html = html.replace(key, val if isinstance(val, str) else f"{val:.1f}")
    return html


def badge_fill(html: str) -> str:
    """v3: the Throwing filter icon on a clean dark square (pixels close to the card colour become exactly it)."""
    shot = Image.open(SHOTS / "originals" / CARD_SHOT).convert("RGB")
    bg = Image.new("RGB", (BADGE_SRC, BADGE_SRC), BADGE_BG)
    crop = shot.crop(BADGE_BOX)
    dist = ImageChops.difference(crop, Image.new("RGB", crop.size, BADGE_BG)).convert("L")
    mask = dist.point(lambda v: 0 if v < 22 else min(255, (v - 22) * 6))
    half = BADGE_SRC // 2
    bg.paste(crop, (BADGE_BOX[0] - (ICON_CENTER[0] - half), BADGE_BOX[1] - (ICON_CENTER[1] - half)), mask)
    icon = WORK / "thumb_badge.png"
    bg.resize((320, 320), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=3, percent=120, threshold=2)).save(icon)
    return html.replace("ICON_IMG", icon.as_uri()).replace("ICON_SIZE", str(ICON_SIZE))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", choices=sorted(VARIANTS), default="v1")
    v = VARIANTS[ap.parse_args().variant]
    out_path = REPO / "docs" / v["out"]
    suffix = "" if v["out"] == "thumbnail.jpg" else "_" + Path(v["out"]).stem.split("_")[-1]

    WORK.mkdir(parents=True, exist_ok=True)
    paths = {n: make_panel(n + suffix, *spec, v["panel"], v["mark_scale"]) for n, spec in v["panels"].items()}

    html = (REPO / "tools" / v["html"]).read_text(encoding="utf-8")
    html = html.replace("PANEL_BEFORE", paths["before"].as_uri()).replace("PANEL_AFTER", paths["after"].as_uri())
    if "CARD_IMG" in html:
        html = card_fill(html)
    elif "ICON_IMG" in html:
        html = badge_fill(html)
    page = WORK / f"thumbnail{suffix}.html"
    page.write_text(html, encoding="utf-8")

    browser = next((b for b in BROWSERS if Path(b).exists()), None) or shutil.which("msedge") or shutil.which("chrome")
    if not browser:
        sys.exit("Edge or Chrome not found.")
    png = WORK / f"thumbnail{suffix}.png"
    png.unlink(missing_ok=True)
    subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                    "--allow-file-access-from-files", "--window-size=1024,1024", f"--screenshot={png}",
                    page.as_uri()], check=True, capture_output=True, timeout=120)
    img = Image.open(png).convert("RGB").crop((0, 0, 1024, 1024))

    for q in (92, 90, 88, 85, 82, 78, 74, 70):
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=q, optimize=True, progressive=True)
        if buf.tell() < STEAM_LIMIT:
            break
    out_path.write_bytes(buf.getvalue())
    print(f"{out_path}: {img.width}x{img.height}, {buf.tell() // 1024} KB, q{q}")


if __name__ == "__main__":
    main()
