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
5. Builds the key vote series (funding, cabinet confirmations, biggest party breaks,
   plus any votes listed in data/key_votes_custom.csv)
6. Writes members_processed.csv, unity_summary.csv, key_votes.csv and key_vote_defectors.csv

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

# Voteview cast codes: 1 = Yea, 6 = Nay, 2-5 = paired or announced positions (not floor votes),
# 7-9 = present / not voting, 0 = not a member. Only actual floor votes are counted, which
# matches the official clerk totals.
YEA_CODES = {1}
NAY_CODES = {6}


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
    # Title-case names, then restore the capital in "Mc" surnames (MCCONNELL -> McConnell, not Mcconnell)
    recent["name"] = (recent["bioname"].str.title()
                      .str.replace(r"\bMc([a-z])", lambda m: "Mc" + m.group(1).upper(), regex=True))
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
    among the ones they actually voted Yea or Nay on, where they sided with their own party's majority.
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


# ---------------------------------------------------------------------------
# Key vote series
# ---------------------------------------------------------------------------
# Every series is chosen by a written rule (below) or listed by hand in
# data/key_votes_custom.csv, so anyone can see why a vote is included.

FUNDING_SERIES = "Funding & Appropriations"
CABINET_SERIES = "Cabinet Confirmations"
BREAKS_SERIES = "Biggest Party Breaks"
BREAKS_PER_CHAMBER = 10

# Final-passage style questions (procedural "rule" votes are excluded)
PASSAGE_RE = (r"^On (?:Passage|Motion to Suspend the Rules and Pass|Motion to Concur|"
              r"Agreeing to the Conference Report|the Conference Report|the Joint Resolution|the Motion to Concur)")
FUNDING_RE = r"\bappropriations\b"
FUNDING_EXCLUDE_RE = r"authoriz|^to amend"
CABINET_RE = (r"to be (?:the )?(?:Secretary of (?:State|the Treasury|Defense|the Interior|Agriculture|Commerce|Labor|"
              r"Health and Human Services|Housing and Urban Development|Transportation|Energy|Education|"
              r"Veterans Affairs|Homeland Security)|Attorney General(?: of the United States)?)\.?\s*$")

CUSTOM_FILE = DATA_DIR / "key_votes_custom.csv"
KEY_VOTES_FILE = DATA_DIR / "key_votes.csv"
DEFECTORS_FILE = DATA_DIR / "key_vote_defectors.csv"


def download_rollcalls(force: bool = True) -> None:
    for cong in CONGRESSES:
        for prefix in CHAMBERS.values():
            name = f"{prefix}{cong}_rollcalls.csv"
            download(f"{BASE_URL}/rollcalls/{name}", RAW_DIR / name, force=force and cong == max(CONGRESSES))


def vote_splits(cong: int, chamber: str, members: pd.DataFrame):
    """Per roll call: Yea/Nay counts by party, party majority positions, and the members who
    voted against their own party's majority (Democrats and Republicans only)."""
    votes = pd.read_csv(RAW_DIR / f"{CHAMBERS[chamber]}{cong}_votes.csv",
                        usecols=["rollnumber", "icpsr", "cast_code"])
    votes = votes[votes["cast_code"].isin(YEA_CODES | NAY_CODES)].copy()
    votes["yea"] = votes["cast_code"].isin(YEA_CODES)
    info = members.loc[(members["congress"] == cong) & (members["chamber"] == chamber),
                       ["icpsr", "name", "party", "state_abbrev"]].drop_duplicates("icpsr")
    # inner join drops anyone who is not a member of this chamber (e.g. a Vice President's tie-breaking vote)
    votes = votes.merge(info, on="icpsr", how="inner")
    votes["grp"] = votes["party"].where(votes["party"].isin(["Democrat", "Republican"]), "Other")

    counts = votes.groupby(["rollnumber", "grp"])["yea"].agg(yea="sum", total="size").reset_index()
    counts["nay"] = counts["total"] - counts["yea"]
    wide = counts.pivot(index="rollnumber", columns="grp", values=["yea", "nay"]).fillna(0).astype(int)
    abbr = {"Democrat": "dem", "Republican": "rep", "Other": "other"}
    wide.columns = [f"{abbr[g]}_{k}" for k, g in wide.columns]
    for col in ["dem_yea", "dem_nay", "rep_yea", "rep_nay", "other_yea", "other_nay"]:
        if col not in wide:
            wide[col] = 0

    def majority(y, n):
        return np.where(y > n, "Yea", np.where(n > y, "Nay", "Tie"))

    wide["dem_position"] = majority(wide["dem_yea"], wide["dem_nay"])
    wide["rep_position"] = majority(wide["rep_yea"], wide["rep_nay"])
    wide["party_unity_vote"] = (
        wide["dem_position"].isin(["Yea", "Nay"]) & wide["rep_position"].isin(["Yea", "Nay"])
        & (wide["dem_position"] != wide["rep_position"])
    )

    dr = votes[votes["grp"] != "Other"].copy()
    pos = wide[["dem_position", "rep_position"]].reset_index()
    dr = dr.merge(pos, on="rollnumber")
    dr["party_position"] = np.where(dr["grp"] == "Democrat", dr["dem_position"], dr["rep_position"])
    dr["vote"] = np.where(dr["yea"], "Yea", "Nay")
    defectors = dr[(dr["party_position"] != "Tie") & (dr["vote"] != dr["party_position"])]
    n_def = defectors.groupby(["rollnumber", "grp"]).size().unstack(fill_value=0)
    wide["dem_defectors"] = n_def.get("Democrat", pd.Series(dtype=int)).reindex(wide.index, fill_value=0)
    wide["rep_defectors"] = n_def.get("Republican", pd.Series(dtype=int)).reindex(wide.index, fill_value=0)
    defectors = defectors[["rollnumber", "icpsr", "name", "party", "state_abbrev", "vote", "party_position"]]
    return wide.reset_index(), defectors


def build_key_votes(members: pd.DataFrame) -> None:
    custom = pd.read_csv(CUSTOM_FILE, comment="#") if CUSTOM_FILE.exists() else pd.DataFrame()
    vote_frames, defector_frames = [], []
    for cong in CONGRESSES:
        for chamber, prefix in CHAMBERS.items():
            rc = pd.read_csv(RAW_DIR / f"{prefix}{cong}_rollcalls.csv")
            splits, defectors = vote_splits(cong, chamber, members)
            rc = rc.merge(splits, on="rollnumber", how="inner")
            q = rc["vote_question"].fillna("")
            d = rc["vote_desc"].fillna("")

            picks = []
            funding = (q.str.contains(PASSAGE_RE, regex=True)
                       & d.str.contains(FUNDING_RE, case=False, regex=True)
                       & ~d.str.contains(FUNDING_EXCLUDE_RE, case=False, regex=True))
            picks.append(rc[funding].assign(series=FUNDING_SERIES, note=""))
            if chamber == "Senate":
                cabinet = (q == "On the Nomination") & d.str.contains(CABINET_RE, case=False, regex=True)
                picks.append(rc[cabinet].assign(series=CABINET_SERIES, note=""))
            final = q.str.contains(PASSAGE_RE, regex=True) | (q == "On the Nomination")
            breaks = (rc[rc["party_unity_vote"] & final]
                      .assign(_n=lambda x: x["dem_defectors"] + x["rep_defectors"])
                      .sort_values(["_n", "date"], ascending=[False, False])
                      .head(BREAKS_PER_CHAMBER).drop(columns="_n"))
            picks.append(breaks.assign(series=BREAKS_SERIES, note=""))
            if not custom.empty:
                mine = custom[(custom["congress"] == cong) & (custom["chamber"] == chamber)]
                if not mine.empty:
                    picks.append(rc.merge(mine[["rollnumber", "series", "note"]], on="rollnumber"))

            chosen = pd.concat(picks, ignore_index=True)
            vote_frames.append(chosen)
            defector_frames.append(
                defectors[defectors["rollnumber"].isin(chosen["rollnumber"])].assign(congress=cong, chamber=chamber))

    cols = ["series", "congress", "chamber", "rollnumber", "date", "bill_number", "vote_question", "vote_desc",
            "vote_result", "yea_count", "nay_count", "dem_yea", "dem_nay", "rep_yea", "rep_nay", "other_yea",
            "other_nay", "dem_position", "rep_position", "party_unity_vote", "dem_defectors", "rep_defectors", "note"]
    key_votes = pd.concat(vote_frames, ignore_index=True)[cols].sort_values(["congress", "chamber", "series", "date", "rollnumber"])
    key_defectors = pd.concat(defector_frames, ignore_index=True)[
        ["congress", "chamber", "rollnumber", "icpsr", "name", "party", "state_abbrev", "vote", "party_position"]]
    key_votes.to_csv(KEY_VOTES_FILE, index=False)
    key_defectors.to_csv(DEFECTORS_FILE, index=False)
    print(f"Wrote {KEY_VOTES_FILE.name} ({len(key_votes):,} rows) and {DEFECTORS_FILE.name} ({len(key_defectors):,} rows)")
    print(key_votes.groupby(["congress", "series"]).size().unstack(fill_value=0))


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

    print("\nBuilding key vote series…")
    build_key_votes(members)


def main() -> None:
    try:
        download_raw()
        download_rollcalls()
        process()
        print("\nRefresh complete. Commit the updated files in data/ and the app will pick them up.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
