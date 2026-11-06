"""How We Measure Consistency: a plain-language, step-by-step walk through the Position Flips math,
using a real member's real votes. Every number on this page is computed live from the same data and
the same function (flip_utils.flip_scores) that the Position Flips page uses."""

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chart_utils import ACCENT, BG, PATTERN_COLORS, show_chart
from flip_utils import MIN_VOTES_EACH_SIDE, flip_scores

DATA_DIR = Path(__file__).parent.parent / "data"
CATEGORIES = ["All categories", "Debt limit", "Stopgap funding", "Full-year funding", "Disaster aid", "War powers limits"]
FRIENDLY = {
    "Debt limit": ("Raising or suspending the debt limit", "Yea (Nay on a resolution blocking an increase)"),
    "Stopgap funding": ("Short-term bills that keep the government open", "Yea"),
    "Full-year funding": ("Large packages that fund the government for the year", "Yea"),
    "Disaster aid": ("Emergency spending after hurricanes, fires and floods", "Yea"),
    "War powers limits": ("Resolutions ordering the president to withdraw U.S. forces", "Nay"),
}
# The two worked examples are the longest-serving Senate leaders of each party in the data, so the page does not
# pick a side. Their overall results happen to be close (+37 and +34), which makes the math easy to compare.
EXAMPLES = {"Chuck Schumer (D-NY)": "Schumer, Charles", "Mitch McConnell (R-KY)": "McConnell, Addison"}
OTHER = "Choose another member"


@st.cache_data
def load():
    members = pd.read_csv(DATA_DIR / "members_processed.csv")
    votes = pd.read_csv(DATA_DIR / "flip_votes.csv")
    member_votes = pd.read_csv(DATA_DIR / "flip_member_votes.csv")
    votes["label"] = votes["note"].where(votes["note"].notna() & (votes["note"].astype(str).str.strip() != ""),
                                         votes["vote_desc"].fillna(votes["bill_number"].fillna("")))
    latest = members.sort_values("congress").groupby("icpsr").tail(1)[["icpsr", "name", "party", "state_abbrev", "chamber"]]
    return votes, member_votes, latest


def scale_chart(shift: float | None, name: str) -> go.Figure:
    """The four pattern bands from -100 to +100, with the member's shift marked."""
    bands = [(-100, -25, "Opposite pattern"), (-25, 25, "Consistent"), (25, 50, "Partly changed"),
             (50, 100, "Changed with the White House")]
    fig = go.Figure()
    for lo, hi, label in bands:
        fig.add_shape(type="rect", x0=lo, x1=hi, y0=0, y1=1, fillcolor=PATTERN_COLORS[label], line=dict(color=BG, width=2))
        fig.add_annotation(x=(lo + hi) / 2, y=0.5, text=label.replace(" with the ", "<br>with the ").replace("Partly ", "Partly<br>"), showarrow=False,
                           font=dict(color="#171614", size=12))
    if shift is not None:
        fig.add_shape(type="line", x0=shift, x1=shift, y0=-0.15, y1=1.15, line=dict(color=ACCENT, width=4))
        fig.add_annotation(x=shift, y=1.15, yanchor="bottom", text=f"{name}: {shift:+.0f}", showarrow=False,
                           font=dict(color=ACCENT, size=14))
    fig.update_xaxes(range=[-102, 102], tickvals=[-100, -50, -25, 0, 25, 50, 100], showgrid=False, zeroline=False,
                     title="Shift (percentage points)")
    fig.update_yaxes(range=[-0.3, 1.5], visible=False)
    fig.update_layout(height=260, margin=dict(l=10, r=10, b=50))
    return fig


votes, member_votes, latest = load()

st.title("How We Measure Consistency")
st.markdown(
    "PartyCohesion asks one question: **does a member vote the same way on the same kind of bill no matter which party "
    "holds the White House?** This page walks through the exact math behind the Position Flips page, four steps, "
    "using a real member's real votes. Nothing here is estimated or weighted. It is counting and one subtraction."
)

# ---------------------------------------------------------------------------
# Pick the example
# ---------------------------------------------------------------------------
c1, c2 = st.columns([2, 1])
with c1:
    choice = st.radio("Worked example", [*EXAMPLES, OTHER], horizontal=True, key="hw_example")
with c2:
    category = st.selectbox("Type of vote", CATEGORIES, key="hw_cat")

scorable = latest[latest["icpsr"].isin(member_votes["icpsr"])].sort_values("name")
if choice == OTHER:
    options = {f"{r.name} ({r.party[0]}-{r.state_abbrev}, {r.chamber})": r.icpsr for r in scorable.itertuples()}
    pick = st.selectbox("Member", list(options), index=None, placeholder="Type a name…", key="hw_member")
    icpsr = options.get(pick)
else:
    match = scorable[scorable["name"].str.startswith(EXAMPLES[choice])]
    icpsr = int(match["icpsr"].iloc[0]) if len(match) else None

if icpsr is None:
    st.info("Pick a member to see their numbers.")
    st.stop()

person = latest[latest["icpsr"] == icpsr].iloc[0]
short = person["name"].split(",")[0]
mine = member_votes[member_votes["icpsr"] == icpsr]
if category != "All categories":
    mine = mine[mine["category"] == category]
mine = mine.merge(votes[["category", "congress", "chamber", "rollnumber", "date", "president", "president_party",
                         "label", "friendly_vote", "position_source"]],
                  on=["category", "congress", "chamber", "rollnumber"])
if mine.empty:
    st.info(f"{short} did not cast a Yea or Nay on any {category.lower()} vote in this data. Try another type of vote.")
    st.stop()

# ---------------------------------------------------------------------------
# Step 1
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("Step 1. Pick votes that come up under every president")
st.markdown(
    "Some questions return no matter who is president. On each one, one side of the vote **gives whichever president "
    "is in office more room** to govern. That is the *president-friendly* vote. It is not the \"right\" vote, just the "
    "side that helps the current administration."
)
st.dataframe(pd.DataFrame([{"Type of vote": k, "What it is": v[0], "President-friendly vote": v[1]}
                           for k, v in FRIENDLY.items()]), hide_index=True, width="stretch")
st.caption("When the White House published an official Statement of Administration Policy on a specific bill, the "
           "president's stated position is used instead of the default above.")

# ---------------------------------------------------------------------------
# Step 2
# ---------------------------------------------------------------------------
st.subheader("Step 2. Split their votes by who was president")
own_party = mine["party"].iloc[0]
st.markdown(
    f"Every vote is matched to the president in office on that date. Then each of {short}'s votes goes in one of two "
    f"piles: votes cast when **their own party** held the White House, and votes cast when **the other party** did."
)
show = mine.assign(**{"Matched president-friendly vote": mine["friendly"].map({1: "Yes", 0: "No"})}).sort_values("date")
cols = ["date", "president", "category", "label", "vote", "friendly_vote", "Matched president-friendly vote"]
names = {"date": "Date", "president": "President", "category": "Type", "label": "Bill", "vote": "Their vote",
         "friendly_vote": "President-friendly vote"}
for flag, title in [(1, "Pile 1: their own party's president"), (0, "Pile 2: the other party's president")]:
    part = show[show["own_president"] == flag]
    st.markdown(f"**{title}** ({len(part)} vote{'s' if len(part) != 1 else ''})")
    if part.empty:
        st.caption("No votes in this pile.")
    else:
        st.dataframe(part[cols].rename(columns=names), hide_index=True, width="stretch",
                     height=min(38 + 35 * len(part), 300), column_config={"Bill": st.column_config.TextColumn(width="large")})

# ---------------------------------------------------------------------------
# Step 3
# ---------------------------------------------------------------------------
s = flip_scores(mine.drop(columns=["date", "president", "president_party", "label", "friendly_vote", "position_source"]))
r = s.iloc[0]
st.subheader("Step 3. Count the president-friendly votes in each pile")
m1, m2 = st.columns(2)
own_txt = f"{r['rate_own']:.0f}%" if r["n_own"] else "No votes"
other_txt = f"{r['rate_other']:.0f}%" if r["n_other"] else "No votes"
m1.metric("Under their own party's president", own_txt,
          help=f"{int(r['friendly_own'])} president-friendly out of {int(r['n_own'])} votes")
m1.caption(f"{int(r['friendly_own'])} of {int(r['n_own'])} votes gave the president room")
m2.metric("Under the other party's president", other_txt,
          help=f"{int(r['friendly_other'])} president-friendly out of {int(r['n_other'])} votes")
m2.caption(f"{int(r['friendly_other'])} of {int(r['n_other'])} votes gave the president room")

# ---------------------------------------------------------------------------
# Step 4
# ---------------------------------------------------------------------------
st.subheader("Step 4. Subtract, and place the result on the scale")
if r["label"] == "Not enough votes":
    st.markdown(
        f"A member needs at least **{MIN_VOTES_EACH_SIDE} votes in each pile** to get a label, so one unusual vote can't "
        f"decide it. {short} has {int(r['n_own'])} and {int(r['n_other'])}, so there is **no label** for "
        f"{category.lower()}. Try \"All categories\" or another type of vote."
    )
    shift = None
else:
    shift = float(r["shift"])
    st.markdown(
        f"**{r['rate_own']:.0f}% − {r['rate_other']:.0f}% = {shift:+.0f} points.** That is the *shift*: how much more "
        f"often {short} gave the president room when it was their own party's president. It lands in "
        f"**{r['label']}**."
    )
show_chart(scale_chart(shift, short), f"{short}, {category.lower()}: shift on the consistency scale",
           f"consistency_scale_{short.lower()}")

st.markdown("""
**Reading the scale**

- **Consistent (−24 to +24):** about the same vote under presidents of both parties. A member who *always* votes yes,
  or *always* votes no, is consistent. This measures whether the position changes, not which position they hold.
- **Partly changed (+25 to +49)** and **Changed with the White House (+50 or more):** more willing to give the
  president room when the president is from their own party.
- **Opposite pattern (−25 or less):** more willing to give room to the *other* party's president.
""")

# ---------------------------------------------------------------------------
# Why and limits
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("Why it works this way")
st.markdown(f"""
- **Same question, different president.** Comparing a member with themselves on the same kind of bill takes their
  ideology out of the picture. Liberal or conservative, the question is only whether the vote moved with the White House.
- **The same rule for everyone.** Every member of both parties goes through these four steps with the same votes and
  the same cutoffs. Independents are scored with the party they caucus with.
- **A minimum number of votes.** At least {MIN_VOTES_EACH_SIDE} votes in each pile, so a single vote never sets a label.
""")
st.subheader("What it can't tell you")
st.markdown("""
- **The bills are not identical.** Two funding bills can carry different cuts or riders, so a changed vote can reflect
  a changed bill rather than a changed principle. That is why every vote is listed, so you can judge for yourself.
- **Congress matters too.** The party running each chamber writes these bills, and it isn't always the president's party.
- **It covers five kinds of votes,** not a member's whole record. It is one lens, not a grade.
""")
st.page_link("pages/7_Position_Flips.py", label="See every member's result on Position Flips →")
st.page_link("pages/3_Methodology.py", label="Full methodology and data sources →")
st.caption("Source: Voteview roll-call records and White House Statements of Administration Policy. Only actual Yea "
           "and Nay floor votes are counted.")
