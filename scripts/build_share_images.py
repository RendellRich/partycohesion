"""Draw a link-preview image (1200x630) for each state and territory: docs/social/states/<XX>.png.

Used as og:image by the share pages (scripts/build_share_pages.py), so a post about Texas previews with Texas.
The outline is drawn in the hero's paper color, not a party color, and the image carries no counts, so it stays true
as seats change and needs redrawing only if the design changes.

Needs Playwright with Chromium (pip install playwright && playwright install chromium) and network access for the
web fonts. Run:  python scripts/build_share_images.py
"""

import json
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ui import STATES  # noqa: E402

OUT = ROOT / "docs" / "social" / "states"
NAVY, PAPER, BLUE, RED = "#1C2A4A", "#F6F1E7", "#2E6DB4", "#B9443A"
FONTS = ("https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;600&"
         "family=Source+Serif+4:opsz,wght@8..60,700&display=block")


def card(code: str, shape: dict | None) -> str:
    name = escape(STATES.get(code, code))
    outline = ""
    if shape:
        w, h = shape["w"], shape["h"]
        outline = (f'<svg viewBox="-2 -2 {w + 4} {h + 4}" class="outline"><path d="{shape["d"]}" fill="{PAPER}" '
                   'fill-opacity="0.14" stroke="#F6F1E7" stroke-width="1.6" stroke-linejoin="round" '
                   'vector-effect="non-scaling-stroke"/></svg>')
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{FONTS}">
<style>
html,body{{margin:0;width:1200px;height:630px;background:{NAVY};color:{PAPER};overflow:hidden}}
.aisle{{position:absolute;top:0;left:0;right:0;height:14px;display:flex;gap:16px}}
.aisle i{{flex:1}} .aisle i:first-child{{background:{BLUE}}} .aisle i:last-child{{background:{RED}}}
.wrap{{position:absolute;inset:14px 0 0 0;display:flex;align-items:center;gap:64px;padding:0 88px}}
.outline{{width:360px;height:360px;flex:none}}
h1{{font:700 92px/1.02 'Source Serif 4',serif;margin:0 0 22px 0}}
p{{font:400 34px/1.35 'Public Sans',sans-serif;margin:0;color:#D9D4CA}}
.mark{{position:absolute;left:88px;bottom:44px;font:600 26px 'Public Sans',sans-serif;color:{PAPER}}}
.mark span{{font-weight:400;color:#B9B4AA}}
</style></head><body><div class="aisle"><i></i><i></i></div>
<div class="wrap">{outline}<div><h1>{name}</h1><p>Your members of Congress and how they vote</p></div></div>
<div class="mark">PartyCohesion <span>· from the official roll-call record</span></div>
</body></html>"""


def main() -> None:
    from playwright.sync_api import sync_playwright
    import pandas as pd

    shapes = json.loads((ROOT / "data" / "state_shapes.json").read_text())
    codes = sorted(pd.read_csv(ROOT / "data" / "current_seats.csv")["state_abbrev"].unique())
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 630})
        for code in codes:
            page.set_content(card(code, shapes.get(code)), wait_until="networkidle")
            page.evaluate("document.fonts.ready")
            page.screenshot(path=str(OUT / f"{code}.png"))
        browser.close()
    print(f"Wrote {len(codes)} images to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
