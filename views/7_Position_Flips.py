"""Position Flips – does a member's vote on the same kind of question change depending on
which party holds the White House?"""

import pandas as pd
import plotly.express as px
import streamlit as st
from pathlib import Path
from chart_utils import show_chart, ordinal, PATTERN_COLORS, ACCENT, MUTED
from flip_utils import add_chamber_control, flip_scores, MIN_VOTES_EACH_SIDE

DATA_DIR = Path(__file__).parent.parent / "data"
CATEGORIES = ["All categories", "Debt limit", "Stopgap funding", "Full-year funding", "Disaster aid", "War powers limits"]
LABEL_ORDER = ["Consistent", "Partly changed", "Changed with the White House", "Opposite pattern"]
LABEL_COLORS = PATTERN_COLORS
FRIENDLY = {
    "Debt limit": "Yea to raise or suspend the debt limit (Nay on resolutions disapproving an increase)",
    "Stopgap funding": "Yea on a stopgap funding bill that passed the chamber",
    "War powers limits": "Nay on a resolution directing the president to remove U.S. forces",
    "Full-year funding": "Yea on the final vote for a full-year funding package (omnibus, minibus or full-year "
                         "continuing resolution) that became law",
    "Disaster aid": "Yea on the final vote for a law with $10 billion or more in disaster relief",
}


@st.cache_data
def load():
    members = pd.read_csv(DATA_DIR / "members_processed.csv")
    votes = pd.read_csv(DATA_DIR / "flip_votes.csv")
    member_votes = add_chamber_control(pd.read_csv(DATA_DIR / "flip_member_votes.csv"), members)
    votes["label"] = votes["note"].where(votes["note"].notna() & (votes["note"].astype(str).str.strip() != ""),
                                         votes["vote_desc"].fillna(votes["bill_number"].fillna("")))
    latest = members.sort_values("congress").groupby("icpsr").tail(1)[["icpsr", "name", "party", "caucus", "state_abbrev", "chamber", "congress"]]
    return members, votes, member_votes, latest


members, votes, member_votes, latest = load()
newest = int(members["congress"].max())

st.title("Position Flips")
st.markdown(
    "Some questions come up under presidents of both parties: raising the debt limit, funding the government, paying "
    "for disaster relief, and limiting the president's power to keep troops in combat. This page checks whether a member's vote on those "
    "questions **stays the same no matter who is president**, or **changes when the White House changes parties**."
)

st.page_link("views/9_How_It_Works.py", label="New here? See the math step by step with a real member")

with st.expander("How to read this page", expanded=False):
    st.markdown(f"""
For each type of vote, one side gives *whichever president is in office* more room:

- **Debt limit:** {FRIENDLY["Debt limit"]}
- **Stopgap funding:** {FRIENDLY["Stopgap funding"]}
- **Full-year funding:** {FRIENDLY["Full-year funding"]}
- **Disaster aid:** {FRIENDLY["Disaster aid"]}
- **War powers limits:** {FRIENDLY["War powers limits"]}

For every member, we compare how often they took that side **when their own party held the White House** versus
**when the other party did**, like for like: a vote is only compared with votes of the **same type** cast when the
member's party was in the **same position in their chamber** (running it, or not). The party running a chamber writes
these bills and moves votes about as much as the president does, so this keeps that from being counted as a change.
The **shift** is the average difference across those matched groups, in percentage points (groups with more votes on
both sides count more):

- **Consistent** (shift between −25 and +25): about the same position under both parties' presidents
- **Partly changed** (+25 to +50) and **Changed with the White House** (+50 or more): more willing to give the president
  room when it's their own party's president
- **Opposite pattern** (−25 or less): more willing to give room to the *other* party's president

**Where the White House issued an official Statement of Administration Policy on one of these votes (other than the
hand-listed debt limit votes), the
president's actual stated position is used** instead of the default (for example, Obama opposed the Sept. 2013 House
stopgap that also defunded the Affordable Care Act, so voting No was the president-friendly vote there).

A member needs at least {MIN_VOTES_EACH_SIDE} matched votes under each party's president to get a label. Only actual
Yea and Nay votes count. Presidents are matched to each vote by its date. The **simple difference**, using every vote
with no matching, is shown next to the shift for comparison.
""")

_counts = votes.groupby("president").agg(n=("date", "size"), first=("date", "min")).sort_values("first")
by_president = "Across all categories: " + ", ".join(f"{r.n} under {p}" for p, r in _counts.iterrows()) + "."
with st.expander("Limits of this measure", expanded=False):
    st.markdown(f"""
- **The bills are not identical.** Two debt limit or funding bills can carry different spending cuts, riders, or
  conditions, so a changed vote can reflect a changed bill rather than a changed principle. Each member's votes are
  listed below so you can judge for yourself.
- **Debt limit, full-year funding and disaster aid votes are listed by hand,** following written rules (see the full
  list at the bottom), because these laws usually pass as unrelated "vehicle" bills that no keyword search can find.
  Debt limit increases passed without a direct roll call (such as the House rule in Oct. 2021) or folded into a much
  larger bill (such as the 2025 reconciliation law) are not included.
- **Votes are not spread evenly across presidents.** {by_president} Some categories have no votes at all under some
  presidents, so members who served in different years are scored on different mixes of votes.
- **Matching leaves some votes out.** Votes with no match of the same type and chamber situation under the other
  party's president can't be compared, so some members are scored on a small share of their votes. The table shows
  how many votes each score rests on.
- **Independents are scored with the party they caucus with** (for example, Sanders and King with the Democrats). Those
  who caucus with neither party are not scored.
""")

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
with f1:
    category = st.selectbox("Type of vote", CATEGORIES, key="fl_cat")
with f2:
    chamber = st.selectbox("Chamber", ["Both", "House", "Senate"], key="fl_cham")
with f3:
    party = st.selectbox("Party", ["Both", "Democrat", "Republican"], key="fl_party")
with f4:
    current_only = st.toggle(f"Serving in the {ordinal(newest)} Congress", value=True, key="fl_current")

scores = flip_scores(member_votes, category).merge(latest, on="icpsr")
# Members are scored under the party they held when voting; show their most recent party
view = scores.copy()
if chamber != "Both":
    view = view[view["chamber"] == chamber]
if party != "Both":
    view = view[view["caucus"] == party]  # independents count with the party they caucus with
if current_only:
    view = view[view["congress"] == newest]
scored = view[view["label"] != "Not enough votes"]

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
st.subheader("How consistent are members?")
if scored.empty:
    st.info("No members in this selection have enough votes under both parties' presidents.")
else:
    m1, m2, m3 = st.columns(3)
    m1.metric("Members scored", f"{len(scored):,}", help=f"{len(view) - len(scored):,} more in this selection lack "
              f"{MIN_VOTES_EACH_SIDE}+ votes under each party's president")
    m2.metric("Consistent", f"{(scored['label'] == 'Consistent').mean() * 100:.0f}%")
    m3.metric("Changed with the White House", f"{(scored['label'] == 'Changed with the White House').mean() * 100:.0f}%")

    # Independents are grouped with the party they caucus with, as in the scoring
    dist = (scored.groupby(["caucus", "label"]).size().reset_index(name="Members").rename(columns={"caucus": "party"}))
    dist["Share"] = dist["Members"] / dist.groupby("party")["Members"].transform("sum") * 100
    fig = px.bar(dist, y="party", x="Share", color="label", orientation="h", text=dist["Share"].round(0).astype(int).astype(str) + "%",
                 category_orders={"label": LABEL_ORDER, "party": ["Democrat", "Republican"]},
                 color_discrete_map=LABEL_COLORS, labels={"party": "", "Share": "Share of members (%)", "label": ""},
                 hover_data={"Members": True, "Share": ":.0f"})
    fig.update_layout(height=280, barmode="stack", xaxis=dict(range=[0, 100], title=None, ticksuffix="%"),
                      legend=dict(orientation="h", y=-0.22, x=0), margin=dict(b=70))
    show_chart(fig, f"Position consistency, {category.lower()}", f"position_flips_{category.lower().replace(' ', '_')}")

    st.caption("Read this chart as a summary of members, not a verdict on either party: votes are not spread evenly "
               "across presidents, and members who served in different years are scored on different votes. See Limits above.")
    st.caption("Shift = how much more often a member gave the president room under their own party's president than "
               "under the other party's, comparing only matched votes (same type, same chamber situation). Simple "
               "difference = the same comparison using every vote, with no matching.")
    # Ties are broken by how many votes back the result, so better-supported patterns come first
    table = scored.assign(total=scored["n_own"] + scored["n_other"]).sort_values(["shift", "total", "name"], ascending=[False, False, True])
    st.dataframe(
        pd.DataFrame({
            "Name": table["name"],
            "Party-State": table["party"].str[0] + "-" + table["state_abbrev"],
            "Chamber": table["chamber"],
            "Own party's president": [f"{f:.0f} of {n:.0f} ({r:.0f}%)" for f, n, r in
                                      zip(table["friendly_own"], table["n_own"], table["rate_own"])],
            "Other party's president": [f"{f:.0f} of {n:.0f} ({r:.0f}%)" for f, n, r in
                                        zip(table["friendly_other"], table["n_other"], table["rate_other"])],
            "Simple difference": table["raw_shift"].astype(int),
            "Shift": table["shift"].astype(int),
            "Pattern": table["label"],
            "Votes compared": (table["matched_own"] + table["matched_other"]).astype(int),
            "All votes": table["total"].astype(int),
        }),
        width="stretch", hide_index=True, height=420,
    )

# ---------------------------------------------------------------------------
# One member in detail
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("One member's votes")
pool = scores if not current_only else scores[scores["congress"] == newest]
labels = {f"{r.name} ({r.party[0]}-{r.state_abbrev}, {r.chamber})": r.icpsr for r in pool.sort_values("name").itertuples()}
pick = st.selectbox("Member", list(labels), index=None, placeholder="Type a name…", key="fl_member")
if pick:
    icpsr = labels[pick]
    rows = []
    for cat in CATEGORIES[1:]:
        s = flip_scores(member_votes[member_votes["icpsr"] == icpsr], cat)
        if not s.empty:
            r = s.iloc[0]
            rows.append({"Type of vote": cat, "Own party's president": r["rate_own"], "Other party's president": r["rate_other"],
                         "n_own": int(r["n_own"]), "n_other": int(r["n_other"]), "Simple difference": r["raw_shift"],
                         "Shift": r["shift"], "Votes compared": int(r["matched_own"] + r["matched_other"]),
                         "Pattern": r["label"]})
    detail = pd.DataFrame(rows)
    if not detail.empty:
        long = detail.melt(id_vars=["Type of vote"], value_vars=["Own party's president", "Other party's president"],
                           var_name="White House", value_name="Gave the president room (%)").dropna()
        fig2 = px.bar(long, x="Type of vote", y="Gave the president room (%)", color="White House", barmode="group",
                      color_discrete_sequence=[ACCENT, MUTED], range_y=[0, 105])
        fig2.update_layout(height=340, legend_title_text="")
        name = pick.split(",")[0]
        show_chart(fig2, f"{name}: votes under each party's president", f"position_flips_{name.lower().replace(' ', '_')}")
        st.dataframe(detail.assign(**{
            "Own party's president": [f"{v:.0f}% of {n}" if n else "—" for v, n in zip(detail["Own party's president"], detail["n_own"])],
            "Other party's president": [f"{v:.0f}% of {n}" if n else "—" for v, n in zip(detail["Other party's president"], detail["n_other"])],
        }).drop(columns=["n_own", "n_other"]), width="stretch", hide_index=True)

    mine = member_votes[member_votes["icpsr"] == icpsr].merge(
        votes[["category", "congress", "chamber", "rollnumber", "date", "president", "label", "vote_result", "friendly_vote", "position_source"]],
        on=["category", "congress", "chamber", "rollnumber"])  # one vote can count in two categories
    mine["Their party ran the chamber"] = mine["own_chamber"].map({1.0: "Yes", 0.0: "No"})
    st.dataframe(
        mine.sort_values("date", ascending=False).rename(columns={
            "date": "Date", "category": "Type", "president": "President", "label": "Vote", "vote": "Their vote",
            "friendly_vote": "President-friendly vote", "vote_result": "Result", "chamber": "Chamber",
            "position_source": "Based on"})[
            ["Date", "Chamber", "President", "Their party ran the chamber", "Type", "Vote", "Their vote",
             "President-friendly vote", "Based on", "Result"]],
        width="stretch", hide_index=True, column_config={"Vote": st.column_config.TextColumn(width="large")},
    )

# ---------------------------------------------------------------------------
# Every vote used
# ---------------------------------------------------------------------------
st.markdown("---")
with st.expander(f"All {len(votes)} votes used on this page"):
    st.dataframe(
        votes.sort_values("date", ascending=False).rename(columns={
            "category": "Type", "date": "Date", "chamber": "Chamber", "rollnumber": "Roll Call", "president": "President",
            "label": "Vote", "vote_result": "Result", "friendly_vote": "President-friendly vote", "selection": "Selected by",
            "position_source": "Based on", "statement_title": "White House statement"})[
            ["Date", "Chamber", "Roll Call", "President", "Type", "Vote", "Result", "President-friendly vote", "Based on",
             "White House statement", "Selected by"]],
        width="stretch", hide_index=True, column_config={"Vote": st.column_config.TextColumn(width="large")},
    )
    st.caption("Selected by: rule = picked automatically by the written rule above; listed = on a hand-made list that "
               "follows a written rule (data/flip_debt_limit_votes.csv for the debt limit, data/flip_funding_votes.csv for "
               "full-year funding and disaster aid). Based on: president's statement = the White House's official Statement "
               "of Administration Policy on that bill; listed or default rule = no statement was issued, so the listed or "
               "default president-friendly vote applies.")

st.caption("Source: Voteview roll-call records. Only actual Yea and Nay floor votes are counted.")
