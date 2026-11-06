"""Every roll call since 2007, and how each member voted on it, for the All Votes page and member voting records.

data/all_votes.csv has one row per roll call with each party's Yea/Nay split and majority position (built by
scripts/refresh_data.py). How each member voted comes from the compact vote matrices in data/matrices/.
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).parent / "data"
PREFIX = {"House": "H", "Senate": "S"}
VOTE_WORD = {1: "Yea", -1: "Nay", 0: "Did not vote"}


@st.cache_data
def load_votes() -> pd.DataFrame:
    v = pd.read_csv(DATA_DIR / "all_votes.csv")
    v["label"] = v["vote_desc"].fillna(v["bill_number"].fillna("") + " " + v["vote_question"].fillna("")).str.strip()
    v["search"] = (v["bill_number"].fillna("") + " " + v["vote_desc"].fillna("") + " " + v["vote_question"].fillna("")).str.lower()
    v["broke_ranks"] = (v["dem_defectors"] + v["rep_defectors"]).astype(int)
    return v


@st.cache_data
def load_matrix(congress: int, chamber: str):
    path = DATA_DIR / "matrices" / f"{PREFIX[chamber]}{congress}.npz"
    if not path.exists():
        return None
    with np.load(path) as f:
        return f["icpsr"], f["rollnumber"], f["votes"]


def voteview_url(congress: int, chamber: str, rollnumber: int) -> str:
    return f"https://voteview.com/rollcall/R{PREFIX[chamber]}{int(congress):03d}{int(rollnumber):04d}"


BILL_RE = re.compile(r"^\s*(h\.?\s*con\.?\s*res|s\.?\s*con\.?\s*res|h\.?\s*j\.?\s*res|s\.?\s*j\.?\s*res|"
                     r"h\.?\s*res|s\.?\s*res|h\.?\s*r|s)\.?\s*(\d+)\s*$", re.IGNORECASE)


def bill_code(text: str) -> str | None:
    """'H.R. 1' -> 'HR1', 's 5' -> 'S5', 'H.J.Res. 31' -> 'HJRES31'; None if text isn't a bill number."""
    m = BILL_RE.match(text or "")
    if not m:
        return None
    return re.sub(r"[^a-z]", "", m.group(1).lower()).upper() + m.group(2)


def search_votes(votes: pd.DataFrame, text: str = "", congress=None, chamber: str = "Both",
                 party_line: bool = False, broke_ranks: bool = False) -> pd.DataFrame:
    """Filter the roll calls. A bill number (e.g. "H.R. 1" or "S. 5") matches that bill exactly, in both chambers;
    otherwise every word in text must appear in the bill number, description or question."""
    v = votes
    if congress is not None:
        v = v[v["congress"] == congress]
    if chamber != "Both":
        v = v[v["chamber"] == chamber]
    if party_line:
        v = v[v["party_unity_vote"]]
    if broke_ranks:
        v = v[v["broke_ranks"] > 0]
    code = bill_code(text)
    if code:
        return v[v["bill_number"].fillna("").str.upper() == code].sort_values(["date", "rollnumber"], ascending=False)
    for word in text.lower().replace(".", "").split():
        v = v[v["search"].str.replace(".", "", regex=False).str.contains(word, regex=False)]
    return v.sort_values(["date", "rollnumber"], ascending=False)


def members_who_broke_ranks(vote: pd.Series, members: pd.DataFrame) -> pd.DataFrame:
    """Democrats and Republicans who voted against their own party's majority on one roll call."""
    mat = load_matrix(int(vote["congress"]), vote["chamber"])
    if mat is None:
        return pd.DataFrame(columns=["icpsr", "name", "party", "state_abbrev", "vote"])
    icpsr, rolls, votes = mat
    col = np.where(rolls == int(vote["rollnumber"]))[0]
    if not len(col):
        return pd.DataFrame(columns=["icpsr", "name", "party", "state_abbrev", "vote"])
    cast = pd.DataFrame({"icpsr": icpsr, "v": votes[:, col[0]]})
    who = members[(members["congress"] == vote["congress"]) & (members["chamber"] == vote["chamber"])][
        ["icpsr", "name", "party", "state_abbrev"]].drop_duplicates("icpsr")
    cast = cast.merge(who, on="icpsr")
    position = {"Democrat": vote["dem_position"], "Republican": vote["rep_position"]}
    cast["position"] = cast["party"].map(position)
    cast["vote"] = cast["v"].map(VOTE_WORD)
    broke = cast[cast["position"].isin(["Yea", "Nay"]) & cast["vote"].isin(["Yea", "Nay"])
                 & (cast["vote"] != cast["position"])]
    return broke.sort_values(["party", "name"])[["icpsr", "name", "party", "state_abbrev", "vote"]]


def member_record(icpsr: int, member_rows: pd.DataFrame, votes: pd.DataFrame) -> pd.DataFrame:
    """Every roll call a member was eligible for, with their vote, their party's majority position, and whether
    they voted against it. Independents are compared with the party they caucus with."""
    out = []
    for r in member_rows[["congress", "chamber", "party", "caucus"]].drop_duplicates(["congress", "chamber"]).itertuples():
        mat = load_matrix(int(r.congress), r.chamber)
        if mat is None:
            continue
        ids, rolls, matrix = mat
        row = np.where(ids == icpsr)[0]
        if not len(row):
            continue
        mine = pd.DataFrame({"rollnumber": rolls, "v": matrix[row[0]]})
        vv = votes[(votes["congress"] == r.congress) & (votes["chamber"] == r.chamber)].merge(mine, on="rollnumber")
        side = r.caucus if pd.notna(r.caucus) else r.party
        vv["party_position"] = vv["dem_position"] if side == "Democrat" else (
            vv["rep_position"] if side == "Republican" else "None")
        vv["their_vote"] = vv["v"].map(VOTE_WORD)
        out.append(vv)
    if not out:
        return pd.DataFrame()
    rec = pd.concat(out, ignore_index=True)
    voted = rec["their_vote"].isin(["Yea", "Nay"])
    took_side = rec["party_position"].isin(["Yea", "Nay"])
    rec["against_party"] = voted & took_side & (rec["their_vote"] != rec["party_position"])
    rec["with_party"] = voted & took_side & (rec["their_vote"] == rec["party_position"])
    return rec.sort_values(["date", "rollnumber"], ascending=False)
