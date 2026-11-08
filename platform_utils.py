"""Platform Votes: how members voted on roll calls where the two parties' platforms take opposite positions.

The topics, planks and linked roll calls are written down by hand in data/platform_topics.csv and
data/platform_votes.csv, each under the published rules in docs/platform-comparison-design.md. This module only
joins them to how each member voted (the vote matrices) and counts who voted against their own party's platform.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from vote_index import VOTE_WORD, load_matrix, load_votes

DATA_DIR = Path(__file__).parent / "data"
PLATFORM_YEAR = {110: 2004, 111: 2008, 112: 2008, 113: 2012, 114: 2012, 115: 2016, 116: 2016, 117: 2020, 118: 2020, 119: 2024, 120: 2024}


def platform_year(congress: int, party: str) -> int:
    """The platform in force for a Congress: the one adopted in the presidential election year before it. The
    Republican Party re-adopted its 2016 platform in 2020, so its 2016 text applies to the 117th and 118th."""
    year = PLATFORM_YEAR[int(congress)]
    return 2016 if party == "Republican" and year == 2020 else year


@st.cache_data
def load_platform() -> tuple[pd.DataFrame, pd.DataFrame]:
    topics = pd.read_csv(DATA_DIR / "platform_topics.csv", comment="#")
    links = pd.read_csv(DATA_DIR / "platform_votes.csv", comment="#")
    links["note"] = links["note"].fillna("")
    links["counts"] = (links["link"] == "direct") & (links["procedural"] == "no")
    votes = load_votes()
    keep = ["congress", "chamber", "rollnumber", "date", "vote_question", "vote_result", "yea_count", "nay_count",
            "dem_yea", "dem_nay", "rep_yea", "rep_nay", "other_yea", "other_nay"]
    links = links.merge(votes[keep], on=["congress", "chamber", "rollnumber"], how="left")
    return topics, links


def member_platform_votes(links: pd.DataFrame, members: pd.DataFrame) -> pd.DataFrame:
    """One row per member per linked roll call they voted Yea or Nay on, with their party's platform vote and
    whether they voted against it. Independents are compared with the party they caucus with."""
    out = []
    for (congress, chamber), group in links.groupby(["congress", "chamber"]):
        mat = load_matrix(int(congress), chamber)
        if mat is None:
            continue
        ids, rolls, matrix = mat
        who = members[(members["congress"] == congress) & (members["chamber"] == chamber)][
            ["icpsr", "name", "party", "caucus", "state_abbrev"]].drop_duplicates("icpsr")
        who = who.assign(side=who["caucus"].where(who["caucus"].isin(["Democrat", "Republican"]), who["party"]))
        who = who[who["side"].isin(["Democrat", "Republican"])]
        for link in group.itertuples():
            col = np.where(rolls == int(link.rollnumber))[0]
            if not len(col):
                continue
            cast = pd.DataFrame({"icpsr": ids, "vote": pd.Series(matrix[:, col[0]]).map(VOTE_WORD)})
            cast = cast[cast["vote"].isin(["Yea", "Nay"])].merge(who, on="icpsr")
            cast["platform_vote"] = np.where(cast["side"] == "Democrat", link.dem_platform_vote, link.rep_platform_vote)
            cast["against"] = cast["vote"] != cast["platform_vote"]
            for k in ("topic_id", "congress", "chamber", "rollnumber", "counts", "link", "procedural"):
                cast[k] = getattr(link, k)
            out.append(cast)
    cols = ["icpsr", "name", "party", "side", "state_abbrev", "vote", "platform_vote", "against", "topic_id",
            "congress", "chamber", "rollnumber", "counts", "link", "procedural"]
    return pd.concat(out, ignore_index=True)[cols] if out else pd.DataFrame(columns=cols)


def member_topics(mv: pd.DataFrame) -> pd.DataFrame:
    """One row per member per topic, over the counted votes. A member counts once per topic, as against their
    platform if they voted against it on any counted vote on that topic, so a topic with several nearly identical
    votes weighs the same as a topic with one."""
    counted = mv[mv["counts"]]
    cols = ["icpsr", "topic_id", "name", "side", "state_abbrev", "votes", "votes_against", "against"]
    if counted.empty:
        return pd.DataFrame(columns=cols)
    g = counted.groupby(["icpsr", "topic_id"], sort=False).agg(
        name=("name", "last"), side=("side", "last"), state_abbrev=("state_abbrev", "last"),
        votes=("against", "size"), votes_against=("against", "sum")).reset_index()
    g["against"] = g["votes_against"] > 0
    return g[cols]


def party_totals(mv: pd.DataFrame) -> pd.DataFrame:
    """For each party, over the counted votes: topics voted on and against the platform (each member once per
    topic), the counted votes behind them, and how many members voted against it at least once."""
    mt = member_topics(mv)
    rows = []
    for side in ("Democrat", "Republican"):
        p = mt[mt["side"] == side]
        rows.append({"party": side, "topics_cast": len(p), "topics_against": int(p["against"].sum()),
                     "votes_cast": int(p["votes"].sum()), "votes_against": int(p["votes_against"].sum()),
                     "members": p["icpsr"].nunique(), "members_against": p.loc[p["against"], "icpsr"].nunique()})
    t = pd.DataFrame(rows)
    t["against_pct"] = (100 * t["topics_against"] / t["topics_cast"].where(t["topics_cast"] > 0)).round(1)
    return t


def member_summary(mv: pd.DataFrame) -> pd.DataFrame:
    """Per member, over the counted votes: how many topics they voted on and how many they voted against their
    party's platform on (each topic once)."""
    mt = member_topics(mv)
    if mt.empty:
        return pd.DataFrame(columns=["icpsr", "name", "side", "state_abbrev", "cast", "against"])
    g = mt.groupby("icpsr").agg(name=("name", "last"), side=("side", "last"), state_abbrev=("state_abbrev", "last"),
                                cast=("against", "size"), against=("against", "sum")).reset_index()
    return g.sort_values(["against", "cast"], ascending=[False, False])


@st.cache_data
def all_member_platform_votes() -> pd.DataFrame:
    """Every member's Yea/Nay votes on the linked roll calls, with the topic and measure names, for the member pages."""
    members = pd.read_csv(DATA_DIR / "members_processed.csv")
    topics, links = load_platform()
    mv = member_platform_votes(links, members)
    mv = mv.merge(links[["congress", "chamber", "rollnumber", "measure", "date"]],
                  on=["congress", "chamber", "rollnumber"])
    return mv.merge(topics[["topic_id", "topic"]], on="topic_id").sort_values(["date", "rollnumber"])


def platform_record(icpsr: int) -> tuple[pd.DataFrame, int, int]:
    """One member's platform votes, plus how many topics they cast a counted vote on and how many of those topics
    they voted against their platform on (each topic once)."""
    mv = all_member_platform_votes()
    mine = mv[mv["icpsr"] == icpsr]
    mt = member_topics(mine)
    return mine, len(mt), int(mt["against"].sum())


@st.cache_data
def platform_roll_calls() -> pd.DataFrame:
    """One row per roll call used on Platform Votes, with its topic and whether it counts, for the All Votes page."""
    topics, links = load_platform()
    out = links.merge(topics[["topic_id", "topic"]], on="topic_id")
    out["status"] = out.apply(lambda r: "Counted" if r["counts"] else (
        "Shown, procedural" if r["procedural"] == "yes" else "Shown, related measure"), axis=1)
    return out[["congress", "chamber", "rollnumber", "topic", "status", "measure", "dem_platform_vote",
                "rep_platform_vote"]]
