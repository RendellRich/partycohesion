"""Checks on the committed data files that the site reads."""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
LABELS = {"Consistent", "Partly changed", "Changed with the White House", "Opposite pattern", "Not enough votes"}


def test_files_present():
    for name in ["members_processed.csv", "unity_summary.csv", "key_votes.csv", "key_vote_defectors.csv",
                 "flip_votes.csv", "flip_member_votes.csv", "president_positions.csv", "president_position_votes.csv"]:
        assert (DATA / name).exists(), name
    assert list((DATA / "matrices").glob("*.npz"))


def test_unity_rates_in_range():
    m = pd.read_csv(DATA / "members_processed.csv")
    u = m["party_unity_pct"].dropna()
    assert len(u) > 1000 and u.between(0, 100).all()


def test_key_vote_party_counts_add_up():
    kv = pd.read_csv(DATA / "key_votes.csv")
    parts = kv["dem_yea"] + kv["rep_yea"] + kv["other_yea"]
    assert (parts == kv["yea_count"]).mean() > 0.95


def test_flip_votes_have_valid_friendly_vote():
    v = pd.read_csv(DATA / "flip_votes.csv")
    assert set(v["friendly_vote"]) <= {"Yea", "Nay"}
    mv = pd.read_csv(DATA / "flip_member_votes.csv")
    assert set(mv["friendly"]) <= {0, 1} and set(mv["own_president"]) <= {0, 1}
