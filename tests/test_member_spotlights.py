"""Member spotlight cards: neutral rotation and numbers that match the data."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("member_spotlights", ROOT / "scripts" / "member_spotlights.py")
ms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ms)

D = ms.load()


def test_rotation_is_fixed_complete_and_alternates_parties():
    order = ms.spotlight_order(D)
    assert order == ms.spotlight_order(D)  # same seed, same order
    eligible = D["members"][D["members"]["unity_votes_cast"] >= ms.MIN_VOTES]
    assert sorted(order) == sorted(eligible["bioguide_id"])
    caucus = eligible.set_index("bioguide_id")["caucus"]
    first = [caucus[b] for b in order[:40]]
    assert all(a != b for a, b in zip(first, first[1:]))  # parties alternate while both have members left
    chamber = eligible.set_index("bioguide_id")["chamber"]
    assert [chamber[b] for b in order[3:40:4]] == ["Senate"] * len(order[3:40:4])


def test_stats_match_members_file():
    b = ms.spotlight_order(D)[0]
    s = ms.stats(D, b)
    row = D["members"][D["members"]["bioguide_id"] == b].iloc[0]
    assert s["pct"] == row["party_unity_pct"] and s["with"] == row["votes_with_party"]
    assert 0 <= s["below"] <= 100


def test_caption_is_neutral_and_links_to_member():
    s = ms.stats(D, ms.spotlight_order(D)[1])
    cap = ms.caption(D, s)
    assert f"Member_Explorer?member={s['row']['bioguide_id']}" in cap
    assert "—" not in cap and "Democrat majority" not in cap
    assert "fixed random rotation" in cap


def test_apart_votes_match_unity_counts():
    for b in ms.spotlight_order(D)[:12]:
        s = ms.stats(D, b)
        assert len(s["apart"]) == s["cast"] - s["with"]


def test_missed_votes_context_is_in_caption():
    s = ms.stats(D, ms.spotlight_order(D)[2])
    assert "don't give reasons for absences" in ms.caption(D, s)


def test_kind_labels():
    assert ms.kind("On the Concurrent Resolution") == "Passing"
    assert ms.kind("On Agreeing to the Conference Report") == "Final version of"
    assert ms.kind("On the Motion to Discharge") == "Discharging"
    assert ms.kind("On the Amendment") == "An amendment to"


def test_concur_is_final_version_not_an_amendment():
    assert ms.kind("On Motion to Concur in the Senate Amendments") == "Final version of"


def test_rule_votes_are_procedural_and_named_for_their_bill():
    import pandas as pd
    r = pd.Series({"bill_number": "HRES518", "vote_question": "On Agreeing to the Resolution", "rule_for": "HR2913", "date": "2026-06-04",
                   "vote_desc": "Providing for consideration of the bill (H.R. 2913) to authorize ..."})
    assert ms.describe(D, r).startswith("The rule for debating H.R. 2913")
    assert ms.purpose(r) is None
    assert ms.RULE.search(r["vote_desc"]).group(1) == "H.R. 2913" and ms.bill_key("H.R. 2913") == "HR2913"


def test_amendment_purpose_comes_from_vote_record():
    import pandas as pd
    r = pd.Series({"bill_number": "HR8800", "vote_question": "On Agreeing to the Amendment", "rule_for": None, "date": "2026-07-22",
                   "vote_desc": "Issa of California Part A Amendment No. 30 to H.R. 8800: Amendment sought to do a thing"})
    assert ms.purpose(r) == "Amendment sought to do a thing (amendment by Rep. Issa)"
    assert ms.describe(D, r).startswith("An amendment to H.R. 8800")


def test_bar_scale_drops_below_80_when_needed():
    s = {"pct": 77.0, "avg": 97.1, "party": "Republican", "chamber": "House"}
    assert "scale 70 to 100%" in ms.compare_bar(s, 560, 15)
    assert "scale 80 to 100%" in ms.compare_bar({**s, "pct": 96.0}, 560, 15)


def test_title_follows_the_bill_when_the_senate_swaps_its_text():
    """H.R. 5334 began as an educator tax bill; the Senate passed it as the Russia sanctions package, and the House's
    final vote was on that version. The title shown for those votes is the sanctions one."""
    assert "Russian Federation" in ms.title_for(D, "HR5334", "2026-09-16")
    assert ms.title_for(D, "S1318", "2026-06-05") == "Fallen Servicemembers Religious Heritage Restoration Act"


def test_names_are_the_ones_members_go_by():
    import pandas as pd
    assert ms.spoken_name(pd.Series({"name": "Krishnamoorthi, S. Raja", "full_name": "Raja Krishnamoorthi"})) == "Raja Krishnamoorthi"
    assert ms.spoken_name(pd.Series({"name": "Crow, Jason", "full_name": "Jason Crow"})) == "Jason Crow"


def test_new_congress_falls_back_to_final_record():
    import pandas as pd
    m = pd.read_csv(ms.DATA / "members_processed.csv")
    assert ms.spotlight_congress(m) == (int(m["congress"].max()), True)
    new = m[m["congress"] == m["congress"].max()].copy()
    new["congress"] += 1
    new["unity_votes_cast"] = 12  # the first week of a new Congress
    newest = int(new["congress"].max())
    assert ms.spotlight_congress(pd.concat([m, new])) == (newest - 1, False)
    new["unity_votes_cast"] = 300
    assert ms.spotlight_congress(pd.concat([m, new])) == (newest, True)


def test_final_record_wording():
    s = ms.stats(D, ms.spotlight_order(D)[0])
    s = {**s, "current": False}
    cap = ms.caption(D, s)
    assert f"In the {s['latest']}th Congress" in cap and "final record" in cap
    assert "this Congress" not in cap and "current Congress" not in cap
    assert "final record" in ms.card(D, s, "wide")
