"""Index of who spoke on the floor about which bill, from the Congressional Record (GovInfo), for "In their own
words" links. One row per member per bill per Record section: data/floor_remarks_index.csv.

Each day's Congressional Record on GovInfo has MODS metadata listing every section (granule) with its title, a
link to the text, every member who spoke (with Bioguide ID) and the bills it references. This keeps sections where
a member spoke and a bill is referenced, which links a member to their own remarks on that bill. It records only
that they spoke and where; it does not code what they said. Stances are coded by hand separately, in
data/floor_statements.csv.

No API key: www.govinfo.gov serves the sitemaps and MODS files directly. Downloads are cached in --cache.

  python scripts/floor_remarks_index.py --years 2025 2026
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import re
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "floor_remarks_index.csv"
NS = {"m": "http://www.loc.gov/mods/v3"}
M = "{http://www.loc.gov/mods/v3}"
SKIP_TITLES = re.compile(r"^(PRAYER|PLEDGE OF ALLEGIANCE|THE JOURNAL|ADJOURNMENT|RECESS|EXECUTIVE COMMUNICATIONS|"
                         r"PUBLIC BILLS AND RESOLUTIONS|ADDITIONAL SPONSORS|DAILY DIGEST|AMENDMENTS SUBMITTED|"
                         r"TEXT OF AMENDMENTS|STATEMENTS ON INTRODUCED BILLS)", re.I)
COLUMNS = ["bioguide_id", "congress", "bill_number", "date", "chamber", "url"]


def fetch(url: str, dest: Path) -> Path | None:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            dest.write_bytes(r.read())
        return dest
    except Exception:
        return None


def days(years: list[int], cache: Path) -> list[str]:
    out = set()
    for y in years:
        sm = fetch(f"https://www.govinfo.gov/sitemap/CREC_{y}_sitemap.xml", cache / f"CREC_{y}_sitemap.xml")
        if sm:
            out |= set(re.findall(r"CREC-\d{4}-\d{2}-\d{2}", sm.read_text(errors="ignore")))
    return sorted(out)


def parse(path: Path) -> list[dict]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return []
    date = re.search(r"CREC-(\d{4}-\d{2}-\d{2})", path.name).group(1)
    rows = []
    for g in root.findall("m:relatedItem[@type='constituent']", NS):
        title = (g.findtext("m:titleInfo/m:title", default="", namespaces=NS) or "").strip()
        if not title or SKIP_TITLES.match(title):
            continue
        url = next((u.text for u in g.findall("m:location/m:url", NS) if u.get("displayLabel") == "HTML rendition"),
                   None)
        speakers = {(c.get("bioGuideId"), c.get("chamber")) for c in g.iter(f"{M}congMember")
                    if c.get("role") == "SPEAKING" and c.get("bioGuideId")}
        bills = {(b.get("congress"), f"{b.get('type', '').upper()}{b.get('number')}") for b in g.iter(f"{M}bill")
                 if b.get("congress") and b.get("number")}
        for bio, chamber in speakers:
            for congress, bill in bills:
                rows.append({"bioguide_id": bio, "congress": int(congress), "bill_number": bill, "date": date,
                             "chamber": {"H": "House", "S": "Senate"}.get(chamber or "", chamber or ""), "url": url})
    return rows


def build(years: list[int], cache: Path, workers: int = 8, recent: int | None = None) -> pd.DataFrame:
    cache.mkdir(parents=True, exist_ok=True)
    ids = days(years, cache)
    if recent:
        ids = ids[-recent:]
    with cf.ThreadPoolExecutor(workers) as ex:
        paths = list(ex.map(lambda i: fetch(f"https://www.govinfo.gov/metadata/pkg/{i}/mods.xml", cache / f"{i}.xml"),
                            ids))
    rows = [r for p in paths if p for r in parse(p)]
    df = pd.DataFrame(rows, columns=COLUMNS)
    # Keep remarks about bills of the same Congress, one row per member, bill and section.
    df = df[df["congress"].isin({(y - 1789) // 2 + 1 for y in years})]
    return df.drop_duplicates(["bioguide_id", "bill_number", "date", "url"]).sort_values(
        ["congress", "bill_number", "date", "bioguide_id"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--years", nargs="+", type=int, default=[2025, 2026])
    ap.add_argument("--cache", type=Path, default=Path("/tmp/crec/mods"))
    ap.add_argument("--recent", type=int, help="only re-read the last N days of the Record (for the twice-weekly refresh)")
    a = ap.parse_args()
    df = build(a.years, a.cache, recent=a.recent)
    old = pd.read_csv(OUT)[COLUMNS] if OUT.exists() else pd.DataFrame(columns=COLUMNS)
    if a.recent:
        keep = old[~old["date"].isin(df["date"].unique())] if len(df) else old
    else:
        keep = old[~old["congress"].isin(df["congress"].unique())]
    out = pd.concat([keep, df]).drop_duplicates(["bioguide_id", "bill_number", "date", "url"])
    out.sort_values(["congress", "bill_number", "date", "bioguide_id"]).to_csv(OUT, index=False)
    print(f"{len(df):,} member-bill remarks for Congress {sorted(df['congress'].unique())} -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
