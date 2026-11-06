"""Member Explorer – look up individual members."""

import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
from chart_utils import show_chart, ordinal, chamber_label


DATA_PATH = Path(__file__).parent.parent / "data" / "members_processed.csv"

@st.cache_data
def load_members():
    return pd.read_csv(DATA_PATH)

df = load_members()

st.title("Member Explorer")
st.markdown("Search any member of Congress from the 110th (2007) to the present and see how often they voted with their own party, where they sit ideologically, and how that changed over time.")

# Filters
c1, c2, c3 = st.columns(3)
with c1:
    congress = st.selectbox("Congress", options=sorted(df["congress"].unique(), reverse=True), index=0, key="me_cong")
with c2:
    chamber = st.selectbox("Chamber", options=["All", "House", "Senate"], index=0, key="me_cham")
with c3:
    party_filter = st.selectbox("Party", options=["All", "Democrat", "Republican", "Independent"], index=0, key="me_party")

filtered = df[df["congress"] == congress].copy()
if chamber != "All":
    filtered = filtered[filtered["chamber"] == chamber]
if party_filter != "All":
    filtered = filtered[filtered["party"] == party_filter]

# Search
search = st.text_input("Search by name or state (e.g. 'Smith' or 'TX')", "")
if search:
    mask = (
        filtered["name"].str.contains(search, case=False, na=False)
        | filtered["state_abbrev"].str.contains(search, case=False, na=False)
    )
    filtered = filtered[mask]

st.caption(f"Showing {len(filtered)} members")

# Table
display_cols = ["name", "chamber", "state_abbrev", "party", "party_unity_pct", "unity_votes_cast", "nominate_dim1", "cohesion_proxy"]
rename = {
    "name": "Name",
    "chamber": "Chamber",
    "state_abbrev": "State",
    "party": "Party",
    "nominate_dim1": "Ideology (Dim 1)",
    "cohesion_proxy": "Cohesion Proxy",
    "party_unity_pct": "Party Unity %",
    "unity_votes_cast": "Party-Unity Votes Cast",
}
table = filtered[display_cols].rename(columns=rename).sort_values("Name")

st.dataframe(
    table,
    width="stretch",
    height=420,
    hide_index=True,
)

st.markdown("---")

# Detail view
st.subheader("Member Detail")
if len(filtered) > 0:
    names = sorted(filtered["name"].unique())
    selected = st.selectbox("Select a member for detail", options=names)

    member = filtered[filtered["name"] == selected].iloc[0]

    d2, d3, d4, d5 = st.columns(4)
    with d2:
        st.metric("Party-State", f"{member['party'][0]}-{member['state_abbrev']}", help=member["party"])
    with d3:
        st.metric("Party Unity %", f"{member['party_unity_pct']:.1f}%" if pd.notna(member["party_unity_pct"]) else "—")
    with d4:
        st.metric("Ideology (Dim 1)", f"{member['nominate_dim1']:.3f}")
    with d5:
        st.metric("Cohesion Proxy", f"{member['cohesion_proxy']:.1f}" if pd.notna(member["cohesion_proxy"]) else "—")

    if pd.notna(member["party_unity_pct"]):
        st.markdown(
            f"**{member['party']}, {member['chamber']}**  |  Voted with the {member['party']} majority on "
            f"**{int(member['votes_with_party'])} of {int(member['unity_votes_cast'])}** party-unity votes."
        )
    else:
        st.markdown(
            f"**{member['party']}, {member['chamber']}**  |  No party unity rate: only Democrats and Republicans are scored, "
            "and the member must have cast at least one party-unity vote."
        )

    # Party unity across every Congress this member served in (same Voteview ID)
    history = df[(df["icpsr"] == member["icpsr"]) & df["party_unity_pct"].notna()].sort_values("congress")
    if len(history) > 1:
        party_avg = (
            df[df["party"] == member["party"]]
            .groupby(["congress", "chamber"])["party_unity_pct"]
            .mean()
            .reset_index()
            .rename(columns={"party_unity_pct": "party_avg"})
        )
        history = history.merge(party_avg, on=["congress", "chamber"], how="left")
        fig_h = px.line(
            history,
            x="congress",
            y=["party_unity_pct", "party_avg"],
            markers=True,
            labels={"congress": "Congress", "value": "Party Unity %", "variable": ""},
            title=f"Party unity across Congresses: {selected}",
            color_discrete_sequence=["#e03131", "#868e96"],
        )
        names = {"party_unity_pct": selected.split(",")[0], "party_avg": f"{member['party']} average"}
        fig_h.for_each_trace(lambda t: t.update(name=names.get(t.name, t.name)))
        fig_h.update_layout(height=360, margin=dict(l=40, r=40, t=50, b=40), xaxis=dict(dtick=1))
        show_chart(fig_h, f"Party unity across Congresses: {selected}", f"party_unity_history_{selected.split(',')[0].lower().replace(' ', '_')}")

    # Context: where this member sits relative to their party
    party_members = df[
        (df["congress"] == congress)
        & (df["chamber"] == member["chamber"])
        & (df["party"] == member["party"])
    ]

    if len(party_members) > 5:
        fig = px.histogram(
            party_members,
            x="nominate_dim1",
            nbins=25,
            title=f"Ideology distribution of {member['party']}s in the {member['chamber']} ({congress}th)",
            labels={"nominate_dim1": "DW-NOMINATE Dimension 1"},
            color_discrete_sequence=["#5c7cfa"],
        )
        # Add vertical line for the selected member
        fig.add_vline(
            x=member["nominate_dim1"],
            line_dash="dash",
            line_color="#e03131",
            annotation_text=selected.split(",")[0],
            annotation_position="top",
        )
        fig.update_layout(height=380, margin=dict(l=40, r=40, t=50, b=40))
        show_chart(fig, f"{selected.split(',')[0]} among {member['party']}s in the {member['chamber']}, {ordinal(congress)} Congress", f"ideology_position_{selected.split(',')[0].lower().replace(' ', '_')}_{congress}")
else:
    st.info("No members match the current filters.")

st.markdown("---")
st.caption("Party unity % is the share of party-unity votes (a majority of Democrats opposed a majority of Republicans) on which the member voted with their own party's majority, computed from Voteview roll-call records. Ideology scores are DW-NOMINATE first-dimension estimates. The cohesion proxy reflects distance from the party median within the same chamber and Congress.")
