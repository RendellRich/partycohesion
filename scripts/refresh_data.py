#!/usr/bin/env python3
"""
Refresh PartyCohesion data from Voteview.

Usage:
    python scripts/refresh_data.py

This script:
1. Downloads the latest HSall_members.csv from Voteview
2. Downloads the House and Senate vote files for each Congress in range
3. Computes a transparent cohesion proxy (distance from party median, DW-NOMINATE Dim 1)
4. Computes classic party-unity rates for every member in every Congress
5. Writes data/members_processed.csv and data/unity_summary.csv

Run from the project root. Raw downloads are cached in data/raw/ (not committed).
"""

from pathlib import Path
import sys
import urllib.request
import pandas as pd
import numpy as np

# Paths
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
MEMBERS_RAW = RAW_DIR / "HSall_members.csv"
PROCESSED_FILE = DATA_DIR / "members_processed.csv"
SUMMARY_FILE = DATA_DIR / "unity_summary.csv"

BASE_URL = "https://voteview.com/static/data/out"
MEMBERS_URL = f"{BASE_URL}/members/HSall_members.csv"

CONGRESSES = range(110, 120)  # 110th through 119th
CHAMBERS = {"House": "H", "Senate": "S"}

PARTY_MAP = {
    100: "Democrat",
    200: "Republican",
    328: "Independent",
    329: "Independent Democrat",
    331: "Independent Republican",
}

# Voteview cast codes: 1-3 = Yea, 4-6 = Nay, 7-9 = present / not voting, 0 = not a member
YEA_CODES = {1, 2, 3}
NAY_CODES = {4, 5, 6}


def download(url: str, dest: Path, force: bool = True) -> None:
    if dest.exists() and not force:
        return
    print(f"  downloading {url}")
    urllib.request.urlretrieve(url, dest)


def download_raw(force: bool = True) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print("Downloading Voteview files…")
    download(MEMBERS_URL, MEMBERS_RAW, force)
    for cong in CONGRESSES:
        for prefix in CHAMBERS.values():
            name = f"{prefix}{cong}_votes.csv"
            # Only the current Congress changes; older ones can be reused from cache.
            download(f"{BASE_URL}/votes/{name}", RAW_DIR / name, force=force and cong == max(CONGRESSES))


def load_members() -> pd.DataFrame:
    df = pd.read_csv(MEMBERS_RAW)
    recent = df[df["congress"].isin(CONGRESSES) & df["chamber"].isin(CHAMBERS)].copy()
    recent["party"] = recent["party_code"].map(PARTY_MAP).fillna("Other")
    recent["name"] = recent["bioname"].str.title()
    cols = [
        "congress", "chamber", "icpsr", "bioguide_id", "name", "state_abbrev",
        "party", "nominate_dim1", "nominate_dim2",
        "nominate_number_of_votes", "nokken_poole_dim1",
    ]
    return recent[cols].dropna(subset=["nominate_dim1"]).copy()


def add_cohesion_proxy(members: pd.DataFrame) -> pd.DataFrame:
    """Within each Congress + chamber + party, rank members by absolute distance
    from the party median on Dim 1. 100 = closest to median, lower = further toward the wing."""
    members["dist_from_party_median"] = np.nan
    members["cohesion_proxy"] = np.nan
    for (cong, cham, party), grp in members.groupby(["congress", "chamber", "party"]):
        if party not in ("Democrat", "Republican") or len(grp) <= 5:
            continue
        dist = (grp["nominate_dim1"] - grp["nominate_dim1"].median()).abs()
        rank = dist.rank(method="average", ascending=True)
        n = len(grp)
        members.loc[grp.index, "dist_from_party_median"] = dist.round(3)
        members.loc[grp.index, "cohesion_proxy"] = (100 * (1 - (rank - 1) / max(n - 1, 1))).round(1)
    return members


def party_unity_for(cong: int, chamber: str, members: pd.DataFrame):
    """Return (per-member unity table, number of party-unity votes) for one Congress + chamber.

    A party-unity vote is a roll call where a majority of voting Democrats opposed a
    majority of voting Republicans. A member's unity rate is the share of those votes,
    among the ones they cast Yea or Nay, where they sided with their own party's majority.
    """
    votes = pd.read_csv(RAW_DIR / f"{CHAMBERS[chamber]}{cong}_votes.csv",
                        usecols=["rollnumber", "icpsr", "cast_code"])
    votes = votes[votes["cast_code"].isin(YEA_CODES | NAY_CODES)].copy()
    votes["yea"] = votes["cast_code"].isin(YEA_CODES)

    party = members.loc[(members["congress"] == cong) & (members["chamber"] == chamber),
                        ["icpsr", "party"]].drop_duplicates("icpsr")
    votes = votes.merge(party, on="icpsr", how="left")
    dr = votes[votes["party"].isin(["Democrat", "Republican"])]

    # Majority position of each party on each roll call (ties excluded)
    share = dr.groupby(["rollnumber", "party"])["yea"].mean().unstack()
    share = share.dropna()
    dem_pos = np.where(share["Democrat"] > 0.5, True, np.where(share["Democrat"] < 0.5, False, np.nan))
    rep_pos = np.where(share["Republican"] > 0.5, True, np.where(share["Republican"] < 0.5, False, np.nan))
    pos = pd.DataFrame({"Democrat": dem_pos, "Republican": rep_pos}, index=share.index)
    pos = pos.dropna()
    unity_rolls = pos[pos["Democrat"] != pos["Republican"]]

    if unity_rolls.empty:
        return pd.DataFrame(columns=["icpsr", "unity_votes_cast", "votes_with_party", "party_unity_pct"]), 0

    long = unity_rolls.stack().rename("party_yea").reset_index().rename(columns={"level_1": "party"})
    on_unity = dr.merge(long, on=["rollnumber", "party"], how="inner")
    on_unity["with_party"] = on_unity["yea"] == on_unity["party_yea"].astype(bool)

    out = on_unity.groupby("icpsr").agg(
        unity_votes_cast=("with_party", "size"),
        votes_with_party=("with_party", "sum"),
    ).reset_index()
    out["party_unity_pct"] = (100 * out["votes_with_party"] / out["unity_votes_cast"]).round(1)
    return out, len(unity_rolls)


def add_party_unity(members: pd.DataFrame):
    frames, summary = [], []
    for cong in CONGRESSES:
        for chamber in CHAMBERS:
            unity, n_rolls = party_unity_for(cong, chamber, members)
            unity["congress"] = cong
            unity["chamber"] = chamber
            frames.append(unity)
            summary.append({"congress": cong, "chamber": chamber, "party_unity_votes": n_rolls})
    unity_all = pd.concat(frames, ignore_index=True)
    merged = members.merge(unity_all, on=["congress", "chamber", "icpsr"], how="left")
    merged["unity_votes_cast"] = merged["unity_votes_cast"].astype("Int64")
    merged["votes_with_party"] = merged["votes_with_party"].astype("Int64")
    return merged, pd.DataFrame(summary)


def process() -> None:
    print("Processing members…")
    members = load_members()
    members = add_cohesion_proxy(members)
    members, summary = add_party_unity(members)

    members.to_csv(PROCESSED_FILE, index=False)
    summary.to_csv(SUMMARY_FILE, index=False)
    print(f"Wrote {PROCESSED_FILE.name} ({len(members):,} rows) and {SUMMARY_FILE.name}")
    print("\nParty-unity votes identified:")
    print(summary.pivot(index="congress", columns="chamber", values="party_unity_votes"))


def main() -> None:
    try:
        download_raw()
        process()
        print("\nRefresh complete. Commit the updated files in data/ and the app will pick them up.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
