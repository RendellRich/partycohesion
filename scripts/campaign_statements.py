#!/usr/bin/env python3
"""
Campaign statements and votes: what House members said on their own campaign websites, next to how they voted on the
closest roll call once in office.

Source of the statements: CampaignView (Porter, Case and Treul, 2025, Harvard Dataverse, doi:10.7910/DVN/JIEAPT,
released as CC0), which collected the issue pages of House primary candidates' campaign websites in 2018, 2020 and
2022. Each statement carries the candidate's Bioguide ID. Text CampaignView took from official House.gov pages is left
out, so every statement here is campaign material.

CampaignView tags each statement's topic but not its stance, so stances are hand-coded in data/campaign_stances.csv
(Supports or Opposes, with the CampaignView statement IDs read). data/campaign_topics.csv lists, for each topic and
campaign year, the roll call that tests it and which vote matches a "Supports" stance.

Writes data/campaign_statement_votes.csv: one row per member, topic and roll call, with the stance, the campaign
text (only the sentences on the topic), the vote that matches the stance, and the member's actual vote.

Usage:
    python scripts/campaign_statements.py
"""

import re
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from vote_index import PREFIX  # noqa: E402

DATA = ROOT / "data"
RAW = DATA / "raw" / "campaignview_policy_platforms.csv"
CAMPAIGNVIEW_URL = "https://dataverse.harvard.edu/api/access/datafile/11595287"  # policy_platforms.csv
STANCES = DATA / "campaign_stances.csv"
TOPICS = DATA / "campaign_topics.csv"
OUT = DATA / "campaign_statement_votes.csv"
OPPOSITE = {"Yea": "Nay", "Nay": "Yea"}
CAST = {1: "Yea", -1: "Nay", 0: "Did not vote"}
# Sentences about each topic, and look-alikes to skip ("Wall Street", "the Berlin Wall")
TOPIC_RE = {
    "border_wall": (r"\bwall\b|fence|barrier", r"wall street|berlin wall|wall of my office"),
    "abortion": (r"abortion|pro-life|pro-choice|unborn|roe v|reproductive|planned parenthood|sanctity of (human )?life|"
                 r"right to choose|life begins|born.alive|heartbeat|right to life", r"^$"),
    "background_checks": (r"background check|gun control|gun law|gun show|infring|second amendment|2nd amendment|"
                          r"firearm", r"health care workers"),
}


def platforms() -> pd.DataFrame:
    if not RAW.exists():
        RAW.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(CAMPAIGNVIEW_URL, RAW)
    return pd.read_csv(RAW, low_memory=False)


def excerpt(texts: list[str], topic: str, limit: int = 600) -> str:
    keep, skip = (re.compile(p, re.IGNORECASE) for p in TOPIC_RE[topic])
    out = []
    for text in texts:
        for s in re.split(r"(?<=[.!?\n])\s+", str(text)):
            s = s.strip(" *o\t\n")
            if keep.search(s) and not skip.search(s) and s not in out:
                out.append(s)
    joined = " … ".join(out)
    return joined if len(joined) <= limit else joined[:limit].rsplit(" ", 1)[0] + " …"


def build() -> pd.DataFrame:
    stances = pd.read_csv(STANCES, comment="#")
    topics = pd.read_csv(TOPICS, comment="#")
    text = platforms().set_index("statement_id")
    members = pd.read_csv(DATA / "members_processed.csv").drop_duplicates(["congress", "chamber", "bioguide_id"])
    rows = []
    for _, t in topics.iterrows():
        with np.load(DATA / "matrices" / f"{PREFIX[t['chamber']]}{int(t['congress'])}.npz") as f:
            icpsrs, rolls, votes = f["icpsr"], f["rollnumber"], f["votes"]
        col = int(np.where(rolls == t["rollnumber"])[0][0])
        cast = dict(zip(icpsrs.tolist(), votes[:, col].tolist()))
        who = members[(members["congress"] == t["congress"]) & (members["chamber"] == t["chamber"])]
        s = stances[(stances["topic_id"] == t["topic_id"]) & (stances["campaign_year"] == t["campaign_year"])]
        s = s.merge(who[["bioguide_id", "icpsr", "name", "party", "state_abbrev"]], on="bioguide_id", how="inner")
        for _, r in s.iterrows():
            ids = [int(i) for i in str(r["statement_ids"]).split(";")]
            src = text.loc[ids]
            expected = t["vote_if_supports"] if r["stance"] == "Supports" else OPPOSITE[t["vote_if_supports"]]
            actual = CAST.get(int(cast.get(int(r["icpsr"]), 0)), "Did not vote")
            rows.append({
                "topic_id": t["topic_id"], "topic": t["topic"], "campaign_year": r["campaign_year"],
                "congress": t["congress"], "chamber": t["chamber"], "rollnumber": t["rollnumber"],
                "vote_label": t["vote_label"], "vote_note": t["note"], "bioguide_id": r["bioguide_id"],
                "icpsr": int(r["icpsr"]), "name": r["name"], "party": r["party"], "state_abbrev": r["state_abbrev"],
                "district": int(src["cd"].iloc[0]), "stance": r["stance"],
                "statement": excerpt(src["issue_text"].tolist(), t["topic_id"]),
                "expected_vote": expected, "actual_vote": actual,
                "same_direction": "Did not vote" if actual == "Did not vote" else
                ("Yes" if actual == expected else "No"),
            })
    return pd.DataFrame(rows).sort_values(["topic_id", "campaign_year", "name"])


def main() -> None:
    out = build()
    out.to_csv(OUT, index=False, lineterminator="\n")
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(out)} rows, {(out['same_direction'] == 'No').sum()} in a different "
          f"direction from the campaign statement")


if __name__ == "__main__":
    main()
