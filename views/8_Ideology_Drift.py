"""Ideology Drift – how far each member's voting position moved over time, compared with their party."""

import pandas as pd
import plotly.express as px
import streamlit as st
from pathlib import Path
from chart_utils import show_chart, ordinal, PARTY_COLORS, MUTED, ACCENT

DATA_DIR = Path(__file__).parent.parent / "data"
NOISE = 0.10  # per-Congress scores move this much from noise alone; smaller changes aren't flagged
DELEGATE_AREAS = {"DC", "PR", "VI", "GU", "AS", "MP"}


@st.cache_data
def load():
    m = pd.read_csv(DATA_DIR / "members_processed.csv").dropna(subset=["nokken_poole_dim1"])
    m = m[m["party"].isin(["Democrat", "Republican"])]
    # Delegates (D.C. and territories) vote on few questions, so their scores are mostly noise
    m = m[~m["state_abbrev"].isin(DELEGATE_AREAS)]
    party_median = (m.groupby(["congress", "chamber", "party"])["nokken_poole_dim1"].median()
                    .rename("party_median").reset_index())
    return m.merge(party_median, on=["congress", "chamber", "party"])


def describe(change: float) -> str:
    if abs(change) < NOISE:
        return "No clear movement"
    return "More conservative" if change > 0 else "More liberal"


m = load()
newest = int(m["congress"].max())

st.title("Ideology Drift")
st.markdown(
    "How far has each member's voting moved over their time in Congress, and did they move **with their party** or "
    "**on their own**? Scores are Voteview's per-Congress ideology estimates: negative is more liberal, positive is "
    "more conservative."
)
with st.expander("How to read this page"):
    st.markdown(f"""
- **Own change:** the member's score in their latest Congress minus their score in their first Congress here.
- **Party change:** how much their party's median member moved over the same Congresses, in the same chamber.
- **Change vs. party:** own change minus party change. This is the part of the movement that was the member's own,
  not the whole party shifting.
- These per-Congress scores (Nokken-Poole) are estimated separately for each Congress, so they bounce around a bit.
  Changes smaller than **{NOISE:.2f}** are labeled "No clear movement".
- **A known quirk:** these scores only see Yea and Nay. A member who votes No because a bill *doesn't go far enough*
  (for example, a libertarian Republican opposing a Republican spending bill) looks like they voted with the other
  party, so their score can drift toward the center even if their views didn't. Read movement alongside the actual votes.
- Delegates from D.C. and the territories are left out: they vote on few questions, so their scores are mostly noise.
- Members are compared within the chamber they served in. Someone who moved from the House to the Senate is measured
  over the Congresses in their latest chamber.
""")

f1, f2, f3, f4 = st.columns([1, 1, 1, 1])
with f1:
    chamber = st.selectbox("Chamber", ["Both", "House", "Senate"], key="dr_cham")
with f2:
    party = st.selectbox("Party", ["Both", "Democrat", "Republican"], key="dr_party")
with f3:
    min_congresses = st.selectbox("Served at least", [2, 3, 4, 5], index=1, format_func=lambda n: f"{n} Congresses", key="dr_min")
with f4:
    current_only = st.toggle(f"Serving in the {ordinal(newest)} Congress", value=True, key="dr_current")

# One row per member over the Congresses in their most recent chamber
last_chamber = m.sort_values("congress").groupby("icpsr")["chamber"].last().rename("last_chamber")
mm = m.merge(last_chamber, on="icpsr")
mm = mm[mm["chamber"] == mm["last_chamber"]].sort_values("congress")
first = mm.groupby("icpsr").first()
last = mm.groupby("icpsr").last()
count = mm.groupby("icpsr").size()
drift = pd.DataFrame({
    "name": last["name"], "party": last["party"], "state": last["state_abbrev"], "chamber": last["chamber"],
    "first": first["congress"], "last": last["congress"], "congresses": count,
    "start": first["nokken_poole_dim1"], "end": last["nokken_poole_dim1"],
    "own_change": last["nokken_poole_dim1"] - first["nokken_poole_dim1"],
    "party_change": last["party_median"] - first["party_median"],
}).reset_index()
drift["vs_party"] = drift["own_change"] - drift["party_change"]
drift["direction"] = drift["vs_party"].apply(describe)

view = drift[drift["congresses"] >= min_congresses]
if chamber != "Both":
    view = view[view["chamber"] == chamber]
if party != "Both":
    view = view[view["party"] == party]
if current_only:
    view = view[view["last"] == newest]

if view.empty:
    st.info("No members match these filters.")
    st.stop()

c1, c2, c3 = st.columns(3)
c1.metric("Members", f"{len(view):,}")
c2.metric("Moved more liberal than their party", f"{(view['direction'] == 'More liberal').mean() * 100:.0f}%")
c3.metric("Moved more conservative than their party", f"{(view['direction'] == 'More conservative').mean() * 100:.0f}%")

fig = px.scatter(view, x="party_change", y="own_change", color="party", hover_name="name",
                 hover_data={"state": True, "first": True, "last": True, "vs_party": ":.2f", "party_change": ":.2f", "own_change": ":.2f"},
                 color_discrete_map=PARTY_COLORS,
                 labels={"party_change": "Party's change", "own_change": "Member's own change", "party": ""})
lo = min(view["party_change"].min(), view["own_change"].min()) - 0.05
hi = max(view["party_change"].max(), view["own_change"].max()) + 0.05
fig.add_shape(type="line", x0=lo, y0=lo, x1=hi, y1=hi, line=dict(color=MUTED, dash="dot"))
fig.add_annotation(x=hi, y=hi, text="moved with party", showarrow=False, xanchor="right", yanchor="bottom",
                   font=dict(size=11, color=MUTED))
fig.update_layout(height=460)
show_chart(fig, "Each member's ideology change vs. their party's change", "ideology_drift_scatter")
st.caption("Points on the dotted line moved exactly as much as their party. Above the line = more conservative than "
           "their party's shift; below = more liberal.")

table = view.reindex(view["vs_party"].abs().sort_values(ascending=False).index)
st.dataframe(pd.DataFrame({
    "Name": table["name"], "Party-State": table["party"].str[0] + "-" + table["state"], "Chamber": table["chamber"],
    "Congresses": [f"{ordinal(a)}–{ordinal(b)}" for a, b in zip(table["first"], table["last"])],
    "Start": table["start"].round(2), "Latest": table["end"].round(2), "Own change": table["own_change"].round(2),
    "Party change": table["party_change"].round(2), "Change vs. party": table["vs_party"].round(2),
    "Direction vs. party": table["direction"],
}), width="stretch", hide_index=True, height=420)

st.markdown("---")
st.subheader("One member over time")
opts = {f"{r.name} ({r.party[0]}-{r.state}, {r.chamber})": r.icpsr for r in view.sort_values("name").itertuples()}
pick = st.selectbox("Member", list(opts), index=None, placeholder="Type a name…", key="dr_member")
if pick:
    rows = mm[mm["icpsr"] == opts[pick]]
    long = pd.concat([
        rows[["congress", "nokken_poole_dim1"]].rename(columns={"nokken_poole_dim1": "score"}).assign(Line=pick.split(",")[0]),
        rows[["congress", "party_median"]].rename(columns={"party_median": "score"}).assign(Line=f"{rows['party'].iloc[-1]} median"),
    ])
    fig2 = px.line(long, x="congress", y="score", color="Line", markers=True,
                   color_discrete_sequence=[ACCENT, MUTED], labels={"congress": "Congress", "score": "Ideology score", "Line": ""})
    fig2.update_layout(height=360, xaxis=dict(dtick=1))
    show_chart(fig2, f"Ideology over time: {pick.split(' (')[0]}", f"ideology_drift_{pick.split(',')[0].lower().replace(' ', '_')}")

st.caption("Source: Voteview Nokken-Poole per-Congress ideology estimates (first dimension).")
