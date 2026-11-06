"""All Votes: search every House and Senate roll call since 2007, see how each party split, and who voted
against their own party's majority."""

from pathlib import Path

import pandas as pd
import streamlit as st

from chart_utils import chamber_label, ordinal
from ui import inject_css, intro, metric_row, vote_card
from vote_index import load_votes, members_who_broke_ranks, search_votes, voteview_url

DATA_DIR = Path(__file__).parent.parent / "data"
SHOW_AT_MOST = 500


@st.cache_data
def load_members():
    return pd.read_csv(DATA_DIR / "members_processed.csv")


def split(y, n) -> str:
    return f"{int(y)}–{int(n)}"


inject_css()
votes = load_votes()
members = load_members()

st.title("All Votes")
intro(f"Every House and Senate roll call since 2007, {len(votes):,} in all. Search by bill number or words in the "
      "bill's title, see how each party voted, and exactly who voted against their own party.")

q = st.text_input("Search", "", key="av_q", placeholder="e.g. H.R. 1, S. 5, debt limit, infrastructure")
st.caption("Tip: Senate records often list a bill by its formal title, so search by bill number (like S. 5) to find "
           "every vote on a bill in both chambers.")
c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1])
with c1:
    congresses = sorted(votes["congress"].unique(), reverse=True)
    congress = st.selectbox("Congress", ["All", *congresses], key="av_cong",
                            format_func=lambda c: "All (2007 to now)" if c == "All" else
                            f"{ordinal(c)} ({2 * c + 1787} to {2 * c + 1788})")
with c2:
    chamber = st.selectbox("Chamber", ["Both", "House", "Senate"], key="av_cham", format_func=chamber_label)
with c3:
    party_line = st.toggle("Party-line votes only", key="av_pl",
                           help="Votes where most Democrats and most Republicans voted on opposite sides")
with c4:
    broke = st.toggle("Someone broke ranks", key="av_br",
                      help="At least one Democrat or Republican voted against their own party's majority")

found = search_votes(votes, q, None if congress == "All" else int(congress), chamber, party_line, broke)
metric_row([
    ("Votes found", f"{len(found):,}", f"of {len(votes):,} since 2007"),
    ("Party-line votes", f"{int(found['party_unity_vote'].sum()):,}", "most of each party on opposite sides"),
    ("With members breaking ranks", f"{int((found['broke_ranks'] > 0).sum()):,}", "against their own party's majority"),
])

if found.empty:
    st.info("No votes match. Try fewer words, or set Congress to All.")
    st.stop()

shown = found.head(SHOW_AT_MOST)
st.dataframe(pd.DataFrame({
    "Date": shown["date"],
    "Chamber": shown["chamber"],
    "Roll Call": shown["rollnumber"],
    "Bill": shown["bill_number"].fillna(""),
    "Vote": shown["label"],
    "Question": shown["vote_question"],
    "Result": shown["vote_result"],
    "Total": [split(y, n) for y, n in zip(shown["yea_count"], shown["nay_count"])],
    "Dem.": [split(y, n) for y, n in zip(shown["dem_yea"], shown["dem_nay"])],
    "Rep.": [split(y, n) for y, n in zip(shown["rep_yea"], shown["rep_nay"])],
    "Broke Ranks": shown["broke_ranks"],
}), width="stretch", hide_index=True, height=420,
    column_config={"Vote": st.column_config.TextColumn(width="large")})
if len(found) > SHOW_AT_MOST:
    st.caption(f"Showing the {SHOW_AT_MOST} most recent of {len(found):,}. Add words or pick a Congress to narrow it.")
st.caption("Party columns show Yea–Nay. Broke Ranks counts Democrats and Republicans who voted against their party's "
           "majority; a party that split exactly evenly has no majority, so none of its members count.")

st.subheader("Look at one vote")
labels = {f"{r.date} · {r.chamber} roll call {r.rollnumber} · {str(r.label)[:90]}": i for i, r in shown.iterrows()}
pick = st.selectbox("Vote", list(labels), key="av_pick", label_visibility="collapsed")
v = shown.loc[labels[pick]]
vote_card(v, members_who_broke_ranks(v, members),
          link=voteview_url(v["congress"], v["chamber"], v["rollnumber"]))

st.markdown("---")
st.caption("Source: Voteview roll-call records, refreshed twice a week. Only actual Yea and Nay floor votes are "
           "counted. Each member's full voting record is on the Members page.")
