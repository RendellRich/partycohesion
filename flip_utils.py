"""Position flip scoring shared by every page that shows Position Flips and by the data checks.

For each member, compare how often they cast the "president-friendly" vote (Yea on debt limit increases and
government funding, Nay on war powers limits) when their own party held the White House versus when the other
party did.

The comparison is like for like. Votes are put in groups by the type of vote and by whether the member's party ran
their chamber at the time, because the party running a chamber writes these bills and moves votes about as much
as the president does. Inside each group the member's president-friendly rate under the other party's president is
subtracted from their rate under their own party's president. The shift is the average of those differences,
weighted so that groups with more votes on both sides count more (weight = own x other / (own + other)). Groups
with votes on only one side can't be compared and are left out of the shift.

The simple difference (all votes under their own party's president minus all votes under the other party's, with
no grouping) is kept as raw_shift so pages can show both.
"""

import numpy as np
import pandas as pd

MIN_VOTES_EACH_SIDE = 2

# Chambers where counting each party's members (including those who caucus with it) gives a tie, so the
# majority is set from the record. 110th Senate: Democrats organized the chamber with independents Sanders and
# Lieberman. 117th Senate: 50-50, with Vice President Harris breaking ties for the Democrats.
MAJORITY_OVERRIDES = {(110, "Senate"): "Democrat", (117, "Senate"): "Democrat"}


def shift_label(shift: float, own_n: int, other_n: int) -> str:
    if own_n < MIN_VOTES_EACH_SIDE or other_n < MIN_VOTES_EACH_SIDE or pd.isna(shift):
        return "Not enough votes"
    if shift >= 50:
        return "Changed with the White House"
    if shift >= 25:
        return "Partly changed"
    if shift > -25:
        return "Consistent"
    return "Opposite pattern"


def chamber_majority(members: pd.DataFrame) -> pd.DataFrame:
    """Majority party of each chamber in each Congress, from members' caucus counts plus MAJORITY_OVERRIDES.
    A chamber that ties without an override gets no majority (its votes then can't be grouped)."""
    counts = members.groupby(["congress", "chamber"])["caucus"].value_counts().unstack(fill_value=0)
    for party in ("Democrat", "Republican"):
        if party not in counts:
            counts[party] = 0
    majority = np.where(counts["Democrat"] > counts["Republican"], "Democrat",
                        np.where(counts["Republican"] > counts["Democrat"], "Republican", None))
    out = pd.DataFrame({"majority": majority}, index=counts.index).reset_index()
    for (congress, chamber), party in MAJORITY_OVERRIDES.items():
        out.loc[(out["congress"] == congress) & (out["chamber"] == chamber), "majority"] = party
    return out


def add_chamber_control(member_votes: pd.DataFrame, members: pd.DataFrame) -> pd.DataFrame:
    """Adds own_chamber: 1 if the member's party (or the party they caucus with) ran their chamber, else 0."""
    mv = member_votes.merge(chamber_majority(members), on=["congress", "chamber"], how="left")
    mv["own_chamber"] = np.where(mv["majority"].isna(), np.nan, (mv["party"] == mv["majority"]).astype(float))
    return mv.drop(columns="majority")


def comparison_groups(member_votes: pd.DataFrame) -> pd.DataFrame:
    """One row per member, type of vote and chamber-control situation, with votes and president-friendly votes
    under each side, the difference, and the weight. compared = both sides have votes."""
    mv = member_votes.dropna(subset=["own_chamber"])
    g = mv.groupby(["icpsr", "category", "own_chamber", "own_president"])["friendly"].agg(n="size", friendly="sum")
    g = g.unstack("own_president", fill_value=0)
    g.columns = [f"{a}_{'own' if b == 1 else 'other'}" for a, b in g.columns]
    for col in ("n_own", "n_other", "friendly_own", "friendly_other"):
        if col not in g:
            g[col] = 0
    g = g.reset_index()
    g["compared"] = (g["n_own"] > 0) & (g["n_other"] > 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        g["rate_own"] = np.where(g["n_own"] > 0, 100 * g["friendly_own"] / g["n_own"], np.nan)
        g["rate_other"] = np.where(g["n_other"] > 0, 100 * g["friendly_other"] / g["n_other"], np.nan)
        g["difference"] = g["rate_own"] - g["rate_other"]
        g["weight"] = np.where(g["compared"], g["n_own"] * g["n_other"] / (g["n_own"] + g["n_other"]), 0.0)
    return g


def flip_scores(member_votes: pd.DataFrame, category: str | None = None) -> pd.DataFrame:
    """One row per member.

    n_own, n_other, friendly_own, friendly_other, rate_own, rate_other and raw_shift describe all their votes with
    no grouping. shift and label use only like-for-like groups (see the module docstring); matched_own and
    matched_other count the votes in those groups. Needs an own_chamber column (add_chamber_control); without it,
    shift falls back to the simple difference.
    """
    mv = member_votes if category in (None, "All categories") else member_votes[member_votes["category"] == category]
    g = mv.groupby(["icpsr", "own_president"])["friendly"].agg(n="size", friendly="sum").unstack(fill_value=0)
    g.columns = [f"{a}_{'own' if b == 1 else 'other'}" for a, b in g.columns]
    for col in ("n_own", "n_other", "friendly_own", "friendly_other"):
        if col not in g:
            g[col] = 0
    g = g.reset_index()
    with np.errstate(invalid="ignore", divide="ignore"):
        g["rate_own"] = np.where(g["n_own"] > 0, 100 * g["friendly_own"] / g["n_own"], np.nan)
        g["rate_other"] = np.where(g["n_other"] > 0, 100 * g["friendly_other"] / g["n_other"], np.nan)
    g["raw_shift"] = (g["rate_own"] - g["rate_other"]).round(0)

    if "own_chamber" in mv.columns:
        used = comparison_groups(mv)
        used = used[used["compared"]]
        if len(used):
            agg = (used.assign(wd=used["difference"] * used["weight"]).groupby("icpsr")
                   .agg(wd=("wd", "sum"), w=("weight", "sum"), matched_own=("n_own", "sum"),
                        matched_other=("n_other", "sum")).reset_index())
            agg["shift"] = agg["wd"] / agg["w"]
            g = g.merge(agg[["icpsr", "shift", "matched_own", "matched_other"]], on="icpsr", how="left")
        else:
            g = g.assign(shift=np.nan, matched_own=0, matched_other=0)
        g[["matched_own", "matched_other"]] = g[["matched_own", "matched_other"]].fillna(0).astype(int)
        g["shift"] = g["shift"].round(0)
    else:
        g["shift"] = g["raw_shift"]
        g["matched_own"], g["matched_other"] = g["n_own"], g["n_other"]
    g["label"] = [shift_label(s, a, b) for s, a, b in zip(g["shift"], g["matched_own"], g["matched_other"])]
    return g
