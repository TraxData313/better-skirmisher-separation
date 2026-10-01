r"""Builds the square Steam Workshop / mod thumbnail, docs\thumbnail.jpg (1024x1024, under 1 MB).

    python tools\make_thumbnail.py

Style matches TrainingBattlesMod's preview_thumbnail (gold frame, Palatino small caps over a dark fade).
1. Cuts the Throwing Weapons block out of the unmarked screenshots "A1 Before" / "A2 After" and redraws
   their marks (screenshots\marks\*.marks.json) MARK_SCALE x bigger, so the red X's and green ticks still
   read on a 256 px Workshop tile. Panels go to screenshots\thumbnail build\ (gitignored, like all screenshots).
2. Renders tools\preview_thumbnail.html with headless Edge (or Chrome) to a 1024x1024 PNG.
3. Saves docs\thumbnail.jpg, stepping JPEG quality down until it fits under 1 MB.

docs\cover.jpg (the stacked BEFORE/AFTER comparison) is separate - see make_cover.py.
Needs Pillow and Edge or Chrome.
"""
from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
from mark_soldiers import draw_marks  # noqa: E402

SHOTS = REPO / "screenshots"
WORK = SHOTS / "thumbnail build"
HTML = REPO / "tools" / "preview_thumbnail.html"
OUT = REPO / "docs" / "thumbnail.jpg"
STEAM_LIMIT = 1024 * 1024
MARK_SCALE = 2.0
PANEL = (512, 700)  # matches .panel in the HTML

# (screenshot, marks, crop box in source pixels) - the Throwing Weapons block, same aspect as PANEL
PANELS = {
    "before": ("A1 Before.jpg", "A1 Before.marks.json", (1985, 300, 2935, 1599)),
    "after": ("A2 After.jpg", "A2 After.marks.json", (2000, 230, 2950, 1529)),
}

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]


def make_panel(name: str, shot: str, marks: str, box: tuple[int, int, int, int]) -> Path:
    img = Image.open(SHOTS / "originals" / shot).convert("RGB")
    with open(SHOTS / "marks" / marks, encoding="utf-8") as f:
        img = draw_marks(img, json.load(f), MARK_SCALE)
    x0, y0, x1, y1 = box
    # crop may run past the bottom edge: pad with the image's own last rows instead of black
    if y1 > img.height:
        y0, y1 = y0 - (y1 - img.height), img.height
    panel = img.crop((x0, y0, x1, y1)).resize(PANEL, Image.LANCZOS)
    out = WORK / f"thumb_{name}.jpg"
    panel.save(out, quality=94, subsampling=0)
    return out


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    paths = {n: make_panel(n, *spec) for n, spec in PANELS.items()}

    html = HTML.read_text(encoding="utf-8")
    html = html.replace("PANEL_BEFORE", paths["before"].as_uri()).replace("PANEL_AFTER", paths["after"].as_uri())
    page = WORK / "thumbnail.html"
    page.write_text(html, encoding="utf-8")

    browser = next((b for b in BROWSERS if Path(b).exists()), None) or shutil.which("msedge") or shutil.which("chrome")
    if not browser:
        sys.exit("Edge or Chrome not found.")
    png = WORK / "thumbnail.png"
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
    OUT.write_bytes(buf.getvalue())
    print(f"{OUT}: {img.width}x{img.height}, {buf.tell() // 1024} KB, q{q}")


if __name__ == "__main__":
    main()
