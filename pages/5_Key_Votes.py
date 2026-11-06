"""Key Votes – curated high-profile series + real party-unity context for the 119th Congress."""

import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path


DATA_DIR = Path(__file__).parent.parent / "data"

@st.cache_data
def load_members():
    return pd.read_csv(DATA_DIR / "members_processed.csv")

@st.cache_data
def load_summary():
    return pd.read_csv(DATA_DIR / "unity_summary.csv")

df = load_members()
n_unity_votes = int(load_summary().query("congress == 119")["party_unity_votes"].sum())

st.title("Key Votes & Party Unity")
st.markdown(
    "Classic party-unity rates (share of votes with the majority of one’s own party on party-unity votes) "
    "plus a framework for high-profile vote series."
)

# Real 119th unity summary
current = df[df["congress"] == 119].copy()
current = current[current["party"].isin(["Democrat", "Republican"])]

st.subheader("119th Congress — Party Unity Rates")
st.caption(
    "Party-unity votes are those where a majority of Democrats opposed a majority of Republicans. "
    "The rate is the percentage of times a member voted with their own party’s majority on those votes. "
    f"Computed from Voteview roll-call data ({n_unity_votes:,} party-unity votes identified across both chambers)."
)

if "party_unity_pct" in current.columns and current["party_unity_pct"].notna().any():
    c1, c2, c3, c4 = st.columns(4)
    dem = current[current["party"] == "Democrat"]["party_unity_pct"]
    rep = current[current["party"] == "Republican"]["party_unity_pct"]
    with c1:
        st.metric("Dem. mean unity", f"{dem.mean():.1f}%")
    with c2:
        st.metric("Rep. mean unity", f"{rep.mean():.1f}%")
    with c3:
        st.metric("Dem. median", f"{dem.median():.1f}%")
    with c4:
        st.metric("Rep. median", f"{rep.median():.1f}%")

    fig = px.box(
        current.dropna(subset=["party_unity_pct"]),
        x="party",
        y="party_unity_pct",
        color="party",
        points="all",
        color_discrete_map={"Democrat": "#2E86AB", "Republican": "#A23B72"},
        labels={"party_unity_pct": "Party Unity %", "party": "Party"},
        title="Distribution of Party Unity Rates — 119th Congress",
    )
    fig.update_layout(showlegend=False, height=420, margin=dict(l=40, r=40, t=50, b=40))
    st.plotly_chart(fig, width="stretch")

    st.subheader("Members with lower party-unity rates")
    st.caption("These members voted against their party majority more often on party-unity votes.")
    low = current.dropna(subset=["party_unity_pct"]).nsmallest(15, "party_unity_pct")[
        ["name", "chamber", "state_abbrev", "party", "party_unity_pct", "nominate_dim1"]
    ].rename(columns={
        "name": "Name", "chamber": "Chamber", "state_abbrev": "State",
        "party": "Party", "party_unity_pct": "Unity %", "nominate_dim1": "Ideology (Dim 1)"
    })
    st.dataframe(low, width="stretch", hide_index=True, height=360)
else:
    st.info("Party unity percentages for the 119th Congress are being prepared.")

st.markdown("---")
st.subheader("High-Profile Vote Series (Framework)")
st.markdown(
    "The sections below will host specific bill/vote series (appropriations packages, major nominations, "
    "signature legislation). The structure is ready; individual roll-call records and cohesion on those series "
    "will be layered in next."
)

SERIES = {
    "Major Appropriations / Funding Votes": "Large spending packages and continuing resolutions — frequent tests of party discipline.",
    "High-Profile Nominations": "Cabinet, judicial, and agency confirmations that drew significant attention.",
    "Signature Legislative Packages": "Major authorizing bills that defined the Congress.",
}
for title, desc in SERIES.items():
    with st.expander(title):
        st.write(desc)
        st.caption("Status: Framework ready — specific vote linkage coming next.")

st.markdown("---")
st.caption("Source: Voteview roll-call and member files. Party-unity definition follows the classic Voteview approach (majority of one party vs majority of the other).")
