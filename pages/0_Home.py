"""
PartyCohesion home page: the site's question, three headline findings computed from the data,
and current coverage. Layout follows the "Home" mockup in the PartyCohesion Figma design system.
"""

from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from chart_utils import ordinal
from flip_utils import flip_scores

DATA_DIR = Path(__file__).parent.parent / "data"

st.markdown("""
<style>
.pc-hero { font-size: 2.5rem; font-weight: 700; line-height: 1.2; max-width: 900px; margin: 0.5rem 0 1rem 0; }
.pc-intro { color: #A8A29E; font-size: 1.05rem; line-height: 1.6; max-width: 900px; margin-bottom: 1.5rem; }
.pc-card { background: #21201D; border: 1px solid #3A3733; border-radius: 10px; padding: 20px; height: 100%; }
.pc-eyebrow { color: #E9C46A; font-size: 0.8rem; font-weight: 600; letter-spacing: 0.04em; }
.pc-stat { font-size: 2.4rem; font-weight: 700; line-height: 1.2; margin: 6px 0 8px 0; }
.pc-body { color: #A8A29E; font-size: 1rem; line-height: 1.5; }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load():
    members = pd.read_csv(DATA_DIR / "members_processed.csv")
    summary = pd.read_csv(DATA_DIR / "unity_summary.csv")
    key_votes = pd.read_csv(DATA_DIR / "key_votes.csv")
    flip_votes = pd.read_csv(DATA_DIR / "flip_member_votes.csv")
    return members, summary, key_votes, flip_votes


def fmt_date(value) -> str:
    """e.g. Sep 30, 2026 (portable: %-d is not supported on Windows)."""
    ts = pd.Timestamp(value)
    return f"{ts:%b} {ts.day}, {ts.year}"


def card(eyebrow: str, stat: str, body: str) -> None:
    st.markdown(f'<div class="pc-card"><div class="pc-eyebrow">{escape(eyebrow)}</div>'
                f'<div class="pc-stat">{escape(stat)}</div><div class="pc-body">{escape(body)}</div></div>',
                unsafe_allow_html=True)


members, summary, key_votes, flip_votes = load()
latest = int(members["congress"].max())
current = members[members["congress"] == latest]

st.markdown('<div class="pc-hero">Do members of Congress vote the same way no matter who is president?</div>',
            unsafe_allow_html=True)
st.markdown('<div class="pc-intro">PartyCohesion uses the official roll-call record, every vote since 2007, to show how '
            "often each member sides with their party, and whether their position on the same question changes when the "
            "White House changes hands. No scorecards, no opinions: the votes and the method.</div>", unsafe_allow_html=True)

# Finding 1: Position Flips, current members
scores = flip_scores(flip_votes).merge(current[["icpsr"]].drop_duplicates(), on="icpsr")
scored = scores[scores["label"] != "Not enough votes"]
pct_consistent = (scored["label"] == "Consistent").mean() * 100 if len(scored) else 0

# Finding 2: party unity, current Congress
dr = current[current["party"].isin(["Democrat", "Republican"])].dropna(subset=["party_unity_pct"])
means = dr.groupby("party")["party_unity_pct"].mean()
n_unity = int(summary.loc[summary["congress"] == latest, "party_unity_votes"].sum())

# Finding 3: the biggest party break among final votes in the current Congress
breaks = key_votes[(key_votes["congress"] == latest) & (key_votes["series"] == "Biggest Party Breaks")].copy()
breaks["broke"] = breaks["dem_defectors"] + breaks["rep_defectors"]
top = breaks.sort_values("broke", ascending=False).iloc[0] if len(breaks) else None

c1, c2, c3 = st.columns(3, gap="medium")
with c1:
    card("POSITION FLIPS", f"{pct_consistent:.0f}%",
         f"of current members ({len(scored)} with enough votes) cast the same vote on debt limits, government funding, "
         "disaster aid and war powers under presidents of both parties.")
    st.page_link("pages/7_Position_Flips.py", label="See every member →")
with c2:
    card("PARTY UNITY", f"{means.min():.0f}–{means.max():.0f}%",
         f"Average share of the {ordinal(latest)} Congress's {n_unity:,} party-line votes on which members sided with "
         "their own party.")
    st.page_link("pages/2_Member_Explorer.py", label="Explore members →")
with c3:
    if top is not None:
        label = str(top["vote_desc"] if pd.notna(top["vote_desc"]) else top["bill_number"])
        card("BIGGEST PARTY BREAK", f"{int(top['broke'])} members",
             f"voted against their own party's majority on {label[:90]} ({top['chamber']}, {top['date']}).")
    st.page_link("pages/5_Key_Votes.py", label="See who broke ranks →")

st.write("")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Congress", ordinal(latest), help="House and Senate")
m2.metric("Members scored", f"{current['party_unity_pct'].notna().sum():,}")
m3.metric("Party-line votes", f"{n_unity:,}", help=f"so far in the {ordinal(latest)} Congress")
try:
    m4.metric("Data through", fmt_date(summary["latest_vote_date"].max()),
              help="Refreshed automatically twice a week")
except Exception:
    m4.metric("Data through", "—")

st.markdown("---")
st.caption("Sources: Voteview roll-call records (Lewis, Poole, Rosenthal, Boche, Rudkin & Sonnet) and White House "
           "Statements of Administration Policy. Coverage: 110th Congress (2007) to present. PartyCohesion is an "
           "independent educational project and does not endorse any party or candidate.")
