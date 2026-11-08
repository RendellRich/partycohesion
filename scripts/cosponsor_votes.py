#!/usr/bin/env python3
"""
Members who cosponsored a bill and then voted against it on final passage.

A cosponsor puts their name on a bill before it reaches the floor, so a "No" from a cosponsor on the bill's final
passage vote is the plainest case of a member voting against something they signed. The bill can change between
signing and the vote, so each vote also records how many amendments were agreed to before it and whether the text
had changed at all (a committee reported it with changes, a rule swapped in a substitute, or the House passed it
"as amended").

Source: GovInfo's bill status files (BILLSTATUS XML, the Congress.gov record of each bill, one static file per bill,
no key needed) for the sponsor, cosponsors (minus withdrawn ones) and amendments; the site's own vote matrices for
how each member voted.

Writes:
- data/cosponsor_votes.csv: one row per final passage vote on a bill or joint resolution: how many of its sponsor
  and cosponsors voted Yea, Nay, or not at all, and how many amendments were agreed to before the vote.
- data/cosponsor_nays.csv: one row per sponsor or cosponsor who voted Nay on that vote.

Older Congresses don't change, so by default only Congresses not yet in the files, and the newest Congress, are
fetched. Usage:
    python scripts/cosponsor_votes.py [--congress 118 119] [--minutes 50]
"""

import argparse
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from vote_index import load_matrix  # noqa: E402

DATA = ROOT / "data"
VOTES_FILE = DATA / "cosponsor_votes.csv"
NAYS_FILE = DATA / "cosponsor_nays.csv"
BILL_STATUS = "https://www.govinfo.gov/bulkdata/BILLSTATUS/{congress}/{kind}/BILLSTATUS-{congress}{kind}{number}.xml"
PASSAGE_RE = r"^On (?:Passage|Motion to Suspend the Rules and Pass|Passage of the Bill|the Joint Resolution)"
BILL_RE = r"^(HR|S|HJRES|SJRES)(\d+)$"
# Bill actions that mean the text changed after it was introduced: a committee reported it with changes, or a rule
# replaced its text with a substitute
CHANGE_RE = r"Reported \(Amended\)|Ordered to be Reported \(Amended\)|in the nature of a substitute|as amended"
VOTE_COLS = ["congress", "chamber", "rollnumber", "date", "bill", "vote_question", "vote_result", "signers_voting",
             "signers_yea", "signers_nay", "signers_not_voting", "amendments_agreed_before", "changed_before_vote"]
NAY_COLS = ["congress", "chamber", "rollnumber", "bill", "icpsr", "bioguide_id", "role", "signed"]


def passage_votes(all_votes: pd.DataFrame) -> pd.DataFrame:
    q = all_votes["vote_question"].fillna("")
    b = all_votes["bill_number"].fillna("")
    return all_votes[q.str.match(PASSAGE_RE) & b.str.match(BILL_RE)]


def fetch(congress: int, bill: str, timeout: int = 60) -> ET.Element | None:
    kind, number = re.match(BILL_RE, bill).groups()
    url = BILL_STATUS.format(congress=congress, kind=kind.lower(), number=number)
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PartyCohesion data refresh"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return ET.fromstring(resp.read())
        except Exception:
            time.sleep(1)
    return None


def signers(root: ET.Element) -> dict[str, tuple[str, str]]:
    """bioguide id -> (role, date signed) for the sponsor and every cosponsor who didn't withdraw."""
    out = {}
    for item in root.findall("./bill/sponsors/item"):
        if item.findtext("bioguideId"):
            out[item.findtext("bioguideId")] = ("Sponsor", (root.findtext("./bill/introducedDate") or "")[:10])
    for item in root.findall("./bill/cosponsors/item"):
        if item.findtext("sponsorshipWithdrawnDate") or not item.findtext("bioguideId"):
            continue
        out.setdefault(item.findtext("bioguideId"), ("Cosponsor", (item.findtext("sponsorshipDate") or "")[:10]))
    return out


def amendments_agreed(root: ET.Element) -> list[str]:
    """Dates on which an amendment to the bill was agreed to (House or Senate)."""
    dates = []
    for a in root.findall("./bill/amendments/amendment"):
        for act in a.iter():
            text = act.findtext("text") or ""
            date = (act.findtext("actionDate") or "")[:10]
            if date and re.search(r"\bagreed to\b", text, re.IGNORECASE) and not re.search(r"not agreed to", text,
                                                                                          re.IGNORECASE):
                dates.append(date)
                break
    return dates


def change_dates(root: ET.Element) -> list[str]:
    """Dates of bill actions showing its text changed: reported with amendments, or a substitute made in order."""
    return [(it.findtext("actionDate") or "")[:10] for it in root.findall("./bill/actions/item")
            if re.search(CHANGE_RE, it.findtext("text") or "", re.IGNORECASE) and it.findtext("actionDate")]


def run(congresses: list[int], minutes: float) -> None:
    deadline = time.monotonic() + minutes * 60
    all_votes = pd.read_csv(DATA / "all_votes.csv")
    members = pd.read_csv(DATA / "members_processed.csv")[["congress", "chamber", "icpsr", "bioguide_id"]]
    old_votes = pd.read_csv(VOTES_FILE) if VOTES_FILE.exists() else pd.DataFrame(columns=VOTE_COLS)
    old_nays = pd.read_csv(NAYS_FILE) if NAYS_FILE.exists() else pd.DataFrame(columns=NAY_COLS)
    votes_out, nays_out, done = [], [], []
    for cong in congresses:
        todo = passage_votes(all_votes[all_votes["congress"] == cong])
        cache, rows, nays, finished = {}, [], [], True
        for r in todo.itertuples():
            if time.monotonic() > deadline:
                finished = False
                break
            if r.bill_number not in cache:
                root = fetch(cong, r.bill_number)
                cache[r.bill_number] = None if root is None else (signers(root), amendments_agreed(root),
                                                                   change_dates(root))
                time.sleep(0.1)
            if cache[r.bill_number] is None:
                continue
            signed, agreed, changes = cache[r.bill_number]
            n_agreed = sum(d <= r.date for d in agreed)
            mat = load_matrix(cong, r.chamber)
            if mat is None:
                continue
            ids, rolls, matrix = mat
            col = np.where(rolls == r.rollnumber)[0]
            if not len(col):
                continue
            here = members[(members["congress"] == cong) & (members["chamber"] == r.chamber)]
            here = here[here["bioguide_id"].isin(signed)].drop_duplicates("icpsr")
            cast = pd.DataFrame({"icpsr": ids, "v": matrix[:, col[0]]}).merge(here, on="icpsr")
            rows.append({"congress": cong, "chamber": r.chamber, "rollnumber": r.rollnumber, "date": r.date,
                         "bill": r.bill_number, "vote_question": r.vote_question, "vote_result": r.vote_result,
                         "signers_voting": int((cast["v"] != 0).sum()), "signers_yea": int((cast["v"] == 1).sum()),
                         "signers_nay": int((cast["v"] == -1).sum()), "signers_not_voting": int((cast["v"] == 0).sum()),
                         "amendments_agreed_before": n_agreed,
                         "changed_before_vote": bool(n_agreed or "as Amended" in r.vote_question
                                                     or any(d <= r.date for d in changes))})
            for x in cast[cast["v"] == -1].itertuples():
                role, when = signed[x.bioguide_id]
                nays.append({"congress": cong, "chamber": r.chamber, "rollnumber": r.rollnumber, "bill": r.bill_number,
                             "icpsr": int(x.icpsr), "bioguide_id": x.bioguide_id, "role": role, "signed": when})
        print(f"{cong}th Congress: {len(rows):,} passage votes, {len(cache):,} bills, {len(nays)} sponsor or "
              f"cosponsor Nays{'' if finished else ' (stopped at the time limit; the rest comes next run)'}")
        if finished:
            votes_out.append(pd.DataFrame(rows, columns=VOTE_COLS))
            nays_out.append(pd.DataFrame(nays, columns=NAY_COLS))
            done.append(cong)
        else:
            break
    if not done:
        return
    keep_v = old_votes[~old_votes["congress"].isin(done)]
    keep_n = old_nays[~old_nays["congress"].isin(done)]
    pd.concat([keep_v] + votes_out, ignore_index=True).sort_values(["congress", "chamber", "rollnumber"]).to_csv(
        VOTES_FILE, index=False)
    pd.concat([keep_n] + nays_out, ignore_index=True).sort_values(["congress", "chamber", "rollnumber", "icpsr"]).to_csv(
        NAYS_FILE, index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--congress", type=int, nargs="*", help="Congresses to (re)build; default: missing + newest")
    parser.add_argument("--minutes", type=float, default=50, help="stop after this many minutes")
    args = parser.parse_args()
    all_votes = pd.read_csv(DATA / "all_votes.csv", usecols=["congress"])
    every = sorted(all_votes["congress"].unique())
    if args.congress:
        congresses = args.congress
    else:
        have = set(pd.read_csv(VOTES_FILE)["congress"]) if VOTES_FILE.exists() else set()
        congresses = [c for c in every if c not in have] + [every[-1]]
        congresses = sorted(set(congresses))
    run(congresses, args.minutes)


if __name__ == "__main__":
    main()
