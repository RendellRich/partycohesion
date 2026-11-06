"""Position flip scoring shared by the Position Flips page and the data checks.

For each member and category, compare how often they cast the "president-friendly" vote
(Yea on debt limit increases and stopgap funding, Nay on war powers limits) when their own
party held the White House versus when the other party did.
"""

import numpy as np
import pandas as pd

MIN_VOTES_EACH_SIDE = 2


def shift_label(shift: float, own_n: int, other_n: int) -> str:
    if own_n < MIN_VOTES_EACH_SIDE or other_n < MIN_VOTES_EACH_SIDE:
        return "Not enough votes"
    if shift >= 50:
        return "Changed with the White House"
    if shift >= 25:
        return "Partly changed"
    if shift > -25:
        return "Consistent"
    return "Opposite pattern"


def flip_scores(member_votes: pd.DataFrame, category: str | None = None) -> pd.DataFrame:
    """One row per member: votes and president-friendly rates under each party's president."""
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
    g["shift"] = (g["rate_own"] - g["rate_other"]).round(0)
    g["label"] = [shift_label(s, a, b) for s, a, b in zip(g["shift"], g["n_own"], g["n_other"])]
    return g
