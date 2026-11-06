"""Every page loads without an error, and the main interactions work. Uses Streamlit's built-in test runner."""
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from flip_utils import flip_scores

ROOT = Path(__file__).resolve().parent.parent
PAGES = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "pages").glob("*.py"))


def open_page(page: str) -> AppTest:
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    at.switch_page(page)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def html(at: AppTest) -> str:
    return " ".join(m.value for m in at.markdown)


def option(widget, starts: str) -> str:
    return next(o for o in widget.options if o.startswith(starts))


@pytest.mark.parametrize("page", PAGES)
def test_page_loads(page):
    open_page(page)


def test_members_profile():
    at = open_page("pages/2_Member_Explorer.py")
    box = at.selectbox(key="me_member")
    box.set_value(option(box, "Murkowski, Lisa")).run()
    assert not at.exception, [e.value for e in at.exception]
    text = html(at)
    assert "Lisa Murkowski" in text and "Same question, different president" in [s.value for s in at.subheader]
    assert "Position Flips" in text and "Ideology score" in text


def test_compare_pair():
    at = open_page("pages/6_Compare.py")
    for key, name in (("cmp_a", "Collins, Susan"), ("cmp_b", "Murkowski, Lisa")):
        box = at.selectbox(key=key)
        box.set_value(option(box, name)).run()
    assert not at.exception, [e.value for e in at.exception]
    text = html(at)
    assert "When they served together" in text and "roll calls they both voted on" in text


def test_compare_never_served_together():
    at = open_page("pages/6_Compare.py")
    for key, name in (("cmp_a", "Abercrombie"), ("cmp_b", "Ocasio-Cortez")):
        box = at.selectbox(key=key)
        box.set_value(option(box, name)).run()
    assert not at.exception
    assert any("never served" in i.value for i in at.info)


def test_key_votes_every_tab_has_a_vote_card():
    at = open_page("pages/5_Key_Votes.py")
    assert len(at.tabs) >= 3
    assert html(at).count('<div class="pc-bars">') == len(at.tabs)
    at.selectbox(key="kv_cham").set_value("Senate").run()
    assert not at.exception


def test_explainer_matches_position_flips_math():
    at = open_page("pages/9_How_It_Works.py")
    mv = pd.read_csv(ROOT / "data" / "flip_member_votes.csv")
    m = pd.read_csv(ROOT / "data" / "members_processed.csv")
    for example, prefix in (("Chuck Schumer (D-NY)", "Schumer, Charles"), ("Mitch McConnell (R-KY)", "McConnell, Addison")):
        at.radio(key="hw_example").set_value(example).run()
        assert not at.exception
        icpsr = m.loc[m["name"].str.startswith(prefix), "icpsr"].iloc[0]
        r = flip_scores(mv[mv["icpsr"] == icpsr]).iloc[0]
        assert [x.value for x in at.metric] == [f"{r['rate_own']:.0f}%", f"{r['rate_other']:.0f}%"]
    for cat in ["Debt limit", "Stopgap funding", "Full-year funding", "Disaster aid", "War powers limits"]:
        at.selectbox(key="hw_cat").set_value(cat).run()
        assert not at.exception, cat


def test_position_flips_member_detail():
    at = open_page("pages/7_Position_Flips.py")
    box = at.selectbox(key="fl_member")
    box.set_value(box.options[0]).run()
    assert not at.exception
