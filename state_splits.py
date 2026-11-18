"""Same State, Different Vote: how often two members of Congress from the same state cast opposite votes on the same
roll call, and which votes those were. Built from the vote matrices in data/matrices/ and the roll-call list in
data/all_votes.csv. Only Yea and Nay count; a member who did not vote is left out of that roll call.

Senate: each state's senators, whatever their parties. Senators from different parties split on most party-line
votes as a matter of course; the telling splits are between two senators of the same party.
House: every pair of members from the same state and the same party (a large state has hundreds), because
members of different parties from one state split on most votes and that says little."""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
PREFIX = {"House": "H", "Senate": "S"}
VOTE_WORD = {1: "Yea", -1: "Nay"}
# A pair needs this many roll calls in common to be ranked: a member who served a few weeks alongside another can
# otherwise top the list on a handful of votes.
MIN_SHARED = {"Senate": 50, "House": 100}


def side(row) -> str:
    """The party a member votes with: their own, or the one an Independent caucuses with."""
    if row["party"] in ("Democrat", "Republican"):
        return row["party"]
    caucus = row.get("caucus")
    return caucus if isinstance(caucus, str) and caucus else row["party"]


def find_pairs(members: pd.DataFrame, matrices: dict, chamber: str = "Senate") -> pd.DataFrame:
    """Every pair of members from the same state who served in the same Congress and chamber (in the House, only
    pairs from the same party), with how many roll calls both voted on and how many they split.

    members: members_processed rows (congress, chamber, icpsr, bioguide_id, name, state_abbrev, party, caucus).
    matrices: {congress: (icpsr array, rollnumber array, votes matrix of 1 Yea, -1 Nay, 0 not voting)}."""
    pairs = []
    people_all = members[members["chamber"] == chamber]
    for congress, (icpsr, _rolls, votes) in sorted(matrices.items()):
        row_of = {int(i): k for k, i in enumerate(icpsr)}
        for state, group in people_all[people_all["congress"] == congress].groupby("state_abbrev"):
            people = [p for p in group.drop_duplicates("icpsr").sort_values("name").to_dict("records")
                      if int(p["icpsr"]) in row_of]
            for p in people:
                p["side"] = side(p)
            for a, b in combinations(people, 2):
                if chamber == "House" and a["side"] != b["side"]:
                    continue
                va, vb = votes[row_of[int(a["icpsr"])]], votes[row_of[int(b["icpsr"])]]
                both = (va != 0) & (vb != 0)
                n_both = int(both.sum())
                if n_both == 0:  # a member and their replacement never served at the same time
                    continue
                n_split = int((both & (va != vb)).sum())
                pairs.append({"congress": congress, "chamber": chamber, "state": state,
                              "icpsr_a": a["icpsr"], "icpsr_b": b["icpsr"], "name_a": a["name"], "name_b": b["name"],
                              "party_a": a["party"], "party_b": b["party"],
                              "district_a": a.get("district_code"), "district_b": b.get("district_code"),
                              "bioguide_a": a.get("bioguide_id"), "bioguide_b": b.get("bioguide_id"),
                              "same_side": a["side"] == b["side"], "side": a["side"] if a["side"] == b["side"] else None,
                              "both_voted": n_both, "splits": n_split, "split_pct": 100 * n_split / n_both})
    return pd.DataFrame(pairs)


def pair_votes(pair, members: pd.DataFrame, rollcalls: pd.DataFrame, matrices: dict) -> pd.DataFrame:
    """The roll calls where one pair split: each member's vote and whether they voted against the majority of the
    party they vote with. pair is a row of find_pairs()."""
    icpsr, rolls, votes = matrices[int(pair["congress"])]
    row_of = {int(i): k for k, i in enumerate(icpsr)}
    va, vb = votes[row_of[int(pair["icpsr_a"])]], votes[row_of[int(pair["icpsr_b"])]]
    idx = np.flatnonzero((va != 0) & (vb != 0) & (va != vb))
    who = members[(members["congress"] == pair["congress"]) & (members["chamber"] == pair["chamber"])]
    who = who.drop_duplicates("icpsr").set_index("icpsr")
    side_a, side_b = side(who.loc[pair["icpsr_a"]]), side(who.loc[pair["icpsr_b"]])
    meta = rollcalls[(rollcalls["congress"] == pair["congress"]) & (rollcalls["chamber"] == pair["chamber"])]
    out = pd.DataFrame({"rollnumber": rolls[idx].astype(int), "vote_a": [VOTE_WORD[int(v)] for v in va[idx]],
                        "vote_b": [VOTE_WORD[int(v)] for v in vb[idx]]})
    out = out.merge(meta, on="rollnumber", how="left")

    def broke(s, col):
        pos = out["dem_position" if s == "Democrat" else "rep_position"]
        return pos.isin(["Yea", "Nay"]) & (out[col] != pos)
    out["broke_a"], out["broke_b"] = broke(side_a, "vote_a"), broke(side_b, "vote_b")
    return out


def load_inputs(data_dir: Path = DATA_DIR):
    """members_processed, all_votes and every vote matrix, keyed by chamber then Congress."""
    members = pd.read_csv(data_dir / "members_processed.csv")
    if "district_code" not in members.columns:
        members["district_code"] = None
    rollcalls = pd.read_csv(data_dir / "all_votes.csv")
    matrices = {"House": {}, "Senate": {}}
    for chamber, prefix in PREFIX.items():
        for path in sorted((data_dir / "matrices").glob(f"{prefix}*.npz")):
            with np.load(path) as f:
                matrices[chamber][int(path.stem[1:])] = (f["icpsr"], f["rollnumber"], f["votes"])
    return members, rollcalls, matrices


def member_summary(pairs: pd.DataFrame, chamber: str = "House") -> pd.DataFrame:
    """One row per member per Congress: how often they split, on average, with the same-party colleagues from their
    state they share enough votes with (MIN_SHARED), their most split colleague, and where they rank in that
    delegation (1 = splits most). Built from find_pairs() rows."""
    p = pairs[(pairs["chamber"] == chamber) & pairs["same_side"] & (pairs["both_voted"] >= MIN_SHARED[chamber])]
    a = p.rename(columns={"icpsr_a": "icpsr", "name_a": "name", "party_a": "party", "bioguide_a": "bioguide_id",
                          "icpsr_b": "other_icpsr", "name_b": "other_name", "bioguide_b": "other_bioguide"})
    b = p.rename(columns={"icpsr_b": "icpsr", "name_b": "name", "party_b": "party", "bioguide_b": "bioguide_id",
                          "icpsr_a": "other_icpsr", "name_a": "other_name", "bioguide_a": "other_bioguide"})
    cols = ["congress", "state", "side", "icpsr", "name", "party", "bioguide_id", "other_icpsr", "other_name",
            "other_bioguide", "both_voted", "splits", "split_pct"]
    long = pd.concat([a[cols], b[cols]], ignore_index=True)
    if long.empty:
        return pd.DataFrame(columns=["congress", "state", "side", "icpsr", "name", "party", "bioguide_id",
                                     "colleagues", "avg_split", "most_split_with", "most_split_pct", "rank",
                                     "delegation"])
    top = long.sort_values("split_pct", ascending=False).drop_duplicates(["congress", "icpsr"])
    out = (long.groupby(["congress", "state", "side", "icpsr", "name", "party", "bioguide_id"], dropna=False)
           .agg(colleagues=("other_icpsr", "nunique"), avg_split=("split_pct", "mean")).reset_index())
    out = out.merge(top[["congress", "icpsr", "other_name", "split_pct"]].rename(
        columns={"other_name": "most_split_with", "split_pct": "most_split_pct"}), on=["congress", "icpsr"])
    grp = out.groupby(["congress", "state", "side"])["avg_split"]
    out["rank"] = grp.rank(ascending=False, method="min").astype(int)
    out["delegation"] = grp.transform("size")
    return out.sort_values(["congress", "avg_split"], ascending=[True, False]).reset_index(drop=True)


_cached_all = None


def load_all():
    """Members, roll calls, vote matrices and every same-state pair in both chambers, cached for the server's life
    (cleared when the data files change). Shared by the Same State, Different Vote and Members pages."""
    global _cached_all
    if _cached_all is None:
        import streamlit as st

        @st.cache_data(show_spinner="Comparing members from the same state...")
        def _load():
            members, rollcalls, matrices = load_inputs()
            pairs = pd.concat([find_pairs(members, matrices[c], c) for c in ("Senate", "House")], ignore_index=True)
            pairs["key"] = pairs["icpsr_a"].astype(int).astype(str) + "-" + pairs["icpsr_b"].astype(int).astype(str)
            return members, rollcalls, matrices, pairs
        _cached_all = _load
    return _cached_all()
