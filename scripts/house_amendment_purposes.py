#!/usr/bin/env python3
"""
Add what each House amendment does to its roll call's description.

The House Clerk's record (see house_vote_labels.py) names an amendment's sponsor but not its purpose. Congress.gov
keeps an official record of every House amendment, with a one-line purpose, and links it to the roll calls held on
it. This script finds the Congress.gov amendment behind each House amendment roll call and stores its purpose in
data/house_amendments.csv. house_vote_labels.apply_labels() then adds the purpose to the description.

Needs a free Congress.gov API key (from https://api.data.gov/signup/) in the CONGRESS_API_KEY environment variable.
Without one it does nothing. Each run stops after a fixed number of requests or minutes, whichever comes first,
and picks up where it left off next time, so the first fill is spread over several runs. Progress is saved as it
goes, so a run that is cut off still keeps what it found.

How a roll call is matched to its amendment:
- 2023 on (118th Congress and later): Congress.gov's House roll call record names the amendment directly.
- Before 2023: Congress.gov lists each bill's amendments with their purpose and latest action, and the latest action
  of an amendment that got a roll call usually names it ("... (Roll no. 380)"). Only when a bill still has roll calls
  left unmatched does the script read the full action history of its remaining amendments, which is slow. Every
  amendment checked is cached, voted on or not, so nothing is looked up twice.

Usage:
    CONGRESS_API_KEY=... python scripts/house_amendment_purposes.py [--budget 4000] [--minutes 50]
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
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
LABELS_FILE = DATA_DIR / "house_vote_labels.csv"
AMENDMENTS_FILE = DATA_DIR / "house_amendments.csv"
API = "https://api.congress.gov/v3"
COLUMNS = ["congress", "hamdt", "bill", "session", "clerk_rollnumber", "purpose"]
BILL_TYPES = [("H CON RES", "hconres"), ("H J RES", "hjres"), ("H RES", "hres"), ("H R", "hr"),
              ("S CON RES", "sconres"), ("S J RES", "sjres"), ("S RES", "sres"), ("S", "s")]
FIRST_HOUSE_VOTE_CONGRESS = 118  # Congress.gov's House roll call records start in 2023
MAX_PURPOSE = 300
SAVE_EVERY = 100  # write progress after this many new rows
TIMEOUT = 90  # seconds to wait for one Congress.gov answer
ROLL_NO = re.compile(r"Roll no\. ?(\d+)", re.IGNORECASE)


class OutOfBudget(Exception):
    pass


class Client:
    """Congress.gov API calls, counted against a per-run budget and time limit, paced to stay under the hourly limit."""

    def __init__(self, key: str, budget: int, pause: float = 0.8, minutes: float | None = None):
        self.key, self.budget, self.pause, self.used = key, budget, pause, 0
        self.deadline = time.monotonic() + minutes * 60 if minutes else None

    def get(self, path_or_url: str, **params) -> dict | None:
        if self.used >= self.budget or (self.deadline is not None and time.monotonic() >= self.deadline):
            raise OutOfBudget
        url = path_or_url if path_or_url.startswith("http") else API + path_or_url
        query = {"format": "json", "api_key": self.key, **params}
        sep = "&" if "?" in url else "?"
        url = url + sep + urllib.parse.urlencode(query)
        for attempt in range(3):
            self.used += 1
            time.sleep(self.pause)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "PartyCohesion data refresh"})
                # Some Congress.gov endpoints (an amendment's actions) can take over 30 seconds to answer
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


def recorded_house_votes(client: Client, congress: int, hamdt: str) -> list[tuple[int, int]]:
    """(session, clerk roll number) of every House roll call on an amendment."""
    found, url = [], f"/amendment/{congress}/hamdt/{hamdt}/actions"
    while url:
        data = client.get(url, limit=250) or {}
        for action in data.get("actions", []):
            for v in action.get("recordedVotes", []) or []:
                if str(v.get("chamber", "")).lower().startswith("house") and v.get("rollNumber"):
                    found.append((int(v.get("sessionNumber") or 0), int(v["rollNumber"])))
        url = (data.get("pagination") or {}).get("next")
    return found


def bill_amendments(client: Client, congress: int, kind: str, number: str) -> list[dict]:
    """A bill's House amendments, each with its number, purpose and latest action, from one list request per 250."""
    items, url = [], f"/bill/{congress}/{kind}/{number}/amendments"
    while url:
        data = client.get(url, limit=250) or {}
        items += [a for a in data.get("amendments", [])
                  if str(a.get("type", "")).upper() == "HAMDT" and a.get("number")]
        url = (data.get("pagination") or {}).get("next")
    return items


def latest_roll_call(congress: int, item: dict) -> tuple[int, int] | None:
    """(session, clerk roll number) named in an amendment's latest action, if it names one."""
    action = item.get("latestAction") or {}
    m = ROLL_NO.search(str(action.get("text") or ""))
    year = str(action.get("actionDate") or "")[:4]
    if not m or not year.isdigit():
        return None
    return int(year) - (2 * congress + 1787) + 1, int(m.group(1))


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
    checked = set(zip(have["congress"].astype(int), have["hamdt"].astype(str)))
    todo = targets()
    added = 0
    saved_at = len(rows)

    def checkpoint() -> None:
        nonlocal saved_at
        if len(rows) - saved_at >= SAVE_EVERY:
            save(rows)
            saved_at = len(rows)

    try:
        # 2023 on: Congress.gov's roll call record names the amendment
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
        # Before 2023: list each bill's amendments and find the ones with these roll calls
        older = todo[todo["congress"] < FIRST_HOUSE_VOTE_CONGRESS]
        for (cong, legis), bill_rolls in older.groupby(["congress", "legis_num"]):
            bp = bill_path(legis)
            if bp is None:
                continue
            cong = int(cong)
            left = {(int(a), int(b)) for a, b in zip(bill_rolls["session"], bill_rolls["clerk_rollnumber"])}

            def record(item: dict, votes: list[tuple[int, int]]) -> None:
                nonlocal added
                hamdt = str(item["number"])
                if not votes:
                    rows.append({"congress": cong, "hamdt": hamdt, "bill": legis, "session": None,
                                 "clerk_rollnumber": None, "purpose": None})  # checked: no roll call we need
                else:
                    purpose = clean_purpose(item.get("purpose") or item.get("description")) \
                        or amendment_purpose(client, cong, hamdt)
                    for session, roll in votes:
                        rows.append({"congress": cong, "hamdt": hamdt, "bill": legis, "session": session,
                                     "clerk_rollnumber": roll, "purpose": purpose})
                        added += 1
                        left.discard((session, roll))
                checked.add((cong, hamdt))
                checkpoint()

            # Fast pass: the roll call named in each amendment's latest action
            slow = []
            for item in bill_amendments(client, cong, *bp):
                if (cong, str(item["number"])) in checked:
                    continue
                vote = latest_roll_call(cong, item)
                if vote is None:
                    slow.append(item)
                else:
                    record(item, [vote] if vote in left else [])
            # Slow pass, only while this bill still has roll calls without a match: read the full action history
            for item in slow:
                if not left:
                    break
                record(item, [v for v in recorded_house_votes(client, cong, str(item["number"])) if v in left])
    except OutOfBudget:
        print(f"Stopped after {client.used:,} requests (this run's request or time limit, or the hourly limit); "
              "the rest comes next run")
    save(rows)
    print(f"Amendment purposes: matched {added:,} roll calls this run ({client.used:,} requests)")
    return added


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget", type=int, default=4000, help="most Congress.gov requests to make this run")
    parser.add_argument("--minutes", type=float, default=50, help="stop after this many minutes")
    args = parser.parse_args()
    key = os.environ.get("CONGRESS_API_KEY", "").strip()
    if not key:
        print("No CONGRESS_API_KEY set, so amendment purposes were skipped.")
        return
    run(args.budget, key, minutes=args.minutes)


if __name__ == "__main__":
    sys.exit(main())
