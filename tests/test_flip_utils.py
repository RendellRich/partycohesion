"""The Position Flips math: labels at each cutoff, and scores computed from a small made-up set of votes."""
import math

import pandas as pd
import pytest

from flip_utils import MIN_VOTES_EACH_SIDE, flip_scores, shift_label


@pytest.mark.parametrize("shift, label", [
    (100, "Changed with the White House"), (50, "Changed with the White House"), (49, "Partly changed"),
    (25, "Partly changed"), (24, "Consistent"), (0, "Consistent"), (-24, "Consistent"),
    (-25, "Opposite pattern"), (-100, "Opposite pattern"),
])
def test_label_cutoffs(shift, label):
    assert shift_label(shift, 5, 5) == label


def test_needs_minimum_votes_each_side():
    assert shift_label(100, MIN_VOTES_EACH_SIDE - 1, 10) == "Not enough votes"
    assert shift_label(100, 10, MIN_VOTES_EACH_SIDE - 1) == "Not enough votes"


def votes(rows):
    return pd.DataFrame(rows, columns=["icpsr", "category", "own_president", "friendly"])


def test_scores_one_member():
    # Own party's president: 3 of 4 president-friendly (75%). Other party's: 1 of 4 (25%). Shift +50.
    mv = votes([(1, "Debt limit", 1, f) for f in (1, 1, 1, 0)] + [(1, "Debt limit", 0, f) for f in (1, 0, 0, 0)])
    r = flip_scores(mv).iloc[0]
    assert (r["n_own"], r["n_other"], r["friendly_own"], r["friendly_other"]) == (4, 4, 3, 1)
    assert r["rate_own"] == 75 and r["rate_other"] == 25 and r["shift"] == 50
    assert r["label"] == "Changed with the White House"


def test_category_filter_and_missing_side():
    mv = votes([(1, "Debt limit", 1, 1), (1, "Debt limit", 1, 1), (1, "Disaster aid", 0, 0), (1, "Disaster aid", 0, 0)])
    r = flip_scores(mv, "Debt limit").iloc[0]
    assert r["n_other"] == 0 and math.isnan(r["rate_other"]) and r["label"] == "Not enough votes"
    assert len(flip_scores(mv, "All categories")) == 1


def test_always_yes_or_always_no_is_consistent():
    always_no = votes([(2, "Stopgap funding", side, 0) for side in (1, 1, 0, 0)])
    always_yes = votes([(3, "Stopgap funding", side, 1) for side in (1, 1, 0, 0)])
    assert flip_scores(always_no).iloc[0]["label"] == "Consistent"
    assert flip_scores(always_yes).iloc[0]["label"] == "Consistent"
