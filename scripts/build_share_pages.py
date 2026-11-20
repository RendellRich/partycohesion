"""Write small share pages to docs/s/ (served by GitHub Pages at rendellrich.github.io/partycohesion/s/).

Streamlit Cloud serves its own page head, so a link to partycohesion.streamlit.app shows up on Facebook, LinkedIn and
X as a generic "Streamlit" preview. Each share page carries the real title, description and image for one view
(a member, a state or a site page) and sends visitors straight on to the app; the share bar in the app links here.
Link previews read the page head without running scripts, so they see these tags; people's browsers follow the
redirect. Any query string on a share link is passed through to the app.

Run after a data refresh:  python scripts/build_share_pages.py
"""

import re
import shutil
import sys
from html import escape
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ui import STATES, display_name  # noqa: E402

OUT = ROOT / "docs" / "s"
BASE = "https://rendellrich.github.io/partycohesion"
SHARE = f"{BASE}/s"
# The app itself, without Streamlit Cloud's frame (its Fork button and hosting badge). The keep-awake workflow visits
# every 6 hours, well inside the 12 hours after which Community Cloud puts an app to sleep.
APP = "https://partycohesion.streamlit.app/~/+"
DEFAULT_IMAGE = f"{BASE}/social/partycohesion-wide.png"
SOURCE = "From the official congressional roll-call record (Voteview). No scorecards, no opinions."


def image_size(url: str) -> tuple[int, int]:
    """Pixel size of one of our own images under docs/, so og:image:width and height are exact."""
    from PIL import Image
    with Image.open(ROOT / "docs" / url.removeprefix(BASE + "/")) as im:
        return im.size


def page(title: str, description: str, share_url: str, target: str, image: str = DEFAULT_IMAGE) -> str:
    t, d, img = escape(title), escape(description), escape(image)
    w, h = image_size(image)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t}</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{escape(share_url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="PartyCohesion">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{escape(share_url)}">
<meta property="og:image" content="{img}">
<meta property="og:image:width" content="{w}">
<meta property="og:image:height" content="{h}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{t}">
<meta name="twitter:description" content="{d}">
<meta name="twitter:image" content="{img}">
<script>var q = location.search;
location.replace({target!r} + (q && {target!r}.indexOf("?") > -1 ? "&" + q.slice(1) : q));</script>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:36rem;margin:3rem auto;padding:0 1rem;color:#1c2a4a}}
a{{color:#7a5a10}}</style>
</head>
<body>
<p>Opening PartyCohesion…</p>
<p><a href="{escape(target)}">{t}</a></p>
</body>
</html>
"""


def nav_pages() -> list[tuple[str, str]]:
    """(url path, title) for each page in app.py's navigation, in the order Streamlit names them."""
    text = (ROOT / "app.py").read_text()
    out = []
    for file, title in re.findall(r'st\.Page\("views/([^"]+)\.py", title="([^"]+)"', text):
        out.append((re.sub(r"^\d+_", "", file), title))
    return out


PAGE_TEXT = {
    "": ("Do members of Congress vote the same way no matter who is president?",
         "Every roll-call vote since 2007: how often each member sides with their party, and whether their position "
         "changes when the White House changes hands."),
    "Member_Explorer": ("Look up how any member of Congress votes",
                        "Party unity, Position Flips, missed votes and every roll call for each member since 2007."),
    "States": ("Your members of Congress and how they vote",
               "Pick a state or enter a ZIP code to see your senators and House member and their voting records."),
}


def write(rel: str, html: str) -> None:
    path = OUT / rel / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html)


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    n = 0
    # Site pages
    for url_path, title in nav_pages():
        rel = "" if url_path == "Home" else url_path
        head, desc = PAGE_TEXT.get(rel, (f"{title} · PartyCohesion", SOURCE))
        write(rel, page(head, desc, f"{SHARE}/{rel}/" if rel else f"{SHARE}/", f"{APP}/{rel}"))
        n += 1

    # States: who represents each state, from the current seats
    seats = pd.read_csv(ROOT / "data" / "current_seats.csv")
    for code, grp in seats.groupby("state_abbrev"):
        name = STATES.get(code, code)
        sen, house = (grp["chamber"] == "Senate").sum(), (grp["chamber"] == "House").sum()
        parts = ([f"{sen} senator{'s' if sen != 1 else ''}"] if sen else []) + \
                ([f"{house} House member{'s' if house != 1 else ''}"] if house else [])
        write(f"state/{code}", page(
            f"{name}'s members of Congress and how they vote",
            f"{' and '.join(parts)}: party unity, Position Flips and missed votes. {SOURCE}",
            f"{SHARE}/state/{code}/", f"{APP}/States?state={code}",
            f"{BASE}/social/states/{code}.png" if (ROOT / "docs" / "social" / "states" / f"{code}.png").exists()
            else DEFAULT_IMAGE))
        n += 1

    # Members: everyone in the data since 2007, under their latest party, state and chamber
    members = pd.read_csv(ROOT / "data" / "members_processed.csv")
    members = members[members["bioguide_id"].notna()]
    # The year their record here starts, as the member page says it: the first year of their first Congress in the
    # data, or the year they joined when that came in the Congress's second year
    since = 2 * members.groupby("bioguide_id")["congress"].min() + 1787
    details = ROOT / "data" / "member_details.csv"
    if details.exists():
        joined = pd.read_csv(details).set_index("bioguide_id")["first_year"]
        for b, y in since.items():
            j = joined.get(b)
            if str(j).isdigit() and y < int(j) <= y + 1:
                since[b] = int(j)
    members = members.sort_values("congress").groupby("bioguide_id").tail(1)
    cards = ROOT / "docs" / "social" / "members"
    for m in members.itertuples():
        who = f"{display_name(m.name)} ({str(m.party)[0]}-{m.state_abbrev})"
        image = (f"{BASE}/social/members/{m.bioguide_id}-wide.png"
                 if (cards / f"{m.bioguide_id}-wide.png").exists() else DEFAULT_IMAGE)
        write(f"member/{m.bioguide_id}", page(
            f"{who}: voting record",
            f"How often {display_name(m.name)} votes with their party, whether their votes change with the White "
            f"House, and every roll call since {int(since[m.bioguide_id])}. {SOURCE}",
            f"{SHARE}/member/{m.bioguide_id}/", f"{APP}/Member_Explorer?member={m.bioguide_id}", image))
        n += 1
    print(f"Wrote {n:,} share pages to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
