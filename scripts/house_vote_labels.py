#!/usr/bin/env python3
"""
Fill in House roll calls that Voteview leaves without a description.

Voteview has no description for most House amendment votes, so they show up in All Votes as just "H.R. 2670 On
Agreeing to the Amendment". The House Clerk's official record of each roll call names the amendment's sponsor
(for example "Jackson of Texas Amendment No. 5"). This module downloads those records for the roll calls that need
them, keeps them in data/house_vote_labels.csv so each is fetched only once, and writes a description from them.

Usage:
    python scripts/house_vote_labels.py          # fetch any missing records, then update all_votes.csv and key_votes.csv

refresh_data.py also calls fetch_missing() and apply_labels() on every refresh. A failed download is skipped and
retried next time; it never stops the refresh.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
LABELS_FILE = DATA_DIR / "house_vote_labels.csv"
CLERK_URL = "https://clerk.house.gov/evs/{year}/roll{roll:03d}.xml"
COLUMNS = ["congress", "rollnumber", "year", "clerk_rollnumber", "legis_num", "amendment_author", "clerk_vote_desc"]
BILL_PREFIX = [("H CON RES", "H.Con.Res."), ("H J RES", "H.J.Res."), ("H RES", "H.Res."), ("H R", "H.R."),
               ("S CON RES", "S.Con.Res."), ("S J RES", "S.J.Res."), ("S RES", "S.Res."), ("S", "S.")]


def needs_label(rc: pd.DataFrame) -> pd.Series:
    """House roll calls with no description in Voteview."""
    return rc["vote_desc"].isna() | (rc["vote_desc"].astype(str).str.strip() == "")


def session_year(congress: int, session: int) -> int:
    """The Clerk files roll calls by the session's year, even for votes held in the first days of January."""
    return 2 * int(congress) + 1787 + int(session) - 1


def bill_label(legis_num: str) -> str:
    """'H R 2670' -> 'H.R. 2670'. Anything that isn't a bill number (QUORUM, JOURNAL) -> ''."""
    text = re.sub(r"\s+", " ", _text(legis_num)).upper()
    for raw, nice in BILL_PREFIX:
        m = re.fullmatch(re.escape(raw) + r" (\d+)", text)
        if m:
            return f"{nice} {m.group(1)}"
    return ""


def _text(value) -> str:
    return "" if value is None or (isinstance(value, float) and value != value) else str(value).strip()


def describe(row) -> str:
    """The description shown for a roll call, built from the Clerk's record. '' if it says nothing useful."""
    desc = _text(row.get("clerk_vote_desc"))
    if desc:
        return desc
    author = _text(row.get("amendment_author"))
    if author:
        bill = bill_label(row.get("legis_num"))
        return f"{author} to {bill}" if bill else author
    return ""


def fetch_one(year: int, roll: int) -> dict | None:
    url = CLERK_URL.format(year=year, roll=roll)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PartyCohesion data refresh"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            root = ET.fromstring(resp.read())
    except Exception:
        return None
    meta = root.find("vote-metadata")
    if meta is None or meta.findtext("rollcall-num", "").strip() != str(roll):
        return None
    return {"legis_num": meta.findtext("legis-num", "").strip(),
            "amendment_author": meta.findtext("amendment-author", "").strip(),
            "clerk_vote_desc": meta.findtext("vote-desc", "").strip()}


def load_labels() -> pd.DataFrame:
    if LABELS_FILE.exists():
        return pd.read_csv(LABELS_FILE, dtype={"legis_num": str, "amendment_author": str, "clerk_vote_desc": str})
    return pd.DataFrame(columns=COLUMNS)


def fetch_missing(congresses=None, workers: int = 8, pause: float = 0.05) -> int:
    """Download the Clerk's record for every House roll call that has no description and isn't cached yet."""
    labels = load_labels()
    have = set(zip(labels["congress"].astype(int), labels["rollnumber"].astype(int)))
    todo = []
    for path in sorted(RAW_DIR.glob("H*_rollcalls.csv")):
        rc = pd.read_csv(path)
        if congresses is not None and int(rc["congress"].iloc[0]) not in congresses:
            continue
        for r in rc[needs_label(rc)].itertuples():
            if (int(r.congress), int(r.rollnumber)) not in have:
                todo.append((int(r.congress), int(r.rollnumber), session_year(r.congress, r.session),
                             int(r.clerk_rollnumber)))
    if not todo:
        return 0

    def work(item):
        time.sleep(pause)
        return item, fetch_one(item[2], item[3])

    rows, failed = [], 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for (cong, roll, year, clerk_roll), got in pool.map(work, todo):
            if got is None:
                failed += 1
                continue
            rows.append({"congress": cong, "rollnumber": roll, "year": year, "clerk_rollnumber": clerk_roll, **got})
    if rows:
        labels = pd.concat([labels, pd.DataFrame(rows, columns=COLUMNS)], ignore_index=True)
        labels = labels.drop_duplicates(["congress", "rollnumber"], keep="last").sort_values(["congress", "rollnumber"])
        labels.to_csv(LABELS_FILE, index=False)
    print(f"House Clerk records: fetched {len(rows):,}, failed {failed:,} (failures are retried next refresh)")
    return len(rows)


def apply_labels(votes: pd.DataFrame) -> pd.DataFrame:
    """Fill blank House vote_desc values from the Clerk's records. Other rows are left exactly as they were."""
    labels = load_labels()
    if labels.empty:
        return votes
    text = labels.assign(_desc=labels.apply(describe, axis=1))[["congress", "rollnumber", "_desc"]]
    text = text[text["_desc"] != ""].assign(chamber="House")
    out = votes.merge(text, on=["congress", "chamber", "rollnumber"], how="left")
    blank = needs_label(out) & out["_desc"].notna()
    out.loc[blank, "vote_desc"] = out.loc[blank, "_desc"]
    return out.drop(columns="_desc")


def main() -> None:
    fetch_missing()
    for name in ("all_votes.csv", "key_votes.csv"):
        path = DATA_DIR / name
        before = pd.read_csv(path)
        after = apply_labels(before)
        filled = int((needs_label(before) & ~needs_label(after)).sum())
        after.to_csv(path, index=False)
        print(f"{name}: filled {filled:,} blank descriptions")


if __name__ == "__main__":
    sys.exit(main())
