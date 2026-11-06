"""Overview page – chamber and party cohesion patterns."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from chart_utils import show_chart, ordinal, chamber_label


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
    show_chart(fig, f"Ideology distribution, {ordinal(congress)} Congress, {chamber_label(chamber)}", f"ideology_{congress}_{chamber.lower()}")
else:
    st.info("No data for the selected filters.")

# Party unity distribution
st.subheader("Party Unity Rates")
st.caption(
    "Share of party-unity votes (a majority of Democrats opposed a majority of Republicans) "
    "on which each member voted with their own party's majority. Computed from Voteview roll-call records."
)

unity_df = plot_df.dropna(subset=["party_unity_pct"])
if not unity_df.empty:
    u1, u2 = st.columns(2)
    for col, party in zip((u1, u2), ("Democrat", "Republican")):
        vals = unity_df.loc[unity_df["party"] == party, "party_unity_pct"]
        with col:
            st.metric(f"{party} median unity", f"{vals.median():.1f}%" if len(vals) else "—")
    fig_u = px.box(
        unity_df,
        x="party",
        y="party_unity_pct",
        color="party",
        points="all",
        hover_name="name",
        color_discrete_map={"Democrat": "#2E86AB", "Republican": "#A23B72"},
        labels={"party_unity_pct": "Party Unity %", "party": "Party"},
    )
    fig_u.update_layout(showlegend=False, height=420, margin=dict(l=40, r=40, t=30, b=40))
    show_chart(fig_u, f"Party unity rates, {ordinal(congress)} Congress, {chamber_label(chamber)}", f"party_unity_{congress}_{chamber.lower()}")

st.subheader("Average Party Unity Across Recent Congresses")
unity_trend = (
    df[df["party"].isin(["Democrat", "Republican"])]
    .groupby(["congress", "chamber", "party"])["party_unity_pct"]
    .mean()
    .round(1)
    .reset_index()
)
fig_ut = px.line(
    unity_trend,
    x="congress",
    y="party_unity_pct",
    color="party",
    facet_col="chamber",
    markers=True,
    color_discrete_map={"Democrat": "#2E86AB", "Republican": "#A23B72"},
    labels={"party_unity_pct": "Mean Party Unity %", "congress": "Congress"},
)
fig_ut.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
fig_ut.update_layout(height=400, margin=dict(l=40, r=40, t=40, b=40))
show_chart(fig_ut, "Average party unity by Congress", "party_unity_trend")

# Cohesion proxy distribution
st.subheader("Cohesion Proxy Distribution")
st.caption(
    "Higher values mean a member's ideology score sits closer to their party's median in that chamber and Congress. "
    "This is a separate, ideology-based measure. It complements the party unity rate above; it does not replace it."
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
    show_chart(fig2, f"Cohesion proxy, {ordinal(congress)} Congress, {chamber_label(chamber)}", f"cohesion_proxy_{congress}_{chamber.lower()}")

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
fig3.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
fig3.update_layout(height=400, margin=dict(l=40, r=40, t=40, b=40))
show_chart(fig3, "Party median ideology by Congress", "party_median_ideology_trend")

st.markdown("---")
st.caption("Source: Voteview (member and roll-call vote files). Ideology scores are DW-NOMINATE estimates. Party unity rates are computed from individual roll-call votes. The cohesion proxy is derived from distance to the party median within chamber and Congress.")
