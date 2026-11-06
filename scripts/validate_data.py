#!/usr/bin/env python3
"""
Sanity-check the data files before they are committed.

Usage:
    python scripts/validate_data.py

Run after refresh_data.py. Exits with an error (and the automatic refresh does not commit
anything) if the data looks incomplete or wrong, e.g. a download was cut off or Voteview
changed a file format. A failed scheduled run also triggers GitHub's failure email.
"""

from pathlib import Path
import subprocess
import sys
from io import StringIO

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
problems: list[str] = []


def check(ok: bool, message: str) -> None:
    if not ok:
        problems.append(message)


def previous_version(path: str) -> pd.DataFrame | None:
    """The last committed copy of a data file, to catch sudden shrinkage."""
    try:
        text = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout
        return pd.read_csv(StringIO(text))
    except Exception:
        return None


members = pd.read_csv(DATA / "members_processed.csv")
summary = pd.read_csv(DATA / "unity_summary.csv")
key_votes = pd.read_csv(DATA / "key_votes.csv")
latest = int(members["congress"].max())
completed = sorted(c for c in members["congress"].unique() if c < latest)

# Members: every completed Congress should have a full chamber, and unity rates for nearly everyone
for cong in completed:
    for chamber, low in (("House", 420), ("Senate", 95)):
        rows = members[(members["congress"] == cong) & (members["chamber"] == chamber)]
        check(len(rows) >= low, f"{cong}th {chamber}: only {len(rows)} members (expected at least {low})")
        dr = rows[rows["party"].isin(["Democrat", "Republican"])]
        coverage = dr["party_unity_pct"].notna().mean() if len(dr) else 0
        check(coverage >= 0.95, f"{cong}th {chamber}: party unity missing for {1 - coverage:.0%} of Democrats/Republicans")

pct = members["party_unity_pct"].dropna()
check(pct.between(0, 100).all(), "party_unity_pct has values outside 0–100")
check(((members["votes_with_party"] <= members["unity_votes_cast"]) | members["unity_votes_cast"].isna()).all(),
      "votes_with_party is larger than unity_votes_cast for some members")

# Unity votes found for every completed Congress
for cong in completed:
    for chamber in ("House", "Senate"):
        n = summary.loc[(summary["congress"] == cong) & (summary["chamber"] == chamber), "party_unity_votes"]
        check(len(n) == 1 and n.iloc[0] > 50, f"{cong}th {chamber}: too few party-unity votes found ({n.tolist()})")

# Key votes: our Yea/Nay totals should match the official totals almost everywhere
yea = key_votes["dem_yea"] + key_votes["rep_yea"] + key_votes["other_yea"]
nay = key_votes["dem_nay"] + key_votes["rep_nay"] + key_votes["other_nay"]
match = ((yea == key_votes["yea_count"]) & (nay == key_votes["nay_count"])).mean()
check(match >= 0.97, f"only {match:.1%} of key votes match official Yea/Nay totals (expected at least 97%)")
off = ((yea - key_votes["yea_count"]).abs() + (nay - key_votes["nay_count"]).abs()).max()
check(off <= 3, f"a key vote's totals are off by {off} votes")

# Vote matrices present for every Congress and chamber
for cong in sorted(members["congress"].unique()):
    for prefix in ("H", "S"):
        path = DATA / "matrices" / f"{prefix}{cong}.npz"
        check(path.exists(), f"missing vote matrix {path.name}")
        if path.exists():
            with np.load(path) as f:
                check(f["votes"].shape[1] > 0, f"{path.name} has no roll calls")

# Position flip data: every hand-listed debt vote found, and each category has votes under both parties' presidents
flip_votes = pd.read_csv(DATA / "flip_votes.csv")
flip_member_votes = pd.read_csv(DATA / "flip_member_votes.csv")
debt_list = pd.read_csv(DATA / "flip_debt_limit_votes.csv", comment="#")
found = (flip_votes["category"] == "Debt limit").sum()
check(found == len(debt_list), f"only {found} of {len(debt_list)} listed debt limit votes were found in the roll-call data")
funding_list = pd.read_csv(DATA / "flip_funding_votes.csv", comment="#")
k = ["category", "congress", "chamber", "rollnumber"]
missing = funding_list[k].merge(flip_votes[k], on=k, how="left", indicator=True).query("_merge == 'left_only'")
check(missing.empty, f"{len(missing)} listed full-year funding or disaster aid votes were not found: "
                     + ", ".join(f"{r.congress}th {r.chamber} {r.rollnumber}" for r in missing.itertuples()))
check(funding_list["kind"].notna().all(), "flip_funding_votes.csv has rows without a kind")
for cat, grp in flip_votes.groupby("category"):
    check(grp["president_party"].nunique() == 2, f"{cat}: votes under only one party's president")
check(flip_member_votes["friendly"].isin([0, 1]).all(), "flip_member_votes has invalid 'friendly' values")
check(len(flip_member_votes) > 20000, f"flip_member_votes looks too small ({len(flip_member_votes):,} rows)")

# Chamber control: every chamber with Position Flips votes needs a majority party, or its votes can't be compared
# like for like. A tie needs an entry in MAJORITY_OVERRIDES in flip_utils.py.
sys.path.insert(0, str(ROOT))
from flip_utils import chamber_majority  # noqa: E402
majority = chamber_majority(members)
needed = flip_member_votes[["congress", "chamber"]].drop_duplicates().merge(majority, how="left")
for r in needed[needed["majority"].isna()].itertuples():
    check(False, f"{r.congress}th {r.chamber}: Democrats and Republicans tie on member count; add the majority "
                 "party to MAJORITY_OVERRIDES in flip_utils.py")

# President's stated positions: most statements classified, and enough linked to floor votes
positions = pd.read_csv(DATA / "president_positions.csv")
check(len(positions) >= 1000, f"only {len(positions)} White House statements (expected 1,000+)")
clear = positions["position"].isin(["Support", "Oppose"]).mean()
check(clear >= 0.9, f"only {clear:.0%} of White House statements have a clear position (expected 90%+)")
position_votes = pd.read_csv(DATA / "president_position_votes.csv")
check(len(position_votes) >= 500, f"only {len(position_votes)} floor votes linked to a White House statement")
# Independents who caucus with a party get scored
ind = members[~members["party"].isin(["Democrat", "Republican"]) & members["caucus"].notna()]
check(ind["party_unity_pct"].notna().all(), "an independent who caucuses with a party is missing a party unity rate")

# All Votes index: one row per roll call in the vote matrices, for every Congress and chamber
all_votes = pd.read_csv(DATA / "all_votes.csv")
n_matrix = 0
for f in (DATA / "matrices").glob("*.npz"):
    with np.load(f) as z:
        n_matrix += len(z["rollnumber"])
check(len(all_votes) == n_matrix, f"all_votes.csv has {len(all_votes):,} roll calls but the vote matrices have {n_matrix:,}")
check(not all_votes.duplicated(["congress", "chamber", "rollnumber"]).any(), "all_votes.csv has duplicate roll calls")

# Platform Votes: every hand-listed roll call exists, every topic has a valid plank for each party from the
# platform in force for its Congress, and each topic has at least one vote linked
topics = pd.read_csv(DATA / "platform_topics.csv", comment="#")
links = pd.read_csv(DATA / "platform_votes.csv", comment="#")
in_force = {115: 2016, 116: 2016, 117: 2020, 118: 2020, 119: 2024, 120: 2024}
for t in topics.itertuples():
    check(t.dem_platform == in_force.get(t.congress), f"platform topic {t.topic_id}: Democratic platform year is wrong")
    check(t.rep_platform == (2016 if in_force.get(t.congress) == 2020 else in_force.get(t.congress)),
          f"platform topic {t.topic_id}: Republican platform year is wrong")
    check({t.dem_stance, t.rep_stance} == {"Supports", "Opposes"}, f"platform topic {t.topic_id}: stances must be opposite")
    check((links["topic_id"] == t.topic_id).any(), f"platform topic {t.topic_id} has no linked vote")
check(not topics["topic_id"].duplicated().any(), "platform_topics.csv has a duplicate topic_id")
check(set(links["topic_id"]) <= set(topics["topic_id"]), "platform_votes.csv links to an unknown topic")
check(set(links["link"]) <= {"direct", "related"} and set(links["procedural"]) <= {"yes", "no"},
      "platform_votes.csv has an unknown link or procedural value")
check(((links["dem_platform_vote"].isin(["Yea", "Nay"])) & (links["rep_platform_vote"].isin(["Yea", "Nay"]))
       & (links["dem_platform_vote"] != links["rep_platform_vote"])).all(),
      "platform_votes.csv: each vote needs opposite Yea/Nay platform votes for the two parties")
found = links.merge(all_votes, on=["congress", "chamber", "rollnumber"], how="left", indicator=True)
for r in found[found["_merge"] != "both"].itertuples():
    check(False, f"platform vote {r.congress} {r.chamber} roll {r.rollnumber} is not in all_votes.csv")
# A flipped Yea/Nay in the hand list would show up as most of a party "voting against its platform"
for r in found[found["_merge"] == "both"].itertuples():
    dem_most = "Yea" if r.dem_yea > r.dem_nay else "Nay"
    rep_most = "Yea" if r.rep_yea > r.rep_nay else "Nay"
    check(dem_most == r.dem_platform_vote and rep_most == r.rep_platform_vote,
          f"platform vote {r.congress} {r.chamber} roll {r.rollnumber}: most of a party voted against the listed "
          "platform vote; check the Yea/Nay direction")
check(not links.duplicated(["congress", "chamber", "rollnumber"]).any(), "platform_votes.csv lists a roll call twice")
same = links.merge(topics[["topic_id", "congress"]], on="topic_id", suffixes=("", "_topic"))
check((same["congress"] == same["congress_topic"]).all(), "a platform vote is in a different Congress from its topic")

# No sudden shrinkage compared with the last committed data
for name, df in (("data/members_processed.csv", members), ("data/key_votes.csv", key_votes),
                 ("data/all_votes.csv", all_votes)):
    old = previous_version(name)
    if old is not None:
        check(len(df) >= 0.95 * len(old), f"{name} shrank from {len(old):,} to {len(df):,} rows")

if problems:
    print("Data check FAILED:")
    for p in problems:
        print(f"  - {p}")
    sys.exit(1)
print(f"Data check passed ({len(members):,} member rows, {len(key_votes):,} key votes, Congresses "
      f"{members['congress'].min()}–{latest}; key vote totals match official counts on {match:.1%}).")
