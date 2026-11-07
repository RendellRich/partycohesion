#!/usr/bin/env python3
"""
Add what each House amendment does to its roll call's description.

The House Clerk's record (see house_vote_labels.py) names an amendment's sponsor but not its purpose. Congress.gov
keeps an official record of every House amendment, with a one-line purpose, and links it to the roll calls held on
it. This script finds the amendment behind each House amendment roll call and stores its purpose in
data/house_amendments.csv. house_vote_labels.apply_labels() then adds the purpose to the description.

How a roll call is matched to its amendment:
- Before 2023: GovInfo publishes each bill's full Congress.gov record as one static file (BILLSTATUS XML), with every
  House amendment, its purpose and the roll calls held on it. One download per bill, no key needed. (Congress.gov's
  API answers these lookups for older bills very slowly, often not at all.)
- 2023 on (118th Congress and later): Congress.gov's House roll call record names the amendment directly. This part
  needs a free Congress.gov API key (from https://api.data.gov/signup/) in the CONGRESS_API_KEY environment variable
  and is skipped without one.

Each run stops after a fixed number of requests or minutes, whichever comes first, and picks up where it left off
next time. Progress is saved as it goes, so a run that is cut off still keeps what it found.

Usage:
    [CONGRESS_API_KEY=...] python scripts/house_amendment_purposes.py [--budget 4000] [--minutes 50]
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LABELS_FILE = DATA_DIR / "house_vote_labels.csv"
AMENDMENTS_FILE = DATA_DIR / "house_amendments.csv"
API = "https://api.congress.gov/v3"
BILL_STATUS = "https://www.govinfo.gov/bulkdata/BILLSTATUS/{congress}/{kind}/BILLSTATUS-{congress}{kind}{number}.xml"
COLUMNS = ["congress", "hamdt", "bill", "session", "clerk_rollnumber", "purpose"]
BILL_TYPES = [("H CON RES", "hconres"), ("H J RES", "hjres"), ("H RES", "hres"), ("H R", "hr"),
              ("S CON RES", "sconres"), ("S J RES", "sjres"), ("S RES", "sres"), ("S", "s")]
FIRST_HOUSE_VOTE_CONGRESS = 118  # Congress.gov's House roll call records start in 2023
MAX_PURPOSE = 300
SAVE_EVERY = 100  # write progress after this many new rows
TIMEOUT = 90  # seconds to wait for one answer
ROLL_NO = re.compile(r"Roll no\. ?(\d+)", re.IGNORECASE)


class OutOfBudget(Exception):
    pass


class Client:
    """Congress.gov API calls, counted against a per-run budget and time limit, paced to stay under the hourly limit."""

    def __init__(self, key: str, budget: int, pause: float = 0.8, minutes: float | None = None):
        self.key, self.budget, self.pause, self.used = key, budget, pause, 0
        self.deadline = time.monotonic() + minutes * 60 if minutes else None

    def _check(self) -> None:
        if self.used >= self.budget or (self.deadline is not None and time.monotonic() >= self.deadline):
            raise OutOfBudget

    def get_xml(self, url: str) -> ET.Element | None:
        """A static XML file (GovInfo bulk data): no key, and a missing file is None."""
        self._check()
        self.used += 1
        time.sleep(min(self.pause, 0.3))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PartyCohesion data refresh"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return ET.fromstring(resp.read())
        except Exception:
            return None

    def get(self, path_or_url: str, **params) -> dict | None:
        self._check()
        url = path_or_url if path_or_url.startswith("http") else API + path_or_url
        query = {"format": "json", "api_key": self.key, **params}
        sep = "&" if "?" in url else "?"
        url = url + sep + urllib.parse.urlencode(query)
        for attempt in range(3):
            self.used += 1
            time.sleep(self.pause)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "PartyCohesion data refresh"})
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    return json.loads(resp.read())
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return None
                if e.code == 429:  # over the hourly limit: stop this run, resume next time
                    raise OutOfBudget
                if attempt == 2:
                    return None
            except Exception:
                if attempt == 2:
                    return None
        return None


def bill_path(legis_num: str) -> tuple[str, str] | None:
    """'H R 2670' -> ('hr', '2670')."""
    text = re.sub(r"\s+", " ", str(legis_num or "")).strip().upper()
    for raw, kind in BILL_TYPES:
        m = re.fullmatch(re.escape(raw) + r" (\d+)", text)
        if m:
            return kind, m.group(1)
    return None


def clean_purpose(text) -> str:
    """Drop the boilerplate that opens most House amendment purposes and keep one readable line."""
    if text is None or (isinstance(text, float) and text != text):
        return ""
    s = re.sub(r"\s+", " ", str(text)).strip()
    s = re.sub(r"^(An )?amendment (numbered|No\.) ?\d+ printed in (Part [A-Z] of )?(House Report|the Congressional "
               r"Record)[^,;]*?\bto\b ", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^(An )?amendment to\b ", "", s, flags=re.IGNORECASE)
    s = s.rstrip(".")
    if s:
        s = s[0].upper() + s[1:]
    return s if len(s) <= MAX_PURPOSE else s[: MAX_PURPOSE - 1].rsplit(" ", 1)[0] + "…"


def amendment_purpose(client: Client, congress: int, hamdt: str) -> str:
    data = client.get(f"/amendment/{congress}/hamdt/{hamdt}") or {}
    a = data.get("amendment") or {}
    return clean_purpose(a.get("purpose") or a.get("description"))


def bill_status_amendments(root: ET.Element) -> list[dict]:
    """Each House amendment in a GovInfo bill status file: number, purpose and the House roll calls held on it."""
    out = []
    for a in root.findall("./bill/amendments/amendment"):
        if (a.findtext("type") or "").upper() != "HAMDT" or not a.findtext("number"):
            continue
        description = a.findtext("description") or ""
        purpose = clean_purpose(a.findtext("purpose")) or ("" if description.startswith("(See") else
                                                           clean_purpose(description))
        votes = set()
        for v in a.iter("recordedVote"):
            if (v.findtext("chamber") or "").lower().startswith("house") and (v.findtext("rollNumber") or "").isdigit():
                votes.add((int(v.findtext("sessionNumber") or 0), int(v.findtext("rollNumber"))))
        if not votes:  # older files list no recordedVote, only action text ending "(Roll no. 526)."
            congress = int(a.findtext("congress") or 0)
            for action in a.iter():
                m = ROLL_NO.search(action.findtext("text") or "")
                year = (action.findtext("actionDate") or "")[:4]
                if m and congress and year.isdigit():
                    votes.add((int(year) - (2 * congress + 1787) + 1, int(m.group(1))))
        out.append({"number": a.findtext("number").strip(), "purpose": purpose, "votes": sorted(votes)})
    return out


def load_amendments() -> pd.DataFrame:
    if AMENDMENTS_FILE.exists():
        return pd.read_csv(AMENDMENTS_FILE, dtype={"hamdt": str, "bill": str, "purpose": str})
    return pd.DataFrame(columns=COLUMNS)


def targets() -> pd.DataFrame:
    """House amendment roll calls (named by the Clerk) that don't have a purpose yet."""
    labels = pd.read_csv(LABELS_FILE, dtype={"legis_num": str, "amendment_author": str})
    t = labels[labels["amendment_author"].fillna("").str.strip() != ""].copy()
    t["session"] = t["year"] - (2 * t["congress"] + 1787) + 1
    have = load_amendments()
    done = set(zip(have["congress"].astype(int), have["session"].fillna(0).astype(int),
                   have["clerk_rollnumber"].fillna(0).astype(int)))
    keep = [(c, s, r) not in done for c, s, r in zip(t["congress"], t["session"], t["clerk_rollnumber"])]
    return t[keep]


def save(rows: list[dict]) -> None:
    out = pd.DataFrame(rows, columns=COLUMNS).drop_duplicates(["congress", "hamdt", "session", "clerk_rollnumber"])
    out.sort_values(["congress", "hamdt"]).to_csv(AMENDMENTS_FILE, index=False)


def run(budget: int, key: str, minutes: float | None = None, client: Client | None = None) -> int:
    client = client or Client(key, budget, minutes=minutes)
    have = load_amendments()
    rows = have.to_dict("records")
    todo = targets()
    added = 0
    saved_at = len(rows)

    def checkpoint() -> None:
        nonlocal saved_at
        if len(rows) - saved_at >= SAVE_EVERY:
            save(rows)
            saved_at = len(rows)

    try:
        # Before 2023: one GovInfo bill status file per bill lists its amendments and their roll calls
        older = todo[todo["congress"] < FIRST_HOUSE_VOTE_CONGRESS]
        for (cong, legis), bill_rolls in older.groupby(["congress", "legis_num"]):
            bp = bill_path(legis)
            if bp is None:
                continue
            cong = int(cong)
            left = {(int(a), int(b)) for a, b in zip(bill_rolls["session"], bill_rolls["clerk_rollnumber"])}
            root = client.get_xml(BILL_STATUS.format(congress=cong, kind=bp[0], number=bp[1]))
            if root is None:
                continue
            for item in bill_status_amendments(root):
                for session, roll in [v for v in item["votes"] if v in left]:
                    rows.append({"congress": cong, "hamdt": item["number"], "bill": legis, "session": session,
                                 "clerk_rollnumber": roll, "purpose": item["purpose"]})
                    left.discard((session, roll))
                    added += 1
                checkpoint()
        # 2023 on: Congress.gov's roll call record names the amendment (needs the API key)
        if key:
            for r in todo[todo["congress"] >= FIRST_HOUSE_VOTE_CONGRESS].itertuples():
                data = client.get(f"/house-vote/{r.congress}/{r.session}/{r.clerk_rollnumber}") or {}
                v = data.get("houseRollCallVote") or {}
                hamdt = str(v.get("amendmentNumber") or "")
                if str(v.get("amendmentType", "")).upper() != "HAMDT" or not hamdt:
                    continue
                rows.append({"congress": r.congress, "hamdt": hamdt, "bill": r.legis_num, "session": r.session,
                             "clerk_rollnumber": r.clerk_rollnumber,
                             "purpose": amendment_purpose(client, r.congress, hamdt)})
                added += 1
                checkpoint()
    except OutOfBudget:
        print(f"Stopped after {client.used:,} requests (this run's request or time limit, or the hourly limit); "
              "the rest comes next run")
    save(rows)
    print(f"Amendment purposes: matched {added:,} roll calls this run ({client.used:,} requests)")
    return added


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget", type=int, default=4000, help="most requests to make this run")
    parser.add_argument("--minutes", type=float, default=50, help="stop after this many minutes")
    args = parser.parse_args()
    key = os.environ.get("CONGRESS_API_KEY", "").strip()
    if not key:
        print("No CONGRESS_API_KEY set, so only amendments before 2023 (from GovInfo) are looked up.")
    run(args.budget, key, minutes=args.minutes)


if __name__ == "__main__":
    sys.exit(main())
