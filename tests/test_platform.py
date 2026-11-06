"""Platform Votes: the hand-listed data follows its rules, and members are scored against the right platform."""
from pathlib import Path

import pandas as pd

from platform_utils import load_platform, member_platform_votes, member_summary, party_totals, platform_year
from ui import display_name

DATA = Path(__file__).resolve().parent.parent / "data"
MEMBERS = pd.read_csv(DATA / "members_processed.csv")


def scored():
    topics, links = load_platform()
    return topics, links, member_platform_votes(links, MEMBERS)


def against_on(mv, congress, chamber, roll):
    rows = mv[(mv["congress"] == congress) & (mv["chamber"] == chamber) & (mv["rollnumber"] == roll) & mv["against"]]
    return sorted(rows["name"].str.split(",").str[0])


def test_platform_in_force():
    assert platform_year(110, "Republican") == 2004 and platform_year(112, "Democrat") == 2008
    assert platform_year(114, "Republican") == 2012
    assert platform_year(115, "Democrat") == 2016 and platform_year(116, "Republican") == 2016
    assert platform_year(117, "Democrat") == 2020 and platform_year(118, "Republican") == 2016  # re-adopted 2016 text
    assert platform_year(119, "Republican") == 2024 and platform_year(120, "Democrat") == 2024


def test_topics_follow_the_rules():
    topics, links = load_platform()
    for t in topics.itertuples():
        assert t.dem_platform == platform_year(t.congress, "Democrat"), t.topic_id
        assert t.rep_platform == platform_year(t.congress, "Republican"), t.topic_id
        assert {t.dem_stance, t.rep_stance} == {"Supports", "Opposes"}, t.topic_id
        assert t.dem_source.startswith("https://") and t.rep_source.startswith("https://")
    assert links["date"].notna().all()  # every listed roll call exists in all_votes.csv
    assert (links["dem_platform_vote"] != links["rep_platform_vote"]).all()
    # only direct, non-procedural votes count
    assert links["counts"].equals((links["link"] == "direct") & (links["procedural"] == "no"))


def test_both_presidents_parties_represented():
    topics, _ = load_platform()
    republican_president = topics["congress"].isin([110, 115, 116, 119, 120]).sum()
    democratic_president = topics["congress"].isin([111, 112, 113, 114, 117, 118]).sum()
    assert republican_president >= 5 and democratic_president >= 5
    assert topics["congress"].min() == 110  # back to the start of the data


def test_known_votes_scored_correctly():
    _, _, mv = scored()
    # 2017 "skinny repeal": the three Republicans who voted no
    assert against_on(mv, 115, "Senate", 179) == ["Collins", "McCain", "Murkowski"]
    # 2021 $15 wage motion: seven Democrats plus King, who caucuses with Democrats
    wage = against_on(mv, 117, "Senate", 74)
    assert len(wage) == 8 and "King" in wage and "Manchin" in wage
    # 2013 assault weapons amendment: 15 Democrats and King (caucuses with Democrats) voted no; Kirk (R) voted yes
    awb = against_on(mv, 113, "Senate", 101)
    assert len(awb) == 17 and "King" in awb and "Kirk" in awb
    # 2015 amendment to end DACA: 26 Republicans voted no, so against the 2012 Republican platform
    daca = mv[(mv["congress"] == 114) & (mv["chamber"] == "House") & (mv["rollnumber"] == 29) & mv["against"]]
    assert set(daca["side"]) == {"Republican"} and len(daca) == 26
    # 2025 global tariff resolution: Republicans who voted to end the tariffs
    assert against_on(mv, 119, "Senate", 225) == ["Collins", "Murkowski", "Paul"]


def test_procedural_and_related_votes_are_shown_not_counted():
    _, links, mv = scored()
    assert len(links[~links["counts"]]) >= 3
    assert not mv.loc[(mv["procedural"] == "yes") | (mv["link"] == "related"), "counts"].any()
    ms = member_summary(mv)
    assert ms["cast"].sum() == mv["counts"].sum()  # the per-member totals use counted votes only


def test_party_totals_add_up():
    _, _, mv = scored()
    t = party_totals(mv).set_index("party")
    counted = mv[mv["counts"]]
    for side in ("Democrat", "Republican"):
        assert t.loc[side, "votes_cast"] == (counted["side"] == side).sum()
        assert t.loc[side, "members_against"] <= t.loc[side, "members"]


def test_roman_numeral_suffix():
    assert display_name("McCain, John Sidney, Iii") == "John McCain III"
    assert display_name("King, Angus Stanley, Jr.") == "Angus King Jr."
