#!/usr/bin/env python3
"""
Member details for the Members profile: official photo, years served, website, office phone and current committees.

Source: the @unitedstates/congress-legislators project (public domain), which publishes every member of Congress with
their terms, official website and office, plus current committee assignments. Official photos come from the same
project's image set (public domain, from the Government Publishing Office's Congressional Pictorial Directory).

Writes data/member_details.csv: one row per member in data/members_processed.csv.

Usage:
    python scripts/member_details.py
"""

import concurrent.futures
import json
import sys
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "member_details.csv"
BASE = "https://unitedstates.github.io/congress-legislators/"
PHOTO = "https://unitedstates.github.io/images/congress/225x275/{bioguide}.jpg"
COLS = ["bioguide_id", "full_name", "first_year", "last_year", "in_office", "website", "contact_form", "phone",
        "office", "committees", "photo_url"]


def fetch(name: str):
    with urllib.request.urlopen(BASE + name, timeout=60) as r:
        return json.load(r)


def photo_exists(url: str) -> bool:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=20) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001 - a missing or unreachable photo just isn't shown
        return False


def build() -> pd.DataFrame:
    current = fetch("legislators-current.json")
    people = current + fetch("legislators-historical.json")
    in_office = {p["id"]["bioguide"] for p in current}
    committees = {c["thomas_id"]: c for c in fetch("committees-current.json")}
    for c in list(committees.values()):
        for sub in c.get("subcommittees", []):
            committees[c["thomas_id"] + sub["thomas_id"]] = {"name": f"{c['name']}: {sub['name']}", "sub": True}
    seats: dict[str, list[str]] = {}
    for cid, members in fetch("committee-membership-current.json").items():
        c = committees.get(cid)
        if not c or c.get("sub"):
            continue  # full committees only, to keep the profile short
        for m in members:
            title = f" ({m['title']})" if m.get("title") else ""
            seats.setdefault(m["bioguide"], []).append(c["name"] + title)

    wanted = set(pd.read_csv(DATA / "members_processed.csv", usecols=["bioguide_id"])["bioguide_id"].dropna())
    rows = []
    for p in people:
        b = p["id"].get("bioguide")
        if b not in wanted:
            continue
        terms = p["terms"]
        last = terms[-1]
        rows.append({
            "bioguide_id": b,
            "full_name": p["name"].get("official_full") or f"{p['name'].get('first', '')} {p['name'].get('last', '')}",
            "first_year": int(terms[0]["start"][:4]),
            "last_year": int(last["end"][:4]),
            "in_office": b in in_office,
            "website": last.get("url", "") if b in in_office else "",
            "contact_form": last.get("contact_form", "") if b in in_office else "",
            "phone": last.get("phone", "") if b in in_office else "",
            "office": last.get("office") or last.get("address", "") if b in in_office else "",
            "committees": "; ".join(sorted(seats.get(b, []))),
            "photo_url": PHOTO.format(bioguide=b),
        })
    out = pd.DataFrame(rows, columns=COLS).drop_duplicates("bioguide_id").sort_values("bioguide_id")
    with concurrent.futures.ThreadPoolExecutor(16) as pool:
        found = list(pool.map(photo_exists, out["photo_url"]))
    out.loc[[not f for f in found], "photo_url"] = ""
    return out


def main() -> None:
    out = build()
    out.to_csv(OUT, index=False, lineterminator="\n")
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(out)} members, {int(out['in_office'].sum())} in office now")


if __name__ == "__main__":
    sys.exit(main())
