"""Overview page – chamber and party cohesion patterns."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(page_title="Overview | PartyCohesion", page_icon="📊", layout="wide")

DATA_PATH = Path(__file__).parent.parent / "data" / "members_processed.csv"

@st.cache_data
def load_members():
    return pd.read_csv(DATA_PATH)

df = load_members()

st.title("Overview")
st.markdown("Party and ideology patterns in recent Congresses. Scores are derived from roll-call voting behavior.")

# Filters
col_f1, col_f2 = st.columns(2)
with col_f1:
    congress = st.selectbox("Congress", options=sorted(df["congress"].unique(), reverse=True), index=0)
with col_f2:
    chamber = st.selectbox("Chamber", options=["House", "Senate", "Both"], index=0)

filtered = df[df["congress"] == congress]
if chamber != "Both":
    filtered = filtered[filtered["chamber"] == chamber]

# Key metrics
st.subheader(f"{congress}th Congress — {chamber}")

party_counts = filtered["party"].value_counts()
dem = filtered[filtered["party"] == "Democrat"]
rep = filtered[filtered["party"] == "Republican"]

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Democrats", len(dem))
with m2:
    st.metric("Republicans", len(rep))
with m3:
    if len(dem) > 0:
        st.metric("Dem. median ideology (Dim 1)", f"{dem['nominate_dim1'].median():.3f}")
    else:
        st.metric("Dem. median ideology", "—")
with m4:
    if len(rep) > 0:
        st.metric("Rep. median ideology (Dim 1)", f"{rep['nominate_dim1'].median():.3f}")
    else:
        st.metric("Rep. median ideology", "—")

st.markdown("---")

# Ideology distribution
st.subheader("Ideology Distribution (DW-NOMINATE Dimension 1)")
st.caption("Negative values lean more liberal; positive values lean more conservative. This is the primary dimension recovered from roll-call votes.")

plot_df = filtered[filtered["party"].isin(["Democrat", "Republican"])].copy()
if not plot_df.empty:
    fig = px.histogram(
        plot_df,
        x="nominate_dim1",
        color="party",
        nbins=40,
        barmode="overlay",
        opacity=0.7,
        color_discrete_map={"Democrat": "#2E86AB", "Republican": "#A23B72"},
        labels={"nominate_dim1": "DW-NOMINATE Dimension 1", "count": "Members"},
        title=None,
    )
    fig.update_layout(
        legend_title_text="Party",
        height=420,
        margin=dict(l=40, r=40, t=30, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No data for the selected filters.")

# Cohesion proxy distribution
st.subheader("Cohesion Proxy Distribution")
st.caption(
    "Higher values indicate a member’s ideology score sits closer to their party’s median in that chamber and Congress. "
    "This is a transparent proxy based on DW-NOMINATE; full party-unity percentages (share of votes with the party majority) "
    "can be layered in when complete roll-call series are processed."
)

if "cohesion_proxy" in plot_df.columns and not plot_df.empty:
    fig2 = px.box(
        plot_df,
        x="party",
        y="cohesion_proxy",
        color="party",
        color_discrete_map={"Democrat": "#2E86AB", "Republican": "#A23B72"},
        points="all",
        labels={"cohesion_proxy": "Cohesion Proxy (0–100)", "party": "Party"},
    )
    fig2.update_layout(showlegend=False, height=420, margin=dict(l=40, r=40, t=30, b=40))
    st.plotly_chart(fig2, use_container_width=True)

# Party median comparison over recent Congresses
st.subheader("Party Median Ideology Across Recent Congresses")
trend = (
    df[df["party"].isin(["Democrat", "Republican"])]
    .groupby(["congress", "chamber", "party"])["nominate_dim1"]
    .median()
    .reset_index()
)

fig3 = px.line(
    trend,
    x="congress",
    y="nominate_dim1",
    color="party",
    facet_col="chamber",
    markers=True,
    color_discrete_map={"Democrat": "#2E86AB", "Republican": "#A23B72"},
    labels={"nominate_dim1": "Median Dim 1", "congress": "Congress"},
)
fig3.update_layout(height=400, margin=dict(l=40, r=40, t=40, b=40))
st.plotly_chart(fig3, use_container_width=True)

st.markdown("---")
st.caption("Source: Voteview (HSall_members). Ideology scores are DW-NOMINATE estimates. Party cohesion proxy is derived from distance to party median within chamber-Congress.")
