"""Same State, Different Vote: how often each state's two senators cast opposite votes on the same roll call, and
which votes those were. Built from the Senate vote matrices in data/matrices/ and the roll-call list in
data/all_votes.csv. Only Yea and Nay count; a senator who did not vote is left out of that roll call.

A state's two senators share the same voters, so a split means they read the same question differently. Senators
from different parties split on most party-line votes as a matter of course; the telling splits are between two
senators of the same party, and the votes where one of them broke with their own party."""

from __future__ import annotations

from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
VOTE_WORD = {1: "Yea", -1: "Nay"}


def side(row: pd.Series) -> str:
    """The party a senator votes with: their own, or the one an Independent caucuses with."""
    if row["party"] in ("Democrat", "Republican"):
        return row["party"]
    return row["caucus"] if isinstance(row.get("caucus"), str) and row["caucus"] else row["party"]


def find_splits(members: pd.DataFrame, rollcalls: pd.DataFrame, matrices: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Every pair of senators from the same state who served in the same Congress, with how many roll calls both
    voted on and how many they split; and one row per split vote.

    members: members_processed rows (congress, chamber, icpsr, bioguide_id, name, state_abbrev, party, caucus).
    rollcalls: all_votes rows for the Senate (congress, rollnumber, dem_position, rep_position, ...).
    matrices: {congress: (icpsr array, rollnumber array, votes matrix of 1 Yea, -1 Nay, 0 not voting)}."""
    pairs, splits = [], []
    sen = members[members["chamber"] == "Senate"]
    for congress, (icpsr, rolls, votes) in sorted(matrices.items()):
        row_of = {int(i): k for k, i in enumerate(icpsr)}
        meta = rollcalls[rollcalls["congress"] == congress].set_index("rollnumber")
        for state, group in sen[sen["congress"] == congress].groupby("state_abbrev"):
            people = group.drop_duplicates("icpsr").sort_values("name").to_dict("records")
            for a, b in combinations(people, 2):
                if int(a["icpsr"]) not in row_of or int(b["icpsr"]) not in row_of:
                    continue
                va, vb = votes[row_of[int(a["icpsr"])]], votes[row_of[int(b["icpsr"])]]
                both = (va != 0) & (vb != 0)
                split = both & (va != vb)
                n_both, n_split = int(both.sum()), int(split.sum())
                if n_both == 0:  # a senator and their replacement never served at the same time
                    continue
                side_a, side_b = side(a), side(b)
                pairs.append({"congress": congress, "state": state, "icpsr_a": a["icpsr"], "icpsr_b": b["icpsr"],
                              "name_a": a["name"], "name_b": b["name"], "party_a": a["party"], "party_b": b["party"],
                              "bioguide_a": a.get("bioguide_id"), "bioguide_b": b.get("bioguide_id"),
                              "same_side": side_a == side_b, "both_voted": n_both, "splits": n_split,
                              "split_pct": 100 * n_split / n_both})
                for k in np.flatnonzero(split):
                    roll = int(rolls[k])
                    m = meta.loc[roll] if roll in meta.index else None
                    broke = []
                    for who, s, v in (("a", side_a, va[k]), ("b", side_b, vb[k])):
                        pos = None if m is None else m.get("dem_position" if s == "Democrat" else "rep_position")
                        if isinstance(pos, str) and pos in ("Yea", "Nay") and VOTE_WORD[int(v)] != pos:
                            broke.append(who)
                    splits.append({"congress": congress, "state": state, "rollnumber": roll,
                                   "icpsr_a": a["icpsr"], "icpsr_b": b["icpsr"],
                                   "vote_a": VOTE_WORD[int(va[k])], "vote_b": VOTE_WORD[int(vb[k])],
                                   "broke_a": "a" in broke, "broke_b": "b" in broke})
    return pd.DataFrame(pairs), pd.DataFrame(splits)


def load(data_dir: Path = DATA_DIR) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Pairs, splits and the Senate roll-call list, from the files in data/."""
    members = pd.read_csv(data_dir / "members_processed.csv")
    rollcalls = pd.read_csv(data_dir / "all_votes.csv")
    rollcalls = rollcalls[rollcalls["chamber"] == "Senate"]
    matrices = {}
    for path in sorted((data_dir / "matrices").glob("S*.npz")):
        with np.load(path) as f:
            matrices[int(path.stem[1:])] = (f["icpsr"], f["rollnumber"], f["votes"])
    pairs, splits = find_splits(members, rollcalls, matrices)
    return pairs, splits, rollcalls
