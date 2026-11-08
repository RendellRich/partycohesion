"""
PartyCohesion home page: the site's question, three headline findings computed from the data,
and current coverage. Layout follows the "Home" mockup in the PartyCohesion Figma design system.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

from chart_utils import ordinal
from flip_utils import add_chamber_control, flip_scores
from platform_utils import all_member_platform_votes, load_platform, party_totals
from ui import card, fmt_date, inject_css

DATA_DIR = Path(__file__).parent.parent / "data"

inject_css()


@st.cache_data
def load():
    members = pd.read_csv(DATA_DIR / "members_processed.csv")
    summary = pd.read_csv(DATA_DIR / "unity_summary.csv")
    key_votes = pd.read_csv(DATA_DIR / "key_votes.csv")
    flip_votes = add_chamber_control(pd.read_csv(DATA_DIR / "flip_member_votes.csv"), members)
    return members, summary, key_votes, flip_votes


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
    card("Position flips", f"{pct_consistent:.0f}%",
         f"of current members ({len(scored)} with enough comparable votes) cast the same vote on debt limits, "
         "government funding, disaster aid and war powers under presidents of both parties, comparing like with like.")
    st.page_link("views/7_Position_Flips.py", label="See every member")
    st.page_link("views/9_How_It_Works.py", label="How this is measured")
with c2:
    card("Party unity", f"{means.min():.0f}–{means.max():.0f}%",
         f"Average share of the {ordinal(latest)} Congress's {n_unity:,} party-line votes on which members sided with "
         "their own party.")
    st.page_link("views/2_Member_Explorer.py", label="Explore members")
with c3:
    if top is not None:
        label = str(top["vote_desc"] if pd.notna(top["vote_desc"]) else top["bill_number"])
        card("Biggest party break", f"{int(top['broke'])} members",
             f"voted against their own party's majority on {label[:90]} ({top['chamber']}, {top['date']}).")
    st.page_link("views/5_Key_Votes.py", label="See who broke ranks")

# Finding 4: Platform Votes, every Congress in the data
plat_topics, plat_links = load_platform()
plat = party_totals(all_member_platform_votes()).set_index("party")
pd_, pr_ = plat.loc["Democrat"], plat.loc["Republican"]
st.write("")
p1, p2 = st.columns(2, gap="medium")
with p1:
    card("Platform votes, Democrats", f"{int(pd_['members_against'])} of {int(pd_['members'])}",
         "Democrats voted against their own party's platform at least once, on topics where the two parties' "
         f"platforms take opposite, specific positions ({len(plat_topics)} topics since 2007).")
with p2:
    card("Platform votes, Republicans", f"{int(pr_['members_against'])} of {int(pr_['members'])}",
         "Republicans voted against their own party's platform at least once, on the same topics. The totals depend "
         "on which topics qualify under the published rules, so they describe these votes, not which party is more "
         "loyal.")
st.page_link("views/11_Platform_Votes.py", label="See every topic, vote and member")

# Findings 5 to 7: missed votes, cosponsored then voted no, campaign statements
missed = pd.read_csv(DATA_DIR / "missed_votes.csv")
missed_pct = 100 * missed["missed"].sum() / missed["eligible"].sum()
house_median = (100 * missed["missed"] / missed["eligible"])[missed["chamber"] == "House"].median()
co_votes = pd.read_csv(DATA_DIR / "cosponsor_votes.csv")
co_nays = pd.read_csv(DATA_DIR / "cosponsor_nays.csv").merge(
    co_votes[["congress", "chamber", "rollnumber", "changed_before_vote"]], on=["congress", "chamber", "rollnumber"])
camp = pd.read_csv(DATA_DIR / "campaign_statement_votes.csv")
camp_diff = camp[camp["same_direction"] == "No"]
st.write("")
f1, f2, f3 = st.columns(3, gap="medium")
with f1:
    card("Missed votes", f"{missed_pct:.1f}%",
         f"of roll calls held while they served were missed by members since 2007. The typical House member misses "
         f"{house_median:.1f}% in a Congress, and a small group accounts for most absences.")
    st.page_link("views/2_Member_Explorer.py", label="Look up a member")
with f2:
    card("Cosponsored, then voted no", f"{len(co_nays):,}",
         f"times a bill's own sponsor or cosponsor voted against it on final passage. Only "
         f"{int((~co_nays['changed_before_vote']).sum())} of those came on text that hadn't changed since they signed.")
    st.page_link("views/12_Cosponsored_Then_No.py", label="See every case")
with f3:
    card("Campaign statements", f"{(camp['same_direction'] == 'Yes').sum()} of {len(camp)}",
         f"clear positions on House members' own campaign websites were followed by a vote in the same direction. "
         f"{len(camp_diff)} went the other way.")
    st.page_link("views/13_Campaign_Statements.py", label="Read the statements")

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
