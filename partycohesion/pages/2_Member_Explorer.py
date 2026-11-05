"""Member Explorer – look up individual members."""

import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

st.set_page_config(page_title="Member Explorer | PartyCohesion", page_icon="👤", layout="wide")

DATA_PATH = Path(__file__).parent.parent / "data" / "members_processed.csv"

@st.cache_data
def load_members():
    return pd.read_csv(DATA_PATH)

df = load_members()

st.title("Member Explorer")
st.markdown("Search any member of the recent Congresses and view their ideology score and cohesion proxy.")

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
display_cols = ["name", "chamber", "state_abbrev", "party", "nominate_dim1", "cohesion_proxy", "nominate_number_of_votes"]
if "party_unity_pct" in filtered.columns:
    display_cols.insert(-1, "party_unity_pct")
rename = {
    "name": "Name",
    "chamber": "Chamber",
    "state_abbrev": "State",
    "party": "Party",
    "nominate_dim1": "Ideology (Dim 1)",
    "cohesion_proxy": "Cohesion Proxy",
    "party_unity_pct": "Party Unity %",
    "nominate_number_of_votes": "Votes in score",
}
table = filtered[display_cols].rename(columns=rename).sort_values("Name")

st.dataframe(
    table,
    use_container_width=True,
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

    d1, d2, d3, d4 = st.columns(4)
    with d1:
        st.metric("Party", member["party"])
    with d2:
        st.metric("State", member["state_abbrev"])
    with d3:
        st.metric("Ideology (Dim 1)", f"{member['nominate_dim1']:.3f}")
    with d4:
        st.metric("Cohesion Proxy", f"{member['cohesion_proxy']:.1f}" if pd.notna(member["cohesion_proxy"]) else "—")

    st.markdown(f"**Chamber:** {member['chamber']}  |  **Votes used in NOMINATE:** {int(member['nominate_number_of_votes']) if pd.notna(member['nominate_number_of_votes']) else '—'}")

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
        st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No members match the current filters.")

st.markdown("---")
st.caption("Ideology scores are DW-NOMINATE first-dimension estimates from Voteview. Cohesion proxy reflects distance from the party median within the same chamber and Congress. Full party-unity vote percentages will be added as complete roll-call series are processed.")
