"""Same bill, different vote: which questions count, how a change is found, and the committed data."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import vote_changes as vc  # noqa: E402

DATA = ROOT / "data"


@pytest.mark.parametrize("question", [
    "On Passage", "On Passage of the Bill", "On Motion to Suspend the Rules and Pass, as Amended",
    "On Agreeing to the Conference Report", "On the Conference Report", "On Motion to Concur in the Senate Amendment",
    "On Motion to Suspend the Rules and Concur in the Senate Amendments", "On Overriding the Veto",
    "Passage, Objections of the President To The Contrary Notwithstanding", "On the Joint Resolution",
])
def test_support_questions_count(question):
    assert vc.SUPPORT_RE.search(question) and not vc.EXCLUDE_RE.search(question)


@pytest.mark.parametrize("question", [
    "On the Cloture Motion", "On Motion to Recommit with Instructions", "On Ordering the Previous Question",
    "On Agreeing to the Amendment", "On Motion to Table the Motion to Concur", "On Motion to Instruct Conferees",
    "On Motion to Suspend the Rules and Pass Certain Bills", "On the Motion",
    "On Motion to Disagree to the Senate Amendment",
])
def test_procedural_questions_do_not_count(question):
    assert not (vc.SUPPORT_RE.search(question) and not vc.EXCLUDE_RE.search(question))


def test_stage_names():
    assert vc.stage("On Passage") == "Passage"
    assert vc.stage("On Agreeing to the Conference Report") == "Final version (conference report)"
    assert vc.stage("On Motion to Concur in the Senate Amendment") == "Final version (other chamber's changes)"
    assert vc.stage("On Overriding the Veto") == "Veto override"


def test_title_changed():
    assert not vc.title_changed("Respect for Marriage Act", "Respect for Marriage Act")
    assert not vc.title_changed("Making appropriations for the Department of Defense for the fiscal year ending "
                                "September 30, 2019", "Department of Defense Appropriations Act, 2019")
    assert vc.title_changed("Enhancing Small Business Research and Innovation Act",
                            "Don't Ask, Don't Tell Repeal Act of 2010")
    assert not vc.title_changed("Some bill", None)


def write_congress(tmp_path, rollcalls, votes):
    raw = tmp_path / "raw"
    raw.mkdir()
    pd.DataFrame(rollcalls).to_csv(raw / "H999_rollcalls.csv", index=False)
    pd.DataFrame(votes).to_csv(raw / "H999_votes.csv", index=False)
    return raw


def test_changes_for_finds_a_member_who_changed_apart_from_the_party(tmp_path, monkeypatch):
    rc = [{"rollnumber": 1, "date": "2022-07-19", "bill_number": "HR1", "vote_question": "On Passage",
           "vote_desc": "A bill", "vote_result": "Passed", "yea_count": 3, "nay_count": 3},
          {"rollnumber": 2, "date": "2022-08-01", "bill_number": "HR1", "vote_question": "On Motion to Recommit",
           "vote_desc": "A bill", "vote_result": "Failed", "yea_count": 3, "nay_count": 3},
          {"rollnumber": 3, "date": "2022-12-08", "bill_number": "HR1",
           "vote_question": "On Motion to Concur in the Senate Amendment", "vote_desc": "A bill",
           "vote_result": "Passed", "yea_count": 4, "nay_count": 2}]
    # Members 1-3 Democrats (Yea, Yea); 4-6 Republicans: 4 and 5 Nay both times, 6 Nay then Yea.
    # Member 2 votes Nay on the motion to recommit, which must not count as a change.
    v = []
    for icpsr, first, final in [(1, 1, 1), (2, 1, 1), (3, 1, 1), (4, 6, 6), (5, 6, 6), (6, 6, 1)]:
        v += [{"rollnumber": 1, "icpsr": icpsr, "cast_code": first, "prob": 100},
              {"rollnumber": 3, "icpsr": icpsr, "cast_code": final, "prob": 100}]
    v += [{"rollnumber": 2, "icpsr": 2, "cast_code": 6, "prob": 100}]
    raw = write_congress(tmp_path, rc, v)
    monkeypatch.setattr(vc, "RAW_DIR", raw)
    members = pd.DataFrame({"congress": 999, "chamber": "House", "icpsr": range(1, 7),
                            "bioguide_id": [f"X{i}" for i in range(1, 7)], "name": [f"M{i}" for i in range(1, 7)],
                            "party": ["Democrat"] * 3 + ["Republican"] * 3, "caucus": ["Democrat"] * 3 + ["Republican"] * 3,
                            "state_abbrev": "WI"})
    rows, bills = vc.changes_for(999, "House", members)
    assert list(rows["icpsr"]) == [6]
    r = rows.iloc[0]
    assert (r["first_vote"], r["final_vote"], r["direction"]) == ("Nay", "Yea", "Nay to Yea")
    assert (r["party_first"], r["party_final"], bool(r["apart"])) == ("Nay", "Nay", True)
    assert r["final_stage"] == "Final version (other chamber's changes)"
    b = bills.iloc[0]
    assert (b["support_votes"], b["voted_twice"], b["changed"], b["changed_apart"]) == (2, 6, 1, 1)


def test_changes_for_with_no_changes_returns_empty_counts(tmp_path, monkeypatch):
    rc = [{"rollnumber": 1, "date": "2023-01-01", "bill_number": "SJRES1", "vote_question": "On the Joint Resolution",
           "vote_desc": "x", "vote_result": "Passed", "yea_count": 2, "nay_count": 1},
          {"rollnumber": 2, "date": "2023-02-01", "bill_number": "SJRES1", "vote_question": "On Overriding the Veto",
           "vote_desc": "x", "vote_result": "Veto Sustained", "yea_count": 2, "nay_count": 1}]
    v = [{"rollnumber": r, "icpsr": i, "cast_code": c, "prob": 100} for r in (1, 2) for i, c in ((1, 1), (2, 1), (3, 6))]
    raw = write_congress(tmp_path, rc, v)
    monkeypatch.setattr(vc, "RAW_DIR", raw)
    members = pd.DataFrame({"congress": 999, "chamber": "House", "icpsr": [1, 2, 3], "bioguide_id": ["A", "B", "C"],
                            "name": ["A", "B", "C"], "party": "Democrat", "caucus": "Democrat", "state_abbrev": "WI"})
    rows, bills = vc.changes_for(999, "House", members)
    assert rows is None
    assert int(bills["changed"].iloc[0]) == 0 and int(bills["changed_apart"].iloc[0]) == 0


def test_committed_data_is_consistent():
    changes = pd.read_csv(DATA / "vote_changes.csv")
    bills = pd.read_csv(DATA / "vote_change_bills.csv")
    assert len(changes) > 1000 and len(bills) > 100
    assert (changes["first_vote"] != changes["final_vote"]).sum() + \
        (changes["direction"] == "Changed, then changed back").sum() == len(changes)
    per_bill = changes.groupby(["congress", "chamber", "bill_number"]).agg(n=("icpsr", "size"), a=("apart", "sum"))
    joined = bills.set_index(["congress", "chamber", "bill_number"]).join(per_bill).fillna(0)
    assert (joined["n"] == joined["changed"]).all()
    assert (joined["a"] == joined["changed_apart"]).all()
    assert (bills["changed"] <= bills["voted_twice"]).all()
    assert not changes.duplicated(["congress", "chamber", "bill_number", "icpsr"]).any()


def test_respect_for_marriage_act_change_is_found():
    """Rep. Gallagher (R-WI) voted Nay on House passage in July 2022 and Yea on the final version in December, while
    most Republicans voted Nay both times. The floor remarks section relies on this."""
    changes = pd.read_csv(DATA / "vote_changes.csv")
    r = changes[(changes["congress"] == 117) & (changes["bill_number"] == "HR8404") &
                changes["name"].str.contains("Gallagher", na=False)]
    assert len(r) == 1
    r = r.iloc[0]
    assert (r["first_vote"], r["final_vote"], bool(r["apart"])) == ("Nay", "Yea", True)
