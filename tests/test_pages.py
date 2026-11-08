"""Every page loads without an error, and the main interactions work. Uses Streamlit's built-in test runner."""
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from flip_utils import flip_scores

ROOT = Path(__file__).resolve().parent.parent
PAGES = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "views").glob("*.py"))


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
    at = open_page("views/2_Member_Explorer.py")
    box = at.selectbox(key="me_member")
    box.set_value(option(box, "Murkowski, Lisa")).run()
    assert not at.exception, [e.value for e in at.exception]
    text = html(at)
    assert "Lisa Murkowski" in text and "Same question, different president" in [s.value for s in at.subheader]
    assert "Position Flips" in text and "Ideology score" in text


def test_compare_pair():
    at = open_page("views/6_Compare.py")
    for key, name in (("cmp_a", "Collins, Susan"), ("cmp_b", "Murkowski, Lisa")):
        box = at.selectbox(key=key)
        box.set_value(option(box, name)).run()
    assert not at.exception, [e.value for e in at.exception]
    text = html(at)
    assert "When they served together" in text and "roll calls they both voted on" in text
    assert "Same question, different president" in [h.value for h in at.subheader]
    assert text.count('class="pc-badge"') >= 2  # each member has at least one Position Flips label


def test_compare_never_served_together():
    at = open_page("views/6_Compare.py")
    for key, name in (("cmp_a", "Abercrombie"), ("cmp_b", "Ocasio-Cortez")):
        box = at.selectbox(key=key)
        box.set_value(option(box, name)).run()
    assert not at.exception
    assert any("never served" in i.value for i in at.info)


def test_key_votes_every_tab_has_a_vote_card():
    at = open_page("views/5_Key_Votes.py")
    assert len(at.tabs) >= 3
    assert html(at).count('<div class="pc-bars">') == len(at.tabs)
    at.selectbox(key="kv_cham").set_value("Senate").run()
    assert not at.exception


def test_explainer_matches_position_flips_math():
    at = open_page("views/9_How_It_Works.py")
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
    at = open_page("views/7_Position_Flips.py")
    box = at.selectbox(key="fl_member")
    box.set_value(box.options[0]).run()
    assert not at.exception


def test_all_votes_search_and_card():
    at = open_page("views/10_All_Votes.py")
    at.text_input(key="av_q").set_value("S. 5").run()
    assert not at.exception
    found = at.dataframe[0].value
    assert set(found["Chamber"]) == {"House", "Senate"}  # a bill number finds the bill in both chambers
    assert (found["Bill"] == "S5").all()
    text = html(at)
    assert '<div class="pc-bars">' in text and "voteview.com/rollcall/" in text
    at.text_input(key="av_q").set_value("no such words anywhere zzz").run()
    assert any("No votes match" in i.value for i in at.info)


def test_member_voting_record():
    at = open_page("views/2_Member_Explorer.py")
    box = at.selectbox(key="me_member")
    box.set_value(option(box, "Murkowski, Lisa")).run()
    assert "Voting record" in [s.value for s in at.subheader]
    record = at.dataframe[0].value
    assert len(record) > 100 and set(record["Their vote"]) <= {"Yea", "Nay", "Did not vote"}
    at.toggle(key="me_rec_against").set_value(True).run()
    assert not at.exception
    assert (at.dataframe[0].value["Against party"] == "Yes").all()


def test_platform_votes_member_lookup():
    at = open_page("views/11_Platform_Votes.py")
    text = html(at)
    assert "voted against their own party" in text and "Platform text" in text
    box = at.selectbox(key="pv_member")
    box.set_value(option(box, "Susan Collins")).run()
    assert not at.exception, [e.value for e in at.exception]
    assert "voted against the Republican platform on" in html(at)
    headings = [m.value for m in at.markdown if m.value.startswith("#### ")]
    latest = max(pd.read_csv(ROOT / "data" / "platform_topics.csv", comment="#")["congress"])
    assert at.selectbox(key="pv_cong").value == latest and 0 < len(headings) < 10  # one Congress by default
    at.selectbox(key="pv_cong").set_value(117).run()
    assert not at.exception, [e.value for e in at.exception]
    headings = [m.value for m in at.markdown if m.value.startswith("#### ")]
    assert "#### The PRO Act and right-to-work laws" in headings
    assert "#### Repealing the Affordable Care Act" not in headings  # a 115th Congress topic


def test_platform_record_on_member_and_compare_pages():
    at = open_page("views/2_Member_Explorer.py")
    box = at.selectbox(key="me_member")
    box.set_value(option(box, "Collins, Susan")).run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Votes on their party's platform" in [s.value for s in at.subheader]
    assert "Against party platform" in html(at) and "Skinny repeal" in html(at)
    at = open_page("views/6_Compare.py")
    for key, name in (("cmp_a", "Collins, Susan"), ("cmp_b", "Murkowski, Lisa")):
        box = at.selectbox(key=key)
        box.set_value(option(box, name)).run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Votes on their party's platform" in [s.value for s in at.subheader]
    assert "(against platform)" in html(at)


def test_no_legacy_pages_folder():
    """A pages/ folder switches on Streamlit's older automatic navigation, which skips app.py for direct links."""
    assert not (ROOT / "pages").exists()
    assert len(PAGES) >= 12


def test_all_votes_platform_column():
    at = open_page("views/10_All_Votes.py")
    at.toggle(key="av_plat").set_value(True).run()
    assert not at.exception, [e.value for e in at.exception]
    found = at.dataframe[0].value
    links = pd.read_csv(ROOT / "data" / "platform_votes.csv", comment="#")
    assert len(found) == len(links) and (found["Platform Topic"] != "").all()
    assert any("On Platform Votes:" in i.value for i in at.info)  # the picked vote explains its platform link
    at.toggle(key="av_plat").set_value(False).run()
    at.text_input(key="av_q").set_value("H.R. 3762").run()
    found = at.dataframe[0].value
    assert "Repealing the Affordable Care Act" in set(found["Platform Topic"])
    assert "" in set(found["Platform Topic"])  # amendment votes on the same bill aren't platform votes


def test_home_platform_votes_cards():
    at = open_page("views/0_Home.py")
    assert not at.exception, [e.value for e in at.exception]
    text = html(at)
    assert "PLATFORM VOTES · DEMOCRATS" in text and "PLATFORM VOTES · REPUBLICANS" in text
    assert "not which party is more loyal" in text


def test_missed_votes_on_member_page():
    at = open_page("views/2_Member_Explorer.py")
    box = at.selectbox(key="me_member")
    box.set_value(option(box, "Sherrill, Mikie")).run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Missed votes" in [s.value for s in at.subheader]
    text = html(at)
    assert "171" in text and "303" in text  # 119th Congress: 171 of 303 roll calls held while she served
    browse = at.dataframe[-1].value
    assert {"Missed Votes", "Missed %"} <= set(browse.columns)


def test_cosponsored_then_no_page():
    at = open_page("views/12_Cosponsored_Then_No.py")
    assert not at.exception, [e.value for e in at.exception]
    assert "Bills with the most signers voting no" in [s.value for s in at.subheader]
    at.toggle(key="cs_unchanged").set_value(True).run()
    assert not at.exception, [e.value for e in at.exception]
    assert (at.dataframe[0].value["Text changed before vote"] == "No").all()
