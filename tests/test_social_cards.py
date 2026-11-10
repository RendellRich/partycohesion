"""Checks that the social cards state numbers that match the data."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("make_social_cards", ROOT / "scripts" / "make_social_cards.py")
cards = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cards)

RAW = ROOT / "data" / "raw" / "H117_votes.csv"


@pytest.fixture(scope="module")
def f():
    return cards.facts()


def test_same_bill_headline_matches_data(f):
    assert f["apart"] == int(f["by_congress"].sum())
    html = cards.card_same_bill(f, "wide")
    assert f"{f['apart']:,}" in html


@pytest.mark.skipif(not RAW.exists(), reason="raw Voteview files not downloaded")
def test_marriage_card_counts_add_up(f):
    bill = f["rfma_bill"]
    first, final = f["rfma_r_yea"][int(bill["first_roll"])], f["rfma_r_yea"][int(bill["final_roll"])]
    rf = f["rfma"]
    to_nay = int((rf["direction"] == "Yea to Nay").sum())
    to_yea = int((rf["direction"] == "Nay to Yea").sum())
    assert first - to_nay - f["rfma_skipped"] + to_yea == final


def test_cards_have_no_em_dashes(f):
    for slug, (fn, title, desc, _) in cards.CARDS.items():
        for size in ("wide", "tall"):
            if fn is cards.card_marriage and not RAW.exists():
                continue
            assert "—" not in fn(f, size), slug
        assert "—" not in title + desc, slug


def test_senate_card_claim_matches_data(f):
    moves = cards.handoffs(f["senate"])
    html = cards.card_senate(f, "wide")
    holds = all((after > before) == (cards.president_party(c) == party) for c, party, before, after in moves)
    assert ("changes of president" in html) == (bool(moves) and holds)
    assert f"{f['senate'].iloc[-1]['Republican']:.1f}%" in html


def test_final_card_uses_the_newest_completed_congress():
    from datetime import date
    assert cards.completed_congress(119, date(2026, 11, 10)) == 118
    assert cards.completed_congress(119, date(2027, 1, 2)) == 118
    assert cards.completed_congress(120, date(2027, 1, 5)) == 119


def test_final_card_numbers_match_members_file(f):
    import pandas as pd
    m = pd.read_csv(ROOT / "data" / "members_processed.csv")
    c = f["final"]["congress"]
    for x in cards.final_cells(f):
        want = m[(m["congress"] == c) & (m["chamber"] == x["chamber"]) & (m["caucus"] == x["party"])]["party_unity_pct"].mean()
        assert x["pct"] == round(want, 1)
    cap = cards.captions(f)["congress-final"]
    assert f"The {cards.ordinal(c)} Congress" in cap and "—" not in cap
    assert cards.change_text(1.24, 117) == "up 1.2 points from the 117th" and cards.change_text(0, 117) == "same as the 117th"
