"""Data for "Find your members": who holds each seat now, and which congressional districts each ZIP code falls in.

  python scripts/member_lookup.py            data/current_seats.csv from data/raw/legislators-current.json
                                             (downloaded by scripts/refresh_data.py; runs on every refresh)
  python scripts/member_lookup.py --zips     data/zip_districts.csv from the Census Bureau's 2020 ZIP Code
                                             Tabulation Area to 119th Congress district relationship file

Sources:
  - unitedstates/congress-legislators (CC0): current members, with state and district.
  - U.S. Census Bureau, tab20_cd11920_zcta520_natl.txt (public domain): how much of each ZCTA's land area lies in
    each 119th Congress district. ZCTAs approximate ZIP codes; a ZIP that crosses a district line lists every
    district with its share of the land, so the page can say "most of this ZIP is in district 3".

District lines are for the 119th Congress (2025 to 2027). Some states drew new lines for the 120th, so the ZIP file
carries VALID_UNTIL and the page falls back to the state's full list after that date until the Census Bureau
publishes the 120th Congress file.
"""

from __future__ import annotations

import argparse
import io
import json
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SEATS = DATA / "current_seats.csv"
ZIPS = DATA / "zip_districts.csv"
CENSUS_URL = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/cd-sld/tab20_cd11920_zcta520_natl.txt"
DISTRICT_CONGRESS = 119
VALID_UNTIL = "2027-01-03"  # the 120th Congress starts; some states use new district lines
MIN_SHARE = 0.01  # leave out slivers under 1% of a ZIP's land

FIPS = {"01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE", "11": "DC",
        "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY",
        "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT",
        "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
        "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
        "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY", "72": "PR"}


def seats(path: Path = DATA / "raw" / "legislators-current.json") -> pd.DataFrame:
    """One row per current member: bioguide_id, name, chamber, state_abbrev, district (0 = at-large or a senator)."""
    rows = []
    for m in json.loads(path.read_text()):
        t = m["terms"][-1]
        rows.append({"bioguide_id": m["id"]["bioguide"],
                     "name": m["name"].get("official_full") or f"{m['name']['first']} {m['name']['last']}",
                     "chamber": "Senate" if t["type"] == "sen" else "House", "state_abbrev": t["state"],
                     "district": int(t.get("district") or 0), "party": t.get("party", ""),
                     "senate_rank": t.get("state_rank", "")})
    return pd.DataFrame(rows).sort_values(["state_abbrev", "chamber", "district", "name"])


def zip_districts(text: str) -> pd.DataFrame:
    """zip, state_abbrev, district, share of the ZIP's land area in that district."""
    df = pd.read_csv(io.StringIO(text.lstrip("﻿")), sep="|", dtype=str)
    df = df[df["GEOID_ZCTA5_20"].notna() & df["GEOID_CD119_20"].notna()].copy()
    df["state_abbrev"] = df["GEOID_CD119_20"].str[:2].map(FIPS)
    code = df["GEOID_CD119_20"].str[2:]
    df["district"] = code.replace({"98": "00", "ZZ": "00"}).astype(int)  # 00 at-large, 98 nonvoting delegate
    df["land"] = pd.to_numeric(df["AREALAND_PART"], errors="coerce").fillna(0)
    df = df[df["state_abbrev"].notna() & ~code.eq("ZZ")]
    total = df.groupby("GEOID_ZCTA5_20")["land"].transform("sum")
    df["share"] = (df["land"] / total.where(total > 0)).fillna(1 / df.groupby("GEOID_ZCTA5_20")["land"].transform("size"))
    df = df[df["share"] >= MIN_SHARE]
    out = df.rename(columns={"GEOID_ZCTA5_20": "zip"})[["zip", "state_abbrev", "district", "share"]]
    out["share"] = out["share"].round(3)
    return out.sort_values(["zip", "share"], ascending=[True, False])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--zips", action="store_true", help="rebuild data/zip_districts.csv from the Census file")
    a = ap.parse_args()
    if a.zips:
        with urllib.request.urlopen(CENSUS_URL, timeout=120) as r:
            out = zip_districts(r.read().decode("utf-8-sig"))
        out.to_csv(ZIPS, index=False)
        print(f"{out['zip'].nunique():,} ZIP codes -> {ZIPS.relative_to(ROOT)}")
    s = seats()
    s.to_csv(SEATS, index=False)
    print(f"{len(s)} current members -> {SEATS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
