#!/usr/bin/env python3
"""
Refresh PartyCohesion data from Voteview.

Usage:
    python scripts/refresh_data.py

This script:
1. Downloads the latest HSall_members.csv from Voteview
2. Processes Congresses 110–119 (House + Senate)
3. Computes a transparent cohesion proxy
4. Writes data/members_processed.csv

Run from the project root.
"""

from pathlib import Path
import sys
import urllib.request
import pandas as pd
import numpy as np

# Paths
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_FILE = DATA_DIR / "HSall_members.csv"
PROCESSED_FILE = DATA_DIR / "members_processed.csv"

VOTEVIEW_URL = "https://voteview.com/static/data/out/members/HSall_members.csv"

PARTY_MAP = {
    100: "Democrat",
    200: "Republican",
    328: "Independent",
    329: "Independent Democrat",
    331: "Independent Republican",
}


def download_raw():
    print(f"Downloading Voteview member file from:\n  {VOTEVIEW_URL}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(VOTEVIEW_URL, RAW_FILE)
    print(f"Saved raw file → {RAW_FILE}")


def process():
    print("Processing members…")
    df = pd.read_csv(RAW_FILE)

    # Keep recent Congresses
    recent = df[df["congress"].between(110, 119)].copy()
    recent = recent[recent["chamber"].isin(["House", "Senate"])]

    recent["party"] = recent["party_code"].map(PARTY_MAP).fillna("Other")
    recent["name"] = recent["bioname"].str.title()

    cols = [
        "congress", "chamber", "icpsr", "bioguide_id", "name", "state_abbrev",
        "party", "nominate_dim1", "nominate_dim2",
        "nominate_number_of_votes", "nokken_poole_dim1",
    ]
    members = recent[cols].dropna(subset=["nominate_dim1"]).copy()

    # Cohesion proxy: within each Congress + chamber + party,
    # rank members by absolute distance from the party median on Dim 1.
    # 100 = closest to median, lower = further toward the wing.
    members["dist_from_party_median"] = np.nan
    members["cohesion_proxy"] = np.nan

    for cong in members["congress"].unique():
        for cham in ["House", "Senate"]:
            mask = (members["congress"] == cong) & (members["chamber"] == cham)
            for party in ["Democrat", "Republican"]:
                pmask = mask & (members["party"] == party)
                n = pmask.sum()
                if n <= 5:
                    continue
                vals = members.loc[pmask, "nominate_dim1"]
                median = vals.median()
                dist = (vals - median).abs()
                members.loc[pmask, "dist_from_party_median"] = dist
                # Rank: smaller distance → better (higher) cohesion score
                rank = dist.rank(method="average", ascending=True)
                score = 100 * (1 - (rank - 1) / max(n - 1, 1))
                members.loc[pmask, "cohesion_proxy"] = score.round(1)

    members["cohesion_proxy"] = members["cohesion_proxy"].fillna(50.0)

    members.to_csv(PROCESSED_FILE, index=False)
    print(f"Wrote processed file → {PROCESSED_FILE}")
    print(f"Shape: {members.shape}")
    print(f"Congress range: {members['congress'].min()} – {members['congress'].max()}")
    print("\nCounts by recent Congress / chamber:")
    print(members.groupby(["congress", "chamber"]).size().tail(8))


def main():
    try:
        download_raw()
        process()
        print("\nRefresh complete. Restart or rerun the Streamlit app to see updated data.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
