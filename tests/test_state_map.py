"""The per-state summary behind the map on Home, and the States page."""
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from state_map import COLOR_BY, member_records, party_mix, state_map, state_summary

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
    assert at.title[0].value == "Florida" and "Member_Explorer?member=" in text
    assert [h.value for h in at.header][:2] == ["Senators", "House, by district"]
    at.text_input(key="st_query").set_value("zzzz").run()
    assert any("No members match" in i.value for i in at.info)


def test_states_zip_narrows_to_your_members():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    at.switch_page("views/16_States.py")
    at.query_params["state"] = "TX"
    at.run()
    at.text_input(key="st_zip").set_value("78701").run()
    assert not at.exception, [e.value for e in at.exception]
    text = " ".join(m.value for m in at.markdown)
    assert "Your members for ZIP code 78701" in text
    seats = pd.read_csv(ROOT / "data" / "current_seats.csv")
    tx = seats[seats["state_abbrev"] == "TX"]
    shown = [b for b in tx["bioguide_id"] if f"member={b}" in text]
    assert len(shown) == 3  # two senators and one House member
    # A ZIP code from another state points there instead
    at.text_input(key="st_zip").set_value("34219").run()
    assert "is in Florida" in " ".join(m.value for m in at.markdown)


def records():
    return pd.DataFrame({"party_unity_pct": [90.0, 80.0, 96.0, 98.0, None], "missed_pct": [1.0, 3.0, 2.0, 2.0, None],
                         "label": ["Consistent", "Partly changed", "Consistent", "Not enough votes", None]},
                        index=pd.Index(["A1", "A2", "A3", "A4", "A5"], name="bioguide_id"))


def test_summary_averages_skip_delegates_and_thin_flip_counts():
    s = state_summary(seats(), records()).set_index("state")
    me = s.loc["ME"]
    assert me["avg_unity"] == 91.0 and me["avg_missed"] == 2.0
    assert (me["n_consistent"], me["n_flip"]) == (2, 3) and round(me["consistent"]) == 67
    assert pd.isna(s.loc["DC", "avg_unity"]) and pd.isna(s.loc["DC", "consistent"])


def test_every_coloring_draws_and_grays_out_missing_states():
    s = state_summary(seats(), records())
    for color_by in COLOR_BY:
        fig = state_map(s, color_by)
        assert fig.data[0].customdata[0][0] in {"DC", "ME"}
    fig = state_map(s, "Party unity")
    assert list(fig.data[1].locations) == ["DC"]  # delegate-only: gray, no voting record
    assert "no voting record" in fig.data[1].customdata[0][5]


def test_real_data_has_averages_for_every_state():
    real = state_summary(pd.read_csv(ROOT / "data" / "current_seats.csv"), member_records(ROOT / "data"))
    states = real[~real["state"].isin(["DC", "PR", "GU", "VI", "AS", "MP"])]
    assert states["avg_unity"].notna().all() and states["avg_missed"].notna().all()
    assert states["avg_unity"].between(50, 100).all()


def test_big_states_have_a_district_picker():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    at.switch_page("views/16_States.py")
    at.query_params["state"] = "CA"
    at.run()
    pick = at.selectbox(key="st_district_CA")
    assert pick.options[0] == "All districts" and "CA-12" in pick.options
    pick.set_value("CA-12").run()
    text = " ".join(m.value for m in at.markdown)
    seats = pd.read_csv(ROOT / "data" / "current_seats.csv")
    ca_house = seats[(seats["state_abbrev"] == "CA") & (seats["chamber"] == "House")]
    shown = [b for b in ca_house["bioguide_id"] if f"member={b}" in text]
    assert len(shown) == 1
