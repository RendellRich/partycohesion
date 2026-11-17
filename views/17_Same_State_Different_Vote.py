"""Same State, Different Vote: how often a state's two senators cast opposite votes on the same roll call, and every
vote where they did. Built by state_splits.py from the Senate vote matrices."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chart_utils import ACCENT, ordinal, show_chart
from state_splits import load as load_splits
from ui import STATES, SITE, bill_label, display_name, explainer, fmt_date, inject_css, intro, metric_row, share_bar
from vote_index import voteview_url

inject_css()


@st.cache_data
def load():
    return load_splits()


def short(name: str) -> str:
    return display_name(name)


def pair_label(r) -> str:
    return f"{r.state}: {short(r.name_a)} and {short(r.name_b)}"


pairs, splits, rollcalls = load()
newest = int(pairs["congress"].max())

st.title("Same State, Different Vote")
intro("Each state's two senators answer to the same voters. This page shows how often they cast opposite votes on "
      "the same roll call, and lists every vote where they did.")
explainer("Senators from different parties split on most party-line votes, so a high number there is expected. "
          "The telling splits are between two senators of the same party, and the votes where one of them broke "
          "with their own party. A split is a fact about the record, not a judgment: a roll call can't show a "
          "senator's reasons.")

congresses = sorted(pairs["congress"].unique(), reverse=True)
congress = st.selectbox("Congress", congresses, key="ss_cong",
                        format_func=lambda c: f"{ordinal(c)} ({2 * c + 1787} to "
                                              f"{'now' if c == newest else 2 * c + 1788})")
now = pairs[pairs["congress"] == congress]
same, mixed = now[now["same_side"]], now[~now["same_side"]]
top = same.sort_values("split_pct", ascending=False).iloc[0] if len(same) else None
split_votes = splits[splits["congress"] == congress]
same_keys = set(zip(same["icpsr_a"], same["icpsr_b"]))
n_same_splits = sum((a, b) in same_keys for a, b in zip(split_votes["icpsr_a"], split_votes["icpsr_b"]))
metric_row([
    ("Same-party senators", f"{same['split_pct'].median():.1f}%" if len(same) else "None",
     f"median share of votes both cast where they split, across {len(same)} pairs"),
    ("Different-party senators", f"{mixed['split_pct'].median():.1f}%" if len(mixed) else "None",
     f"median, across {len(mixed)} pairs" + (f" ({', '.join(sorted(mixed['state'].unique()))})" if len(mixed) else "")),
    ("Most split same-party pair", f"{top['split_pct']:.1f}%" if top is not None else "None",
     f"{short(top['name_a'])} and {short(top['name_b'])} ({top['state']})" if top is not None else ""),
    ("Same-party splits", f"{n_same_splits:,}", f"roll calls in the {ordinal(congress)} Congress"),
])

# The same-party pairs that split most often; click a bar to see that state's votes below
ranked = same.sort_values("split_pct", ascending=False).head(15).iloc[::-1]
if len(ranked):
    fig = go.Figure(go.Bar(
        x=ranked["split_pct"], y=[pair_label(r) for r in ranked.itertuples()], orientation="h",
        marker=dict(color=ACCENT), customdata=ranked[["state", "splits", "both_voted"]].values,
        text=[f"{v:.1f}%" for v in ranked["split_pct"]], textposition="outside", cliponaxis=False,
        hovertemplate=("%{y}<br>Split on %{customdata[1]} of %{customdata[2]} votes both cast (%{x:.1f}%)"
                       "<br><i>Click to see the votes</i><extra></extra>")))
    fig.update_layout(height=120 + 30 * len(ranked), margin=dict(l=10, r=60, b=20),
                      xaxis=dict(ticksuffix="%", title=None, rangemode="tozero"), yaxis=dict(title=None),
                      showlegend=False)
    event = show_chart(fig, f"Same-party senators who split most often, {ordinal(congress)} Congress",
                       f"same_state_splits_{congress}",
                       key=f"ss_bars_{congress}_{st.session_state.get('ss_clicks', 0)}", on_select="rerun")
    st.caption("Share of roll calls both senators voted on where one voted Yea and the other Nay. Votes a senator "
               "missed are left out. Independents are grouped with the party they caucus with.")
    points = (event or {}).get("selection", {}).get("points", []) if event else []
    if points and points[0].get("customdata"):
        st.session_state["ss_clicks"] = st.session_state.get("ss_clicks", 0) + 1
        st.session_state["ss_state"] = points[0]["customdata"][0]
        st.rerun()

# One state's pair and every vote where they split
st.subheader("Every split vote, by state")
states = sorted(now["state"].unique(), key=lambda a: STATES.get(a, a))
wanted = st.query_params.get("state", "").upper()
if "ss_state" not in st.session_state and wanted in states:
    st.session_state["ss_state"] = wanted
if st.session_state.get("ss_state") not in states:
    st.session_state.pop("ss_state", None)
state = st.selectbox("State", states, index=None, format_func=lambda a: STATES.get(a, a),
                     placeholder="Choose a state", key="ss_state")
if not state:
    st.caption("Pick a state, or click a bar above.")
    st.stop()
st.query_params["state"] = state

here = now[now["state"] == state]
for r in here.itertuples():
    kind = "same party" if r.same_side else "different parties"
    st.markdown(f"**{short(r.name_a)}** ({r.party_a[0]}) and **{short(r.name_b)}** ({r.party_b[0]}), {kind}: "
                f"split on **{r.splits:,}** of {r.both_voted:,} votes both cast ({r.split_pct:.1f}%).")
share_bar(f"How often {STATES.get(state, state)}'s senators vote opposite ways, on PartyCohesion",
          "Same_State_Different_Vote", {"state": state})

votes = split_votes[split_votes["state"] == state].merge(
    rollcalls[["congress", "rollnumber", "date", "bill_number", "vote_question", "vote_desc", "vote_result",
               "party_unity_vote"]], on=["congress", "rollnumber"], how="left")
names = {r.icpsr_a: short(r.name_a) for r in here.itertuples()} | {r.icpsr_b: short(r.name_b) for r in here.itertuples()}

c1, c2 = st.columns([1.4, 1])
query = c1.text_input("Search the votes", placeholder="e.g. H.R. 1 or nomination", key="ss_query")
only_broke = c2.toggle("Only votes where one of them broke with their party", value=bool(here["same_side"].all()),
                       key=f"ss_broke_{state}")
if only_broke:
    votes = votes[votes["broke_a"] | votes["broke_b"]]
if query.strip():
    q = query.strip().lower()
    code = q.replace(".", "").replace(" ", "").upper()
    votes = votes[(votes["bill_number"].fillna("") == code)
                  | votes["vote_desc"].fillna("").str.lower().str.contains(q, regex=False)
                  | votes["vote_question"].fillna("").str.lower().str.contains(q, regex=False)]
votes = votes.sort_values(["date", "rollnumber"], ascending=False)


def broke_text(r) -> str:
    who = [names[i] for i, flag in ((r.icpsr_a, r.broke_a), (r.icpsr_b, r.broke_b)) if flag]
    return " and ".join(who) if who else "Neither (the parties split)"


st.caption(f"{len(votes):,} votes")
st.dataframe(pd.DataFrame({
    "Date": [fmt_date(d) for d in votes["date"]],
    "Bill": [bill_label(b) if isinstance(b, str) else "" for b in votes["bill_number"]],
    "Vote": [f"{d} ({q})" if isinstance(d, str) and d else str(q) for d, q in zip(votes["vote_desc"],
                                                                                 votes["vote_question"])],
    "How they voted": [f"{names[a]} {va}, {names[b]} {vb}" for a, b, va, vb in
                       zip(votes["icpsr_a"], votes["icpsr_b"], votes["vote_a"], votes["vote_b"])],
    "Broke with their party": [broke_text(r) for r in votes.itertuples()],
    "Result": votes["vote_result"].fillna(""),
    "Roll call": [voteview_url(c, "Senate", r) for c, r in zip(votes["congress"], votes["rollnumber"])],
}), hide_index=True, width="stretch", height=480,
    column_config={"Vote": st.column_config.TextColumn(width="large"),
                   "Roll call": st.column_config.LinkColumn(display_text="Voteview")})
st.caption("\"Broke with their party\" means the senator voted against the majority of the party they caucus with "
           "on that roll call. Member pages: " + ", ".join(
               f"[{short(n)}]({SITE}/Member_Explorer?member={b})" for n, b in
               {(r.name_a, r.bioguide_a) for r in here.itertuples()} | {(r.name_b, r.bioguide_b) for r in here.itertuples()}
               if isinstance(b, str)) + ".")
st.caption("Source: Voteview roll-call records. Only Yea and Nay votes count; paired and announced positions don't.")
