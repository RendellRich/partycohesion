"""The Position Flips math: labels at each cutoff, and scores computed from a small made-up set of votes."""
import math

import pandas as pd
import pytest

from flip_utils import MIN_VOTES_EACH_SIDE, chamber_majority, comparison_groups, flip_scores, shift_label


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


# --- Like-for-like matching (type of vote x whether the member's party ran the chamber) ---------------------------

def votes_cc(rows):
    """icpsr, category, own_chamber, own_president, friendly"""
    return pd.DataFrame(rows, columns=["icpsr", "category", "own_chamber", "own_president", "friendly"])


def test_chamber_control_is_not_counted_as_a_change():
    # Own party's president: always in the majority, always president-friendly.
    # Other party's president: half the votes in the majority (friendly), half in the minority (not friendly).
    # Simple difference says +50, but in the majority group the member voted the same way under both presidents.
    mv = votes_cc([(1, "Stopgap funding", 1, 1, 1)] * 4 + [(1, "Stopgap funding", 1, 0, 1)] * 2
                  + [(1, "Stopgap funding", 0, 0, 0)] * 2)
    r = flip_scores(mv).iloc[0]
    assert r["raw_shift"] == 50
    assert r["shift"] == 0 and r["label"] == "Consistent"
    assert (r["matched_own"], r["matched_other"]) == (4, 2)  # the minority group has no own-president votes


def test_weighted_average_across_groups():
    # Debt limit group: 2 v 2 votes, difference +100, weight 1.0
    # Stopgap group: 6 v 3 votes, difference 0, weight 2.0 -> shift = 100 * 1 / 3 = 33
    mv = votes_cc([(1, "Debt limit", 0, 1, 1)] * 2 + [(1, "Debt limit", 0, 0, 0)] * 2
                  + [(1, "Stopgap funding", 0, 1, 1)] * 6 + [(1, "Stopgap funding", 0, 0, 1)] * 3)
    g = comparison_groups(mv).set_index("category")
    assert g.loc["Debt limit", "weight"] == 1.0 and g.loc["Stopgap funding", "weight"] == 2.0
    r = flip_scores(mv).iloc[0]
    assert r["shift"] == 33 and r["label"] == "Partly changed"


def test_needs_matched_votes_for_a_label():
    # Plenty of votes, but none in a shared situation, so nothing can be compared
    mv = votes_cc([(1, "Debt limit", 1, 1, 1)] * 5 + [(1, "Debt limit", 0, 0, 0)] * 5)
    r = flip_scores(mv).iloc[0]
    assert r["label"] == "Not enough votes" and r["matched_own"] == 0


def test_chamber_majority_counts_and_overrides():
    members = pd.DataFrame({
        "congress": [118] * 3 + [117] * 4, "chamber": ["Senate"] * 7,
        "caucus": ["Democrat", "Democrat", "Republican", "Democrat", "Democrat", "Republican", "Republican"]})
    m = chamber_majority(members).set_index("congress")["majority"]
    assert m[118] == "Democrat"
    assert m[117] == "Democrat"  # tie broken by MAJORITY_OVERRIDES (Vice President Harris)
