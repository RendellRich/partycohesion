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

# No sudden shrinkage compared with the last committed data
for name, df in (("data/members_processed.csv", members), ("data/key_votes.csv", key_votes)):
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
