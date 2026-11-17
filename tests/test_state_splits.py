"""Same State, Different Vote: pairs of senators from one state and the roll calls where they split."""
from pathlib import Path

import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

from state_splits import find_splits

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
    pairs, splits = find_splits(members, rollcalls, {119: (np.array([1, 2, 3, 4]), np.array([1, 2, 3, 4]), votes)})
    ky = pairs[pairs["state"] == "KY"].iloc[0]
    assert (ky["both_voted"], ky["splits"], bool(ky["same_side"])) == (3, 2, True)
    me = pairs[pairs["state"] == "ME"].iloc[0]
    assert bool(me["same_side"]) is False and me["splits"] == 2  # an Independent counts with their caucus
    roll2 = splits[(splits["state"] == "KY") & (splits["rollnumber"] == 2)].iloc[0]
    assert (roll2["vote_a"], roll2["vote_b"], bool(roll2["broke_a"]), bool(roll2["broke_b"])) == ("Nay", "Yea", False, True)
    roll4 = splits[(splits["state"] == "KY") & (splits["rollnumber"] == 4)].iloc[0]
    assert bool(roll4["broke_a"]) and not bool(roll4["broke_b"])


def test_page_opens_a_state_from_a_link():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.run()
    at.switch_page("views/17_Same_State_Different_Vote.py")
    at.query_params["state"] = "KY"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    text = " ".join(m.value for m in at.markdown)
    assert "Same-party senators" in text and "split on" in text
