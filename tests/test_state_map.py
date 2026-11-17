"""The per-state summary behind the map on Home, and the States page."""
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from state_map import party_mix, state_summary

ROOT = Path(__file__).resolve().parent.parent


def seats():
    return pd.DataFrame([
        {"bioguide_id": "A1", "name": "Ann", "chamber": "Senate", "state_abbrev": "ME", "district": 0, "party": "Republican"},
        {"bioguide_id": "A2", "name": "Bo", "chamber": "Senate", "state_abbrev": "ME", "district": 0, "party": "Independent"},
        {"bioguide_id": "A3", "name": "Cy", "chamber": "House", "state_abbrev": "ME", "district": 1, "party": "Democrat"},
        {"bioguide_id": "A4", "name": "Di", "chamber": "House", "state_abbrev": "ME", "district": 2, "party": "Democrat"},
        {"bioguide_id": "A5", "name": "Ed", "chamber": "House", "state_abbrev": "DC", "district": 0, "party": "Democrat"},
    ])


def test_summary_counts_and_hover_lines():
    s = state_summary(seats()).set_index("state")
    me = s.loc["ME"]
    assert (me["senators"], me["house"], me["members"]) == (2, 2, 4)
    assert me["seats_line"] == "2 senators, 2 representatives"
    assert me["mix"] == "2 Democrats, 1 Republican, 1 Independent"
    assert me["rep_share"] == 0.25
    assert me["short"] == "2D, 1R, 1I"
    assert s.loc["DC", "seats_line"] == "1 non-voting delegate in the House"


def test_party_mix_empty():
    assert party_mix(0, 0, 0) == "No members seated"


def test_every_state_and_dc_is_on_the_map():
    real = pd.read_csv(ROOT / "data" / "current_seats.csv")
    s = state_summary(real)
    assert len(s[s["senators"] == 2]) == 50
    assert s["members"].sum() == len(real)


def test_states_page_opens_from_a_link():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    at.switch_page("views/16_States.py")
    at.query_params["state"] = "FL"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    text = " ".join(m.value for m in at.markdown)
    assert "Members from Florida" in text and "Member_Explorer?member=" in text
    at.text_input(key="st_query").set_value("zzzz").run()
    assert any("No members match" in i.value for i in at.info)
