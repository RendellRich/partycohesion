"""Same State, Different Vote: pairs of senators from one state and the roll calls where they split."""
from pathlib import Path

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

from state_splits import find_pairs, pair_votes

ROOT = Path(__file__).resolve().parent.parent


def test_pairs_count_only_votes_both_cast_and_flag_who_broke_ranks():
    members = pd.DataFrame([
        {"congress": 119, "chamber": "Senate", "icpsr": 1, "bioguide_id": "A", "name": "Ash, Al", "state_abbrev": "KY",
         "party": "Republican", "caucus": None},
        {"congress": 119, "chamber": "Senate", "icpsr": 2, "bioguide_id": "B", "name": "Bay, Bo", "state_abbrev": "KY",
         "party": "Republican", "caucus": None},
        {"congress": 119, "chamber": "Senate", "icpsr": 3, "bioguide_id": "C", "name": "Cole, Cy", "state_abbrev": "ME",
         "party": "Independent", "caucus": "Democrat"},
        {"congress": 119, "chamber": "Senate", "icpsr": 4, "bioguide_id": "D", "name": "Dunn, Di", "state_abbrev": "ME",
         "party": "Republican", "caucus": None},
    ])
    rollcalls = pd.DataFrame({"congress": [119] * 4, "rollnumber": [1, 2, 3, 4],
                              "dem_position": ["Yea", "Nay", "Yea", "Yea"], "rep_position": ["Nay", "Nay", "Yea", "Nay"]})
    votes = np.array([[-1, -1, 1, 1],    # Ash
                      [-1, 1, 0, -1],    # Bay: breaks on roll 2, misses roll 3
                      [1, -1, 1, 1],     # Cole
                      [-1, -1, 1, -1]])  # Dunn
    mats = {119: (np.array([1, 2, 3, 4]), np.array([1, 2, 3, 4]), votes)}
    pairs = find_pairs(members, mats, "Senate")
    ky = pairs[pairs["state"] == "KY"].iloc[0]
    assert (ky["both_voted"], ky["splits"], bool(ky["same_side"])) == (3, 2, True)
    me = pairs[pairs["state"] == "ME"].iloc[0]
    assert bool(me["same_side"]) is False and me["splits"] == 2  # an Independent counts with their caucus
    rc = rollcalls.assign(chamber="Senate")
    split = pair_votes(ky, members, rc, mats).set_index("rollnumber")
    assert list(split.index) == [2, 4]
    assert (split.loc[2, "vote_a"], split.loc[2, "vote_b"], bool(split.loc[2, "broke_a"]),
            bool(split.loc[2, "broke_b"])) == ("Nay", "Yea", False, True)
    assert bool(split.loc[4, "broke_a"]) and not bool(split.loc[4, "broke_b"])


def test_house_pairs_are_same_party_only():
    members = pd.DataFrame([
        {"congress": 119, "chamber": "House", "icpsr": i, "bioguide_id": f"H{i}", "name": f"M{i}, X",
         "state_abbrev": "TX", "party": party, "caucus": None}
        for i, party in [(1, "Democrat"), (2, "Democrat"), (3, "Republican")]])
    votes = np.array([[1, 1, -1], [1, -1, -1], [-1, -1, 1]])
    pairs = find_pairs(members, {119: (np.array([1, 2, 3]), np.array([1, 2, 3]), votes)}, "House")
    assert len(pairs) == 1 and pairs.iloc[0]["splits"] == 1 and pairs.iloc[0]["side"] == "Democrat"


def test_page_opens_a_state_from_a_link():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.run()
    at.switch_page("views/17_Same_State_Different_Vote.py")
    at.query_params["state"] = "KY"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    text = " ".join(m.value for m in at.markdown)
    assert "Same-party senators" in text and "split on" in text
    at.segmented_control(key="ss_chamber").set_value("House").run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Same-party House pairs" in " ".join(m.value for m in at.markdown)


def test_member_summary_ranks_within_delegation():
    from state_splits import member_summary
    pairs = pd.DataFrame([
        {"congress": 119, "chamber": "House", "state": "KY", "side": "Republican", "same_side": True,
         "icpsr_a": a, "icpsr_b": b, "name_a": na, "name_b": nb, "party_a": "Republican", "party_b": "Republican",
         "bioguide_a": None, "bioguide_b": None, "both_voted": 600, "splits": sp, "split_pct": sp / 6}
        for a, b, na, nb, sp in [(1, 2, "A", "B", 150), (1, 3, "A", "C", 120), (2, 3, "B", "C", 30)]])
    s = member_summary(pairs).set_index("name")
    assert s.loc["A", "rank"] == 1 and s.loc["A", "colleagues"] == 2 and s.loc["A", "delegation"] == 3
    assert round(s.loc["A", "avg_split"], 2) == 22.5 and s.loc["A", "most_split_with"] == "B"
    assert s.loc["C", "rank"] == 3


def test_member_page_shows_same_state_section():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.run()
    at.switch_page("views/2_Member_Explorer.py")
    at.query_params["member"] = "M000355"  # Mitch McConnell
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Same state, different vote" in h.value for h in at.subheader)


def test_member_page_ranks_against_the_whole_delegation():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.run()
    at.switch_page("views/2_Member_Explorer.py")
    at.query_params["member"] = "M001184"  # Thomas Massie, who splits most among Kentucky Republicans
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "1 of 5 (splits most)" in " ".join(m.value for m in at.markdown)
