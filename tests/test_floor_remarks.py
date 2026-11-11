"""Links from votes to members' own floor remarks."""
from pathlib import Path

import pandas as pd

import floor_remarks as fr

IDX = fr.load_index()


def test_index_shape_and_sources():
    assert list(IDX.columns) == fr.COLUMNS
    assert set(IDX["congress"]) >= set(range(110, 120))  # 2007 on
    assert IDX["url"].str.startswith("https://www.govinfo.gov/content/pkg/CREC-").all()
    assert set(IDX["chamber"]) <= {"House", "Senate"}


def test_window_picks_closest_remark_and_ignores_far_ones():
    spoke = pd.DataFrame({"bill_number": ["S2", "S2", "S2"], "date": ["2026-05-01", "2026-06-04", "2026-06-20"],
                          "url": ["far", "close", "after"]})
    assert fr.remark_near(spoke, "S2", "2026-06-05") == "close"
    assert fr.remark_near(spoke, "S2", "2026-08-01") is None  # nothing within 30 days before or 7 after
    assert fr.remark_near(spoke, None, "2026-06-05") is None


def test_known_example_cassidy_s2():
    rec = pd.DataFrame({"congress": [119], "bill_number": ["S2"], "date": ["2026-06-05"]})
    url = fr.attach(rec, "C001075", IDX).iloc[0]
    assert url and "CREC-2026-06-04" in url


def test_vote_explanation_is_not_remarks_on_the_bill():
    """In the Dec 17, 2025 rule debate, Rep. Fitzpatrick only said how he would have voted on a roll call. The
    Record's metadata lists him as speaking there; the text check must not turn that into remarks on the bills."""
    rec = pd.DataFrame({"congress": [119, 119], "bill_number": ["HR4776", "HR3492"], "date": ["2025-12-18", "2025-12-17"]})
    urls = fr.attach(rec, "F000466", IDX)
    assert not any(isinstance(u, str) and "PgH5947-3" in u for u in urls)


def test_real_remarks_are_kept():
    """Rep. Fitzpatrick's speech for the Ukraine Support Act (H.R. 2913) on June 4, 2026, but not the rule (H.Res.
    518) debated in the same section, which he didn't speak about."""
    rec = pd.DataFrame({"congress": [119, 119], "bill_number": ["HR2913", "HRES518"], "date": ["2026-06-04"] * 2})
    urls = fr.attach(rec, "F000466", IDX)
    assert "PgH3879" in urls.iloc[0] and urls.iloc[1] is None


def _index_module():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("fri", Path(__file__).resolve().parents[1] / "scripts" / "floor_remarks_index.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_text_check_rules():
    f = _index_module()
    words = " ".join(["word"] * 70)
    assert f.substantive(f"I yield back the balance of my time. {words}")  # a real speech survives
    assert f.substantive("Mr. Speaker, had I been present, I would have voted yea on Roll Call No. 343.") == ""
    roll_list = ("I was unable to be present. Had I been present I would have voted: " +
                 " ".join(f"Roll No. {n} on H.R. {n}, a bill about things, yea." for n in range(1, 20)))
    assert f.substantive(roll_list) == ""  # a long list of how they would have voted is still not remarks
    text = "x\n  Mr. SMITH. hi there\n Mr. McCAIN. a speech\n     Mr. QUOTED. not a turn\n"
    assert [label for label, _ in f.turns(text)] == ["Mr. SMITH", "Mr. McCAIN"]  # one leading space happens
    assert f.names_bill("I rise in support of H.R. 2913 today", "HR2913", None)
    assert f.names_bill("the Ukraine Support Act matters", "HR2913", "Ukraine Support Act")
    assert f.names_bill("Senate Joint Resolution 31 is", "SJRES31", None)
    assert not f.names_bill("S. 20 is different", "S2", None)


def test_which_sections_need_the_bill_named():
    f = _index_module()
    row = lambda headline, n_headline, n_bills: type("R", (), {"headline": headline, "n_headline": n_headline, "n_bills": n_bills})
    assert not f.needs_name(row(True, 1, 3))      # the section is about this bill
    assert f.needs_name(row(True, 4, 4))          # a rule for debating four bills at once
    assert f.needs_name(row(False, 1, 2))         # the bill only comes up in a section about another
    assert not f.needs_name(row(False, 0, 1))     # the only bill in the section
    assert f.needs_name(row(False, 0, 3))         # no main bill marked and several referenced


def test_topic_check_scores_remarks_against_the_bill(monkeypatch):
    import pytest
    pytest.importorskip("sklearn")
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    f = _index_module()
    import bill_topics
    profiles = {"HR1": "Wildfire prevention act forest management grants for states fire crews forest thinning",
                "HR2": "Veterans health care act medical centers clinics veterans affairs benefits",
                "HR3": "Postal service naming post office building", "HR4": "Water resources harbors dams levees"}
    # A big bill: many unrelated provisions, one amendment about a war commission.
    defense = ["National defense authorization act", "Military pay shipbuilding aircraft procurement missile defense",
               "Military construction housing bases cyber command space force readiness training",
               "Amendment to end the Afghanistan war commission early and cut its final report on the twenty year war",
               "In the nature of a substitute"]
    profiles["HR5"] = " ".join(defense)
    monkeypatch.setattr(bill_topics, "profiles", lambda c: profiles)
    monkeypatch.setattr(bill_topics, "parts", lambda c: {k: [v] for k, v in profiles.items()} | {"HR5": defense})
    rows = pd.DataFrame({"congress": [119] * 3, "bill_number": ["HR1", "HR1", "HR5"], "bioguide_id": ["A", "B", "C"],
                         "date": ["2026-01-01"] * 3, "granule": ["g"] * 3, "others": ["HR2", "HR2", ""]})
    said = {("2026-01-01", "g", "A"): "This bill funds fire crews and forest thinning so states can stop wildfire.",
            ("2026-01-01", "g", "B"): "I rise to honor the veterans of my district and their care at our clinics.",
            ("2026-01-01", "g", "C"): "The Afghanistan war commission needs one more year to finish its report on "
                                      "the war, so I oppose ending the commission early."}
    (on, _), (off, other), (part, _) = f.topic_scores(rows, said)
    assert on > f.TOPIC_MIN and not f.off_topic(on, None)
    assert off < f.TOPIC_MIN and f.off_topic(off, other) and other > off
    assert not f.off_topic(None, None)  # no description of the bill: no verdict
    # Scored against the whole bill the commission speech looks off topic; against its own amendment it doesn't.
    monkeypatch.setattr(bill_topics, "parts", lambda c: {})
    (_, _), (_, _), (whole, _) = f.topic_scores(rows, said)
    assert part > whole and not f.off_topic(part, None)
    # A short part can't carry a match on one shared word.
    said[("2026-01-01", "g", "C")] = "My substitute keeps the substitute language and nothing else from the substitute."
    monkeypatch.setattr(bill_topics, "parts", lambda c: {"HR5": ["In the nature of a substitute"]})
    (_, _), (_, _), (short, _) = f.topic_scores(rows, said)
    monkeypatch.setattr(bill_topics, "parts", lambda c: {})
    (_, _), (_, _), (whole_only, _) = f.topic_scores(rows, said)
    assert short == whole_only


def test_speech_well_before_a_bill_existed_is_about_an_older_bill(monkeypatch):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    f = _index_module()
    import bill_topics
    # H.R. 3590 of the 113th Congress was introduced in November 2013; a March 2013 speech citing "H.R. 3590" means
    # the 2009 health care law, which the metadata still tags as the current Congress's bill.
    monkeypatch.setattr(bill_topics, "introduced", lambda c: {"HR3590": "2013-11-20", "S100": "2013-12-13"})
    rows = pd.DataFrame({"congress": [113] * 4, "bill_number": ["HR3590", "HR3590", "S100", "S999"],
                         "date": ["2013-03-21", "2013-11-20", "2013-12-11", "2013-01-01"]})
    # Too early; on the day; two days early (a Senate statement dated ahead of its bill); no date known.
    assert f.before_introduced(rows).tolist() == [True, False, False, False]
