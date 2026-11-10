"""Find your members by ZIP code or state."""
from datetime import date

import find_members as fm

SEATS, ZIPS = fm.load()


def test_clean_zip():
    assert fm.clean_zip(" 34219 ") == "34219" and fm.clean_zip("34219-1234") == "34219"
    assert fm.clean_zip("3421") is None and fm.clean_zip("abcde") is None and fm.clean_zip(None) is None


def test_zip_in_one_district():
    r = fm.lookup_zip("34219", SEATS, ZIPS, today=date(2026, 11, 10))  # Parrish, Florida
    assert r["found"] and r["state"] == "FL" and len(r["senators"]) == 2
    assert [d["district"] for d in r["districts"]] == [16] and len(r["districts"][0]["member"]) == 1


def test_zip_across_districts_lists_each_with_share():
    multi = ZIPS.groupby("zip").filter(lambda g: len(g) > 1)["zip"].iloc[0]
    r = fm.lookup_zip(multi, SEATS, ZIPS, today=date(2026, 11, 10))
    shares = [d["share"] for d in r["districts"]]
    assert len(shares) > 1 and shares == sorted(shares, reverse=True) and 0.95 <= sum(shares) <= 1.0


def test_after_new_lines_falls_back_to_whole_state():
    r = fm.lookup_zip("34219", SEATS, ZIPS, today=date(2027, 1, 3))
    assert not r["lines_current"] and len(r["districts"]) == (SEATS.query("state_abbrev == 'FL' and chamber == 'House'")["district"].nunique())


def test_unknown_zip_and_at_large():
    assert not fm.lookup_zip("00000", SEATS, ZIPS)["found"]
    assert fm.district_label("WY", 0) == "WY at-large" and fm.district_label("FL", 16) == "FL-16"


def test_every_state_has_two_senators_and_every_seat_a_member_file():
    sen = SEATS[SEATS["chamber"] == "Senate"].groupby("state_abbrev").size()
    assert len(sen) == 50 and (sen == 2).all()
    assert SEATS["bioguide_id"].is_unique
