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
    assert "Platform votes, Democrats" in text and "Platform votes, Republicans" in text
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


def test_campaign_statements_page():
    at = open_page("views/13_Campaign_Statements.py")
    assert "Votes in a different direction from the campaign statement" in [s.value for s in at.subheader]
    text = html(at)
    assert "Massie" in text and "Fitzpatrick" in text
    at.selectbox(key="cmp_dir").set_value("Different from the statement").run()
    assert not at.exception, [e.value for e in at.exception]
    assert set(at.dataframe[0].value["Same direction"]) == {"No"}


def test_campaign_statements_other_topics():
    at = open_page("views/13_Campaign_Statements.py")
    for topic in ("Legal access to abortion", "Background checks on all gun sales"):
        at.selectbox(key="cmp_topic").set_value(topic).run()
        assert not at.exception, [e.value for e in at.exception]
        assert len(at.dataframe[0].value) > 100


def test_floor_statements_on_ukraine_topic():
    at = open_page("views/13_Campaign_Statements.py")
    assert "Said on the floor of Congress" not in [s.value for s in at.subheader]
    at.selectbox(key="cmp_topic").set_value("Military aid to Ukraine").run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Said on the floor of Congress" in [s.value for s in at.subheader]
    text = html(at)
    assert "Welch" in text and "Netanyahu" in text and "Rubio" in text
    floor = at.dataframe[0].value
    assert len(floor) == 122 and set(floor["Chamber"]) == {"House", "Senate"}
    at.selectbox(key="cmp_topic").set_value("Same-sex marriage").run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Gallagher" in html(at) and "religious liberty" in html(at)
    assert len(at.dataframe[0].value) == 62


def test_floor_statement_quotes_are_sourced():
    import pandas as pd
    f = pd.read_csv(ROOT / "data" / "floor_statements.csv", dtype=str).fillna("")
    quoted = f[f["quote"] != ""]
    assert quoted["source_url"].str.startswith("https://www.govinfo.gov/content/pkg/CREC-").all()
    assert set(f["stance"]) <= {"Supports more aid", "Opposes more aid", "Supports the bill", "Opposes the bill",
                                "With conditions", "No clear stance"}
    assert not f.duplicated(["topic", "bioguide_id"]).any()


def test_campaign_statements_on_member_page():
    at = open_page("views/2_Member_Explorer.py")
    box = at.selectbox(key="me_member")
    box.set_value(option(box, "Fitzpatrick, Brian")).run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Campaign statements and votes" in [s.value for s in at.subheader]
    text = html(at)
    assert "2 of 3" in text and "physical barrier" in text


def test_members_table_campaign_column():
    at = open_page("views/2_Member_Explorer.py")
    at.selectbox(key="me_cong").set_value(116).run()
    at.toggle(key="me_only_camp").set_value(True).run()
    assert not at.exception, [e.value for e in at.exception]
    table = at.dataframe[-1].value
    assert table["Campaign Statements"].notna().all() and len(table) > 100
    assert table["Voted Differently"].sum() >= 2  # Fitzpatrick and Johnson


def test_home_more_findings_and_share():
    at = open_page("views/0_Home.py")
    text = html(at)
    for label in ("Missed votes", "Cosponsored, then voted no", "Campaign statements", "pc-share"):
        assert label in text
    assert any("partycohesion.streamlit.app" in c.value for c in at.code)


def test_member_deep_link_details_and_share():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    at.switch_page("views/2_Member_Explorer.py")
    at.query_params["member"] = "F000466"
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.selectbox(key="me_member").value.startswith("Fitzpatrick, Brian")
    text = html(at)
    assert "pc-person" in text and "fitzpatrick.house.gov" in text and "Committees:" in text
    assert any("member=F000466" in c.value for c in at.code)


def test_home_lookup_and_unity_chart():
    at = open_page("views/0_Home.py")
    assert not at.exception, [e.value for e in at.exception]
    box = at.selectbox(key="home_lookup")
    box.set_value(option(box, "Brian Fitzpatrick")).run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.query_params.get("member") in ("F000466", ["F000466"])


def test_page_explainers():
    for page in ("views/10_All_Votes.py", "views/11_Platform_Votes.py", "views/13_Campaign_Statements.py"):
        assert "What this means" in html(open_page(page))


def test_member_page_seat_map_highlights_member():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.query_params["member"] = "F000466"
    at.run()
    at.switch_page("views/2_Member_Explorer.py")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("seat is ringed" in c.value for c in at.caption)


def test_same_bill_different_vote_page():
    at = open_page("views/14_Same_Bill_Different_Vote.py")
    assert "Bills where the most members changed while their party didn't" in [s.value for s in at.subheader]
    table = at.dataframe[0].value
    assert len(table) > 100
    assert set(table["Their party"].str.split(" then ").str[0]) <= {"Yea", "Nay"}
    at.text_input(key="sb_q").set_value("H.R. 8404").run()
    assert not at.exception, [e.value for e in at.exception]
    table = at.dataframe[0].value
    assert table["Member"].str.contains("Gallagher").any()
    at.toggle(key="sb_title").set_value(True).run()
    assert not at.exception, [e.value for e in at.exception]
    assert (at.dataframe[0].value["Title changed"] == "No").all()


def test_member_page_lists_same_bill_changes():
    at = open_page("views/2_Member_Explorer.py")
    label = next(o for o in at.selectbox(key="me_member").options if "Gallagher" in o and "WI" in o)
    at.selectbox(key="me_member").set_value(label).run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Same bill, different vote" in [s.value for s in at.subheader]
    assert "H.R. 8404" in html(at)


def test_home_find_members_by_zip_and_state():
    at = open_page("views/0_Home.py")
    at.text_input(key="home_zip").input("34219").run()  # Parrish, Florida
    assert not at.exception, [e.value for e in at.exception]
    labels = [b.label for b in at.button]
    assert sum(", Senate" in b for b in labels) == 2 and any("FL-16" in b for b in labels)
    at.text_input(key="home_zip").set_value("").run()
    at.selectbox(key="home_state").select("WY").run()
    assert any("WY at-large" in b.label for b in at.button)
    at.text_input(key="home_zip").set_value("00000").run()
    assert "isn't in the Census Bureau's ZIP list" in " ".join(c.value for c in at.caption)


def test_position_flips_says_who_is_left_out():
    at = open_page("views/7_Position_Flips.py")
    assert not at.exception
    note = [c.value for c in at.caption if "Who's left out" in c.value]
    assert note and "aren't counted in the percentages" in note[0] and "first Congress" in note[0]


def test_lobbying_page_waits_for_data(monkeypatch, tmp_path):
    monkeypatch.setenv("LOBBYING_DATA", str(tmp_path / "missing"))
    at = open_page("views/15_Lobbying.py")
    assert any("still being downloaded" in i.value for i in at.info)


def test_lobbying_page_with_data(monkeypatch):
    monkeypatch.setenv("LOBBYING_DATA", str(ROOT / "tests" / "fixtures" / "lobbying_sample"))
    at = open_page("views/15_Lobbying.py")
    text = html(at)
    assert "which members were contacted" in text and "for or against" in text  # what the reports can't say, up front
    at.text_input(key="lb_q").set_value("H.R. 8070").run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.selectbox(key="lb_bill").value == "HR8070"
    assert any("named this bill" in m.value for m in at.markdown)


def test_check_floor_quotes_catches_a_cut_sentence():
    import sys
    import pandas as pd
    sys.path.insert(0, str(ROOT / "scripts"))
    from check_floor_quotes import missing
    page = "<pre>It is unacceptable to throw money ``away,'' especially at a time when we cut our budget.</pre>"
    rows = pd.DataFrame({"bioguide_id": ["A", "B"], "topic": ["t", "t"], "source_url": ["u", "u"],
                         "quote": ['It is unacceptable to throw money "away," especially',
                                   "It is unacceptable to throw money away, especially."]})
    assert [b[0] for b in missing(rows, fetch=lambda url: page)] == ["B"]
