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
