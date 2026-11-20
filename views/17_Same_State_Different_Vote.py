"""Same State, Different Vote: how often two members of Congress from the same state cast opposite votes on the
same roll call, and every vote where they did. Senate: each state's two senators. House: members of the same party
from the same state. Built by state_splits.py from the vote matrices."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chart_utils import ACCENT, ordinal, show_chart
from state_splits import MIN_SHARED, load_all, member_summary, pair_votes
from ui import STATES, SITE, bill_label, display_name, explainer, fmt_date, html_table, inject_css, intro, metric_row, party_tag, share_bar
from vote_index import voteview_url

inject_css()


@st.cache_data
def votes_for(chamber: str, congress: int, key: str) -> pd.DataFrame:
    members, rollcalls, matrices, pairs = load_all()
    pair = pairs[(pairs["chamber"] == chamber) & (pairs["congress"] == congress) & (pairs["key"] == key)].iloc[0]
    return pair_votes(pair, members, rollcalls, matrices[chamber])


def short(name: str) -> str:
    return display_name(name)


def pair_name(r) -> str:
    return f"{short(r.name_a)} and {short(r.name_b)}"


def one_per_member(ranked: pd.DataFrame, n: int) -> pd.DataFrame:
    """The top pairs, skipping any pair with a member already shown, so one member can't fill the chart."""
    seen, keep = set(), []
    for r in ranked.itertuples():
        if r.icpsr_a in seen or r.icpsr_b in seen:
            continue
        keep.append(r.Index)
        seen.update({r.icpsr_a, r.icpsr_b})
        if len(keep) == n:
            break
    return ranked.loc[keep]


members, rollcalls, matrices, pairs = load_all()

st.title("Same State, Different Vote")
intro("Members of Congress from the same state answer to many of the same voters. This page shows how often two of "
      "them cast opposite votes on the same roll call, and lists every vote where they did.")
explainer("Members from different parties split on most party-line votes, so a high number there is expected. The "
          "telling splits are between two members of the same party, and the votes where one of them broke with "
          "their own party. A split is a fact about the record, not a judgment: a roll call can't show a member's "
          "reasons.")

wanted_chamber = "House" if st.query_params.get("chamber", "").lower() == "house" else "Senate"
c1, c2 = st.columns([1, 2])
chamber = c1.segmented_control("Chamber", ["Senate", "House"], default=wanted_chamber, key="ss_chamber") or "Senate"
in_chamber = pairs[pairs["chamber"] == chamber]
newest = int(in_chamber["congress"].max())
congress = c2.selectbox("Congress", sorted(in_chamber["congress"].unique(), reverse=True), key=f"ss_cong_{chamber}",
                        format_func=lambda c: f"{ordinal(c)} ({2 * c + 1787} to "
                                              f"{'now' if c == newest else 2 * c + 1788})")
now = in_chamber[in_chamber["congress"] == congress]
same = now[now["same_side"]]
ranked = same[same["both_voted"] >= MIN_SHARED[chamber]].sort_values("split_pct", ascending=False)
top = ranked.iloc[0] if len(ranked) else None

if chamber == "Senate":
    mixed = now[~now["same_side"]]
    cards = [
        ("Same-party senators", f"{same['split_pct'].median():.1f}%" if len(same) else "No pairs",
         f"median share of votes both cast where they split, across {len(same)} pairs"),
        ("Different-party senators", f"{mixed['split_pct'].median():.1f}%" if len(mixed) else "No pairs",
         f"median, across {len(mixed)} pairs" + (f" ({', '.join(sorted(mixed['state'].unique()))})" if len(mixed) else "")),
    ]
else:
    cards = [
        ("Same-party House pairs", f"{len(same):,}", f"two members of one party from one state, in the "
                                                     f"{ordinal(congress)} Congress"),
        ("Typical pair", f"{same['split_pct'].median():.1f}%" if len(same) else "No pairs",
         "median share of votes both cast where they split"),
    ]
cards += [
    ("Most split same-party pair", f"{top['split_pct']:.1f}%" if top is not None else "No pairs",
     f"{short(top['name_a'])} and {short(top['name_b'])} ({top['state']})" if top is not None else ""),
    ("Same-party splits", f"{int(same['splits'].sum()):,}", f"times two same-party members from one state split, "
                                                           f"{ordinal(congress)} Congress"),
]
metric_row(cards)

# The same-party pairs that split most often; click a bar to see that pair's votes below
shown = one_per_member(ranked, 15) if chamber == "House" else ranked.head(15)
shown = shown.iloc[::-1]
if len(shown):
    fig = go.Figure(go.Bar(
        x=shown["split_pct"], y=[f"{r.state}: {pair_name(r)}" for r in shown.itertuples()], orientation="h",
        marker=dict(color=ACCENT), customdata=shown[["state", "key", "splits", "both_voted"]].values,
        text=[f"{v:.1f}%" for v in shown["split_pct"]], textposition="outside", cliponaxis=False,
        hovertemplate=("%{y}<br>Split on %{customdata[2]} of %{customdata[3]} votes both cast (%{x:.1f}%)"
                       "<br><i>Click to see the votes</i><extra></extra>")))
    fig.update_layout(height=120 + 30 * len(shown), margin=dict(l=10, r=60, b=20),
                      xaxis=dict(ticksuffix="%", title=None, rangemode="tozero"), yaxis=dict(title=None),
                      showlegend=False)
    noun = "senators" if chamber == "Senate" else "House members"
    event = show_chart(fig, f"Same-party {noun} from one state who split most often, {ordinal(congress)} Congress",
                       f"same_state_splits_{chamber.lower()}_{congress}",
                       key=f"ss_bars_{chamber}_{congress}_{st.session_state.get('ss_clicks', 0)}", on_select="rerun")
    st.caption("Share of roll calls both members voted on where one voted Yea and the other Nay. Votes a member "
               f"missed are left out, and pairs with fewer than {MIN_SHARED[chamber]} votes in common are not ranked. "
               "Independents are grouped with the party they caucus with."
               + (" Each member appears once, in their most split pair, so one member can't fill the chart."
                  if chamber == "House" else ""))
    points = (event or {}).get("selection", {}).get("points", []) if event else []
    if points and points[0].get("customdata"):
        st.session_state["ss_clicks"] = st.session_state.get("ss_clicks", 0) + 1
        st.session_state[f"ss_state_{chamber}"] = points[0]["customdata"][0]
        st.session_state[f"ss_pair_{chamber}"] = points[0]["customdata"][1]
        st.rerun()

# House: the members who split most, on average, from their own state's same-party colleagues
if chamber == "House":
    people = member_summary(now)
    loners = people[people["colleagues"] >= 2].head(15).iloc[::-1]
    if len(loners):
        fig = go.Figure(go.Bar(
            x=loners["avg_split"], orientation="h",
            y=[f"{short(r.name)} ({r.party[0]}-{r.state})" for r in loners.itertuples()],
            marker=dict(color=ACCENT), text=[f"{v:.1f}%" for v in loners["avg_split"]], textposition="outside",
            cliponaxis=False,
            customdata=[[r.state, r.colleagues, r.side, short(r.most_split_with), r.most_split_pct]
                        for r in loners.itertuples()],
            hovertemplate=("%{y}<br>Splits on %{x:.1f}% of votes, on average, with %{customdata[1]} "
                           "%{customdata[2]} colleagues from their state<br>Most with %{customdata[3]} "
                           "(%{customdata[4]:.1f}%)<br><i>Click to see the votes</i><extra></extra>")))
        fig.update_layout(height=120 + 30 * len(loners), margin=dict(l=10, r=60, b=20),
                          xaxis=dict(ticksuffix="%", title=None, rangemode="tozero"), yaxis=dict(title=None),
                          showlegend=False)
        own = show_chart(fig, f"House members who split most from their own state's party, {ordinal(congress)} Congress",
                         f"same_state_members_{congress}",
                         key=f"ss_people_{congress}_{st.session_state.get('ss_clicks', 0)}", on_select="rerun")
        st.caption(f"Each member's average split with the colleagues of their party from their state, among those they "
                   f"shared at least {MIN_SHARED['House']} votes with. Members with fewer than two such colleagues are "
                   f"left out. The typical member splits on {people['avg_split'].median():.1f}% of votes with their "
                   "state's party colleagues.")
        hit = (own or {}).get("selection", {}).get("points", []) if own else []
        if hit and hit[0].get("customdata"):
            st.session_state["ss_clicks"] = st.session_state.get("ss_clicks", 0) + 1
            st.session_state["ss_state_House"] = hit[0]["customdata"][0]
            st.session_state.pop("ss_pair_House", None)
            st.rerun()

# One state's pairs and every vote where a pair split
st.header("Every split vote, by state")
states = sorted(now["state"].unique(), key=lambda a: STATES.get(a, a))
state_key = f"ss_state_{chamber}"
wanted = st.query_params.get("state", "").upper()
if state_key not in st.session_state and wanted in states:
    st.session_state[state_key] = wanted
if st.session_state.get(state_key) not in states:
    st.session_state.pop(state_key, None)
state = st.selectbox("State", states, index=None, format_func=lambda a: STATES.get(a, a),
                     placeholder="Choose a state", key=state_key)
if not state:
    st.caption("Pick a state, or click a bar above.")
    st.stop()
st.query_params["state"] = state
st.query_params["chamber"] = chamber.lower()

here = now[now["state"] == state].sort_values("split_pct", ascending=False)
if chamber == "House":
    people_here = member_summary(here)
    if len(people_here):
        rows = [[f"{short(r.name)}", party_tag(r.party), f"{r.avg_split:.1f}%", str(r.colleagues),
                 f"{short(r.most_split_with)} ({r.most_split_pct:.1f}%)"]
                for r in people_here.sort_values(["side", "avg_split"], ascending=[True, False]).itertuples()]
        html_table(["Member", "Party", "Average split with their state's party", "Colleagues compared",
                    "Splits most with"], rows, raw_cols=(1,))
    st.caption(f"{len(here)} same-party pairs from {STATES.get(state, state)} in the House, most split first.")
pair_key = f"ss_pair_{chamber}"
if st.session_state.get(pair_key) not in set(here["key"]):
    st.session_state[pair_key] = here["key"].iloc[0]
labels = {r.key: f"{pair_name(r)}: split on {r.splits:,} of {r.both_voted:,} votes ({r.split_pct:.1f}%)"
          for r in here.itertuples()}
if len(here) > 1:
    key = st.selectbox("Pair", list(labels), format_func=labels.get, key=pair_key)
else:
    key = here["key"].iloc[0]
pair = here[here["key"] == key].iloc[0]
kind = "same party" if pair["same_side"] else "different parties"
st.markdown(f"**{short(pair['name_a'])}** ({pair['party_a'][0]}) and **{short(pair['name_b'])}** "
            f"({pair['party_b'][0]}), {kind}: split on **{pair['splits']:,}** of {pair['both_voted']:,} votes both "
            f"cast ({pair['split_pct']:.1f}%).")
share_bar(f"How often members of Congress from {STATES.get(state, state)} vote opposite ways, on PartyCohesion",
          "Same_State_Different_Vote", {"state": state, "chamber": chamber.lower()})

votes = votes_for(chamber, int(congress), key)
names = {"a": short(pair["name_a"]), "b": short(pair["name_b"])}
c1, c2 = st.columns([1.4, 1])
query = c1.text_input("Search the votes", placeholder="e.g. H.R. 1 or nomination", key="ss_query")
only_broke = c2.toggle("Only votes where one of them broke with their party", value=bool(pair["same_side"]),
                       key=f"ss_broke_{chamber}_{key}")
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
    who = [names[w] for w, flag in (("a", r.broke_a), ("b", r.broke_b)) if flag]
    return " and ".join(who) if who else "Neither (the parties split)"


st.caption(f"{len(votes):,} votes")
st.dataframe(pd.DataFrame({
    "Date": [fmt_date(d) for d in votes["date"]],
    "Bill": [bill_label(b) if isinstance(b, str) else "" for b in votes["bill_number"]],
    "Vote": [f"{d} ({q})" if isinstance(d, str) and d else str(q) for d, q in zip(votes["vote_desc"],
                                                                                 votes["vote_question"])],
    "How they voted": [f"{names['a']} {va}, {names['b']} {vb}" for va, vb in zip(votes["vote_a"], votes["vote_b"])],
    "Broke with their party": [broke_text(r) for r in votes.itertuples()],
    "Result": votes["vote_result"].fillna(""),
    "Roll call": [voteview_url(congress, chamber, r) for r in votes["rollnumber"]],
}), hide_index=True, width="stretch", height=480,
    column_config={"Vote": st.column_config.TextColumn(width="large"),
                   "Roll call": st.column_config.LinkColumn(display_text="Voteview")})
links = [f"[{short(n)}]({SITE}/Member_Explorer?member={b})" for n, b in
         ((pair["name_a"], pair["bioguide_a"]), (pair["name_b"], pair["bioguide_b"])) if isinstance(b, str)]
st.caption("\"Broke with their party\" means the member voted against the majority of the party they caucus with "
           "on that roll call." + (f" Member pages: {', '.join(links)}." if links else ""))
st.caption("Source: Voteview roll-call records. Only Yea and Nay votes count; paired and announced positions don't.")
