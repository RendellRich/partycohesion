#!/usr/bin/env python3
"""
Refresh PartyCohesion data from Voteview.

Usage:
    python scripts/refresh_data.py

This script:
1. Downloads the latest HSall_members.csv from Voteview
2. Downloads the House and Senate vote and roll-call files for each Congress from the 110th to the newest
3. Computes a transparent cohesion proxy (distance from party median, DW-NOMINATE Dim 1)
4. Computes classic party-unity rates for every member in every Congress
5. Builds the key vote series (funding, cabinet confirmations, biggest party breaks,
   plus any votes listed in data/key_votes_custom.csv)
6. Writes members_processed.csv, unity_summary.csv, key_votes.csv and key_vote_defectors.csv

Run from the project root. Raw downloads are cached in data/raw/ (not committed).
"""

from pathlib import Path
import sys
import urllib.error
import urllib.request
import pandas as pd
import numpy as np

from house_vote_labels import apply_labels, fetch_missing

# Paths
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
MEMBERS_RAW = RAW_DIR / "HSall_members.csv"
PROCESSED_FILE = DATA_DIR / "members_processed.csv"
SUMMARY_FILE = DATA_DIR / "unity_summary.csv"

BASE_URL = "https://voteview.com/static/data/out"
MEMBERS_URL = f"{BASE_URL}/members/HSall_members.csv"
# Which party each independent caucuses with (unitedstates/congress-legislators, CC0)
LEGISLATORS_URLS = {
    "legislators-current.json": "https://unitedstates.github.io/congress-legislators/legislators-current.json",
    "legislators-historical.json": "https://unitedstates.github.io/congress-legislators/legislators-historical.json",
}

FIRST_CONGRESS = 110
# Set at runtime from the member file: FIRST_CONGRESS through the newest Congress with vote data.
CONGRESSES = range(FIRST_CONGRESS, 120)
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
    """Download the member file, then vote and roll-call files for every Congress from
    FIRST_CONGRESS to the newest one Voteview has. A brand-new Congress whose vote files are
    not published yet is skipped until they are."""
    global CONGRESSES
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print("Downloading Voteview files…")
    download(MEMBERS_URL, MEMBERS_RAW, force)
    for name, url in LEGISLATORS_URLS.items():
        download(url, RAW_DIR / name, force)
    latest = int(pd.read_csv(MEMBERS_RAW, usecols=["congress"])["congress"].max())
    available = []
    for cong in range(FIRST_CONGRESS, latest + 1):
        try:
            for prefix in CHAMBERS.values():
                for kind in ("votes", "rollcalls"):
                    name = f"{prefix}{cong}_{kind}.csv"
                    # Only the newest two Congresses change; older ones are reused from cache.
                    download(f"{BASE_URL}/{kind}/{name}", RAW_DIR / name, force=force and cong >= latest - 1)
            available.append(cong)
        except urllib.error.HTTPError as e:
            if cong < latest:
                raise
            print(f"  {cong}th Congress vote files not available yet ({e.code}); skipping it for now")
    CONGRESSES = range(FIRST_CONGRESS, max(available) + 1)
    print(f"Congresses included: {FIRST_CONGRESS}–{max(available)}")


def caucus_periods() -> dict:
    """bioguide -> list of (start, end, caucus party) from congress-legislators. A member's caucus is
    their party if Democrat/Republican, otherwise the party they caucus with (None if neither)."""
    import json
    people = []
    for name in LEGISLATORS_URLS:
        path = RAW_DIR / name
        if path.exists():
            people += json.loads(path.read_text(encoding="utf-8"))
    periods = {}
    for person in people:
        bio = person.get("id", {}).get("bioguide")
        for term in person.get("terms", []):
            affiliations = term.get("party_affiliations") or [
                {"start": term["start"], "end": term["end"], "party": term.get("party"), "caucus": term.get("caucus")}]
            for a in affiliations:
                party = a.get("party")
                if party in ("Democrat", "Republican"):
                    continue  # only independent periods are needed; D/R members are scored with their own party
                caucus = a.get("caucus") if "party_affiliations" in term else term.get("caucus")
                periods.setdefault(bio, []).append((a["start"], a.get("end", term["end"]), caucus))
    return periods


def congress_dates(cong: int):
    first_year = 1789 + 2 * (cong - 1)
    return f"{first_year}-01-03", f"{first_year + 2}-01-03"


def add_caucus(members: pd.DataFrame) -> pd.DataFrame:
    """Add a 'caucus' column: the party a member is scored with. Same as party for Democrats and
    Republicans; for independents, the party they caucus with during that Congress (if any)."""
    periods = caucus_periods()

    def lookup(row):
        if row["party"] in ("Democrat", "Republican"):
            return row["party"]
        start, end = congress_dates(row["congress"])
        # Independent periods overlapping this Congress, latest first; None if they caucus with neither party
        found = sorted((s, c) for s, e, c in periods.get(row["bioguide_id"], []) if s < end and e > start)
        return found[-1][1] if found else None

    members["caucus"] = members.apply(lookup, axis=1)
    return members


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
    return add_caucus(recent[cols].dropna(subset=["nominate_dim1"]).copy())


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
                        ["icpsr", "party", "caucus"]].drop_duplicates("icpsr")
    votes = votes.merge(party, on="icpsr", how="left")
    # Party majorities come from Democrats and Republicans only; independents are then scored
    # against the majority of the party they caucus with.
    dr = votes[votes["party"].isin(["Democrat", "Republican"])]
    scored = votes[votes["caucus"].isin(["Democrat", "Republican"])].drop(columns="party").rename(columns={"caucus": "party"})

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
    on_unity = scored.merge(long, on=["rollnumber", "party"], how="inner")
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
            last = pd.read_csv(RAW_DIR / f"{CHAMBERS[chamber]}{cong}_rollcalls.csv", usecols=["date"])["date"].max()
            summary.append({"congress": cong, "chamber": chamber, "party_unity_votes": n_rolls, "latest_vote_date": last})
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
ALL_VOTES_FILE = DATA_DIR / "all_votes.csv"  # every roll call with party splits, for the All Votes search page


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
    vote_frames, defector_frames, all_frames = [], [], []
    for cong in CONGRESSES:
        for chamber, prefix in CHAMBERS.items():
            rc = pd.read_csv(RAW_DIR / f"{prefix}{cong}_rollcalls.csv")
            if chamber == "House":  # Voteview leaves most House amendment votes without a description
                rc = apply_labels(rc.assign(congress=cong, chamber=chamber))
            splits, defectors = vote_splits(cong, chamber, members)
            rc = rc.merge(splits, on="rollnumber", how="inner")
            all_frames.append(rc.assign(congress=cong, chamber=chamber))
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
    all_votes = pd.concat(all_frames, ignore_index=True)[[c for c in cols if c not in ("series", "note")]]
    all_votes.sort_values(["congress", "chamber", "rollnumber"]).to_csv(ALL_VOTES_FILE, index=False)
    print(f"Wrote {ALL_VOTES_FILE.name} ({len(all_votes):,} roll calls)")
    key_defectors.to_csv(DEFECTORS_FILE, index=False)
    print(f"Wrote {KEY_VOTES_FILE.name} ({len(key_votes):,} rows) and {DEFECTORS_FILE.name} ({len(key_defectors):,} rows)")
    print(key_votes.groupby(["congress", "series"]).size().unstack(fill_value=0))


# ---------------------------------------------------------------------------
# Compact vote matrices (used by the Compare Members page)
# ---------------------------------------------------------------------------
MATRIX_DIR = DATA_DIR / "matrices"


def build_vote_matrices(members: pd.DataFrame) -> None:
    """One small file per Congress + chamber: rows = members, columns = roll calls,
    values 1 = Yea, -1 = Nay, 0 = did not vote. Lets the app compare any two members
    on every vote without shipping the full Voteview files."""
    MATRIX_DIR.mkdir(parents=True, exist_ok=True)
    wanted = {f"{p}{c}.npz" for c in CONGRESSES for p in CHAMBERS.values()}
    for old in MATRIX_DIR.glob("*.npz"):
        if old.name not in wanted:
            old.unlink()
    for cong in CONGRESSES:
        for chamber, prefix in CHAMBERS.items():
            ids = members.loc[(members["congress"] == cong) & (members["chamber"] == chamber), "icpsr"].unique()
            votes = pd.read_csv(RAW_DIR / f"{prefix}{cong}_votes.csv", usecols=["rollnumber", "icpsr", "cast_code"])
            votes = votes[votes["icpsr"].isin(ids)]
            votes["v"] = np.select([votes["cast_code"].isin(YEA_CODES), votes["cast_code"].isin(NAY_CODES)], [1, -1], 0)
            mat = votes.pivot_table(index="icpsr", columns="rollnumber", values="v", aggfunc="first", fill_value=0)
            arrays = {
                "icpsr": mat.index.to_numpy(dtype=np.int32),
                "rollnumber": mat.columns.to_numpy(dtype=np.int32),
                "votes": mat.to_numpy(dtype=np.int8),
            }
            path = MATRIX_DIR / f"{prefix}{cong}.npz"
            # .npz files embed a timestamp, so only rewrite when the votes actually changed;
            # otherwise every scheduled refresh would commit an identical-looking change.
            if path.exists():
                with np.load(path) as old:
                    if all(k in old and np.array_equal(old[k], v) for k, v in arrays.items()):
                        continue
            np.savez_compressed(path, **arrays)
    size = sum(f.stat().st_size for f in MATRIX_DIR.glob("*.npz"))
    print(f"Wrote vote matrices to {MATRIX_DIR.name}/ ({size / 1e6:.1f} MB)")


# ---------------------------------------------------------------------------
# Position flips: recurring votes under presidents of both parties
# ---------------------------------------------------------------------------
# For each category, the "president-friendly" vote is the one that gives whoever is president
# money, borrowing room, or a free hand. A member's flip score compares how often they cast that
# vote when their own party held the White House versus when the other party did.

PRESIDENTS = [  # (first day in office, name, party)
    ("2001-01-20", "Bush", "Republican"),
    ("2009-01-20", "Obama", "Democrat"),
    ("2017-01-20", "Trump", "Republican"),
    ("2021-01-20", "Biden", "Democrat"),
    ("2025-01-20", "Trump", "Republican"),
]

# "On the Motion" is left out on purpose: in Senate records it can be a concurrence, a waiver, or an
# unrelated deal riding in a stopgap bill's shell (e.g. the Dec. 2013 Ryan-Murray budget agreement).
FLIP_FINAL_RE = (r"^On (?:Passage|Motion to Suspend the Rules and Pass|Motion to Concur|Agreeing to the Conference Report|"
                 r"the Conference Report|the Joint Resolution|the Motion to Concur|Passage of the Bill)")
PASSED_RE = r"Passed|Agreed to|Concurred"
STOPGAP_RE = (r"continuing appropriations (?:and (?:other )?extensions )?for (?:the )?fiscal year|further continuing appropriations|"
              r"Continuing Appropriations (?:and Extensions )?Act")
# One-agency "mini" stopgaps (e.g. 2013 bills funding only parks or NIH) are not government-wide funding
# Full-year continuing resolutions fund the government for the rest of the year, so they are listed as full-year
# funding (data/flip_funding_votes.csv), not counted as stopgaps
STOPGAP_EXCLUDE_RE = (r"Providing for|Relating to consideration|disposition|disapproval|Full-Year Continuing|"
                      r"continuing appropriations (?:of|for) (?!(?:the )?fiscal year)")
WAR_POWERS_RE = r"(?:remove|removal of) (?:all |the )?(?:United States )?Armed Forces|War Powers Resolution"
WAR_POWERS_QUESTION_RE = (r"^On (?:Passage|Agreeing to the Resolution|the Joint Resolution|the Concurrent Resolution|"
                          r"Agreeing to the Concurrent Resolution|Motion to Suspend the Rules and Pass)")

DEBT_LIST = DATA_DIR / "flip_debt_limit_votes.csv"
FUNDING_LIST = DATA_DIR / "flip_funding_votes.csv"  # full-year funding and disaster aid, listed by written rule
POSITIONS_FILE = DATA_DIR / "president_positions.csv"
POSITION_VOTES_FILE = DATA_DIR / "president_position_votes.csv"
POSITION_WINDOW_DAYS = 30  # a statement covers final votes on its bill within this many days (or until the next statement)
FLIP_VOTES_FILE = DATA_DIR / "flip_votes.csv"
FLIP_MEMBER_VOTES_FILE = DATA_DIR / "flip_member_votes.csv"


def president_on(date: str):
    name, party = None, None
    for start, n, p in PRESIDENTS:
        if date >= start:
            name, party = n, p
    return name, party


def link_president_positions() -> pd.DataFrame:
    """Link each Statement of Administration Policy to the final floor votes on its bill: same Congress,
    same chamber (when the statement names one), on or after the statement date, within
    POSITION_WINDOW_DAYS, and before any later statement on the same bill."""
    if not POSITIONS_FILE.exists():
        print("  president_positions.csv not found; run scripts/build_president_positions.py")
        return pd.DataFrame()
    st_ = pd.read_csv(POSITIONS_FILE)
    st_ = st_[st_["position"].isin(["Support", "Oppose"])].copy()
    st_["bill_list"] = st_["bills"].str.split(";")
    st_ = st_.explode("bill_list")
    rows = []
    for cong in CONGRESSES:
        for chamber, prefix in CHAMBERS.items():
            rc = pd.read_csv(RAW_DIR / f"{prefix}{cong}_rollcalls.csv")
            rc = rc[rc["vote_question"].fillna("").str.contains(FLIP_FINAL_RE, regex=True)]
            rc = rc.assign(bill=rc["bill_number"].fillna("").str.upper())
            sc = st_[(st_["congress"] == cong) & (st_["chamber"].isna() | (st_["chamber"] == chamber))]
            for _, s in sc.iterrows():
                end = str((pd.Timestamp(s["date"]) + pd.Timedelta(days=POSITION_WINDOW_DAYS)).date())
                later = sc[(sc["bill_list"] == s["bill_list"]) & (sc["date"] > s["date"])]["date"]
                if len(later):
                    end = min(end, later.min())
                hit = rc[(rc["bill"] == s["bill_list"]) & (rc["date"] >= s["date"]) & (rc["date"] <= end)]
                for _, r in hit.iterrows():
                    rows.append({"congress": cong, "chamber": chamber, "rollnumber": r["rollnumber"], "vote_date": r["date"],
                                 "president": s["president"], "president_party": s["president_party"],
                                 "president_position": s["position"], "president_vote": "Yea" if s["position"] == "Support" else "Nay",
                                 "statement_date": s["date"], "statement_title": s["title"], "statement_url": s["statement_url"]})
    linked = pd.DataFrame(rows).drop_duplicates(["congress", "chamber", "rollnumber"], keep="last")
    linked.to_csv(POSITION_VOTES_FILE, index=False)
    print(f"Linked president's stated position to {len(linked)} floor votes ({POSITION_VOTES_FILE.name})")
    return linked


def build_flip_data(members: pd.DataFrame, positions: pd.DataFrame) -> None:
    debt = pd.read_csv(DEBT_LIST, comment="#")
    funding = pd.read_csv(FUNDING_LIST, comment="#")
    vote_rows, member_rows = [], []
    for cong in CONGRESSES:
        for chamber, prefix in CHAMBERS.items():
            rc = pd.read_csv(RAW_DIR / f"{prefix}{cong}_rollcalls.csv")
            q, d = rc["vote_question"].fillna(""), rc["vote_desc"].fillna("")
            picks = []
            # Only stopgaps that passed the chamber: when rival versions fail (e.g. Sept. 2025 in the Senate),
            # a vote for one and against the other reflects the bills' contents, not a position on funding.
            stop = (q.str.contains(FLIP_FINAL_RE, regex=True) & d.str.contains(STOPGAP_RE, case=False, regex=True)
                    & ~d.str.contains(STOPGAP_EXCLUDE_RE, case=False, regex=True)
                    & rc["vote_result"].fillna("").str.contains(PASSED_RE, regex=True))
            picks.append(rc[stop].assign(category="Stopgap funding", friendly_vote="Yea", selection="rule", note=""))
            war = (q.str.contains(WAR_POWERS_QUESTION_RE, regex=True) & d.str.contains(WAR_POWERS_RE, case=False, regex=True)
                   & ~d.str.contains(r"Providing for consideration|Consideration of", case=False, regex=True))
            picks.append(rc[war].assign(category="War powers limits", friendly_vote="Nay", selection="rule", note=""))
            # Full-year funding and disaster aid are listed by hand (see the rules in data/flip_funding_votes.csv),
            # because these laws usually pass as vehicle bills whose titles have nothing to do with funding.
            fund = funding[(funding["congress"] == cong) & (funding["chamber"] == chamber)]
            if not fund.empty:
                picks.append(rc.merge(fund[["rollnumber", "category", "note"]], on="rollnumber")
                             .assign(friendly_vote="Yea", selection="listed"))
                full_year_cr = fund.loc[fund["kind"] == "full-year CR", "rollnumber"]
                picks[0] = picks[0][~picks[0]["rollnumber"].isin(full_year_cr)]  # not also a stopgap
            listed = debt[(debt["congress"] == cong) & (debt["chamber"] == chamber)]
            if not listed.empty:
                picks.append(rc.merge(listed[["rollnumber", "friendly_vote", "note"]], on="rollnumber")
                             .assign(category="Debt limit", selection="listed"))
            chosen = pd.concat(picks, ignore_index=True)
            if chosen.empty:
                continue
            chosen[["president", "president_party"]] = chosen["date"].apply(lambda x: pd.Series(president_on(x)))
            # Where the White House issued a statement, use the president's actual position instead of the
            # default assumption (e.g. Obama opposed the Sept. 2013 House stopgap that defunded the ACA).
            # The hand-listed debt limit votes keep their listed direction.
            chosen = chosen.merge(positions[(positions["congress"] == cong) & (positions["chamber"] == chamber)]
                                  [["rollnumber", "president_position", "president_vote", "statement_title"]],
                                  on="rollnumber", how="left") if not positions.empty else chosen.assign(
                                  president_position=None, president_vote=None, statement_title=None)
            use = chosen["president_vote"].notna() & (chosen["category"] != "Debt limit")
            chosen["position_source"] = np.where(use, "president's statement",
                                                 np.where(chosen["selection"] == "listed", "listed", "default rule"))
            chosen.loc[use, "friendly_vote"] = chosen.loc[use, "president_vote"]
            vote_rows.append(chosen)

            votes = pd.read_csv(RAW_DIR / f"{prefix}{cong}_votes.csv", usecols=["rollnumber", "icpsr", "cast_code"])
            votes = votes[votes["rollnumber"].isin(chosen["rollnumber"]) & votes["cast_code"].isin(YEA_CODES | NAY_CODES)]
            # Independents are scored with the party they caucus with
            party = (members.loc[(members["congress"] == cong) & (members["chamber"] == chamber), ["icpsr", "caucus"]]
                     .drop_duplicates("icpsr").rename(columns={"caucus": "party"}))
            votes = votes.merge(party, on="icpsr", how="inner")
            votes = votes[votes["party"].isin(["Democrat", "Republican"])]
            mv = votes.merge(chosen[["rollnumber", "category", "friendly_vote", "president_party"]], on="rollnumber")
            mv["vote"] = np.where(mv["cast_code"].isin(YEA_CODES), "Yea", "Nay")
            mv["friendly"] = (mv["vote"] == mv["friendly_vote"]).astype(int)
            mv["own_president"] = (mv["party"] == mv["president_party"]).astype(int)
            member_rows.append(mv.assign(congress=cong, chamber=chamber)[
                ["icpsr", "congress", "chamber", "rollnumber", "category", "party", "vote", "friendly", "own_president"]])

    cols = ["category", "congress", "chamber", "rollnumber", "date", "president", "president_party", "bill_number",
            "vote_question", "vote_desc", "vote_result", "yea_count", "nay_count", "friendly_vote", "selection", "note",
            "position_source", "president_position", "statement_title"]
    flip_votes = pd.concat(vote_rows, ignore_index=True)[cols].sort_values(["category", "date", "chamber", "rollnumber"])
    flip_member_votes = pd.concat(member_rows, ignore_index=True).sort_values(["icpsr", "category", "congress", "rollnumber"])
    flip_votes.to_csv(FLIP_VOTES_FILE, index=False)
    flip_member_votes.to_csv(FLIP_MEMBER_VOTES_FILE, index=False)
    print(f"Wrote {FLIP_VOTES_FILE.name} ({len(flip_votes)} votes) and {FLIP_MEMBER_VOTES_FILE.name} ({len(flip_member_votes):,} member votes)")
    print(flip_votes.groupby(["category", "president_party"]).size().unstack(fill_value=0))


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

    print("\nBuilding vote matrices…")
    build_vote_matrices(members)

    print("\nLinking the president's stated positions…")
    positions = link_president_positions()

    print("\nBuilding position flip data…")
    build_flip_data(members, positions)


def main() -> None:
    try:
        download_raw()
        try:
            fetch_missing()
        except Exception as e:  # the Clerk's site being down shouldn't stop the refresh
            print(f"Skipped House Clerk records this time: {e}")
        process()
        print("\nRefresh complete. Commit the updated files in data/ and the app will pick them up.")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
