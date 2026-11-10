"""Overview page – chamber and party cohesion patterns."""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from chart_utils import BG, PARTY_COLORS, chamber_label, ordinal, show_chart
from ui import early_congress, early_congress_note, explainer, intro, metric_row

ORDER = {"party": ["Democrat", "Republican"], "chamber": ["House", "Senate"]}


DATA_PATH = Path(__file__).parent.parent / "data" / "members_processed.csv"

@st.cache_data
def load_members():
    return pd.read_csv(DATA_PATH)

df = load_members()

st.title("Overview")
intro("How tightly each party votes together, and how far apart the parties sit, Congress by Congress. Every number "
      "comes from roll-call votes.")
explainer("Pick a Congress and a chamber. The first chart shows how far apart the two parties sit on Voteview's "
          "ideology scale. The next ones show how often members side with their own party when the parties split.")

if early_congress_note(df):
    st.info(early_congress_note(df))

# Filters
col_f1, col_f2 = st.columns(2)
with col_f1:
    congress = st.selectbox("Congress", options=sorted(df["congress"].unique(), reverse=True),
                            index=1 if early_congress(df) else 0, format_func=ordinal)
with col_f2:
    chamber = st.selectbox("Chamber", options=["House", "Senate", "Both"], index=0)

filtered = df[df["congress"] == congress]
if chamber != "Both":
    filtered = filtered[filtered["chamber"] == chamber]

# Key metrics
st.subheader(f"{ordinal(congress)} Congress: {chamber_label(chamber)}")

party_counts = filtered["party"].value_counts()
dem = filtered[filtered["party"] == "Democrat"]
rep = filtered[filtered["party"] == "Republican"]

def median_score(rows: pd.DataFrame) -> str:
    return f"{rows['nominate_dim1'].median():+.2f}" if len(rows) else "none"


metric_row([
    ("Democrats", f"{len(dem):,}", "members who served"),
    ("Republicans", f"{len(rep):,}", "members who served"),
    ("Typical Democrat's ideology score", median_score(dem), "median, on a scale of -1 to +1"),
    ("Typical Republican's ideology score", median_score(rep), "median, on a scale of -1 to +1"),
])

# Ideology distribution
st.subheader("Where members sit on the ideology scale")
st.caption("Voteview's ideology score (DW-NOMINATE, first dimension) runs from -1 to +1. Lower scores lean liberal and "
           "higher scores lean conservative. It is estimated from roll-call votes alone.")

plot_df = filtered[filtered["party"].isin(["Democrat", "Republican"])].copy()
if not plot_df.empty:
    fig = px.histogram(
        plot_df,
        x="nominate_dim1",
        color="party",
        nbins=40,
        barmode="overlay",
        color_discrete_map=PARTY_COLORS,
        category_orders=ORDER,
        labels={"nominate_dim1": "Ideology score", "count": "Members"},
        title=None,
    )
    fig.update_traces(marker_opacity=1)  # overlay mode defaults to half opacity; bargap leaves the gaps
    fig.update_layout(
        yaxis_title="Members",
        height=420,
        margin=dict(l=40, r=40, t=30, b=40),
    )
    show_chart(fig, f"Members by ideology score, {ordinal(congress)} Congress, {chamber_label(chamber)}", f"ideology_{congress}_{chamber.lower()}")
else:
    st.info("No data for the selected filters.")

# Party unity distribution
st.subheader("How often members vote with their party")
st.caption(
    "Share of party-unity votes (a majority of Democrats opposed a majority of Republicans) "
    "on which each member voted with their own party's majority. Computed from Voteview roll-call records."
)

unity_df = plot_df.dropna(subset=["party_unity_pct"])
if not unity_df.empty:
    medians = unity_df.groupby("party")["party_unity_pct"].median()
    metric_row([(f"Typical {p}", f"{medians[p]:.1f}%" if p in medians else "none", "median share of party-line votes "
                 "cast with own party") for p in ("Democrat", "Republican")])
    fig_u = px.box(
        unity_df,
        x="party",
        y="party_unity_pct",
        color="party",
        points="all",
        hover_name="name",
        color_discrete_map=PARTY_COLORS,
        category_orders=ORDER,
        labels={"party_unity_pct": "Votes with own party (%)", "party": ""},
    )
    fig_u.update_traces(marker=dict(size=6, line=dict(color=BG, width=1)), jitter=0.4, pointpos=0)
    fig_u.update_layout(showlegend=False, height=420, margin=dict(l=40, r=40, t=30, b=40))
    show_chart(fig_u, f"Share of party-line votes cast with own party, {ordinal(congress)} Congress, {chamber_label(chamber)}", f"party_unity_{congress}_{chamber.lower()}")

st.subheader("Party unity over time")
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
    color_discrete_map=PARTY_COLORS,
    category_orders=ORDER,
    labels={"party_unity_pct": "Average votes with own party (%)", "congress": "Congress"},
)
fig_ut.update_traces(line_width=2, marker=dict(size=8, line=dict(color=BG, width=2)))
fig_ut.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
fig_ut.update_layout(height=400, margin=dict(l=40, r=40, t=40, b=40))
show_chart(fig_ut, "Average share of party-line votes cast with own party, by Congress", "party_unity_trend")

# Cohesion proxy distribution
st.subheader("How close members sit to their party's middle")
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
        color_discrete_map=PARTY_COLORS,
        category_orders=ORDER,
        points="all",
        labels={"cohesion_proxy": "Closeness to party median (0 to 100)", "party": ""},
    )
    fig2.update_traces(marker=dict(size=6, line=dict(color=BG, width=1)), jitter=0.4, pointpos=0)
    fig2.update_layout(showlegend=False, height=420, margin=dict(l=40, r=40, t=30, b=40))
    show_chart(fig2, f"Closeness to party median ideology, {ordinal(congress)} Congress, {chamber_label(chamber)}", f"cohesion_proxy_{congress}_{chamber.lower()}")

# Party median comparison over recent Congresses
st.subheader("How far apart the parties sit over time")
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
    color_discrete_map=PARTY_COLORS,
    category_orders=ORDER,
    labels={"nominate_dim1": "Median ideology score", "congress": "Congress"},
)
fig3.update_traces(line_width=2, marker=dict(size=8, line=dict(color=BG, width=2)))
fig3.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
fig3.update_layout(height=400, margin=dict(l=40, r=40, t=40, b=40))
show_chart(fig3, "Median ideology score of each party, by Congress", "party_median_ideology_trend")

st.markdown("---")
st.caption("Source: Voteview (member and roll-call vote files). Ideology scores are DW-NOMINATE estimates. Party unity rates are computed from individual roll-call votes. The cohesion proxy is derived from distance to the party median within chamber and Congress.")
