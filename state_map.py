"""Members of Congress by state: a summary per state from data/current_seats.csv, and the clickable U.S. map
used on Home and the States page. Hover a state for its delegation; click it to open the States page."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from ui import STATES

# Places that send a non-voting member to the House. DC is drawn on the map; the rest are listed beside it.
DELEGATE_PLACES = ["DC", "PR", "GU", "VI", "AS", "MP"]
OFF_MAP = ["PR", "GU", "VI", "AS", "MP"]


def _count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def party_mix(dem: int, rep: int, ind: int) -> str:
    """'20 Republicans, 10 Democrats', largest group first; a vacant delegation says so."""
    parts = [(rep, "Republican", "Republicans"), (dem, "Democrat", "Democrats"), (ind, "Independent", "Independents")]
    parts = sorted([p for p in parts if p[0]], key=lambda p: -p[0])
    return ", ".join(_count(*p) for p in parts) or "No members seated"


def party_short(dem: int, rep: int, ind: int) -> str:
    """'26R, 13D': the delegation's party counts, largest first, short enough for a metric card."""
    parts = sorted([p for p in [(rep, "R"), (dem, "D"), (ind, "I")] if p[0]], key=lambda p: -p[0])
    return ", ".join(f"{n}{c}" for n, c in parts) or "None"


def state_summary(seats: pd.DataFrame) -> pd.DataFrame:
    """One row per state or territory: senators, House members (or delegate), party counts and the hover text."""
    rows = []
    for abbrev, s in seats.groupby("state_abbrev"):
        sen = int((s["chamber"] == "Senate").sum())
        house = int((s["chamber"] == "House").sum())
        dem, rep = int((s["party"] == "Democrat").sum()), int((s["party"] == "Republican").sum())
        ind = len(s) - dem - rep
        name = STATES.get(abbrev, abbrev)
        if abbrev in DELEGATE_PLACES:
            seats_line = "1 non-voting delegate in the House"
        else:
            seats_line = f"{_count(sen, 'senator', 'senators')}, {_count(house, 'representative', 'representatives')}"
        rows.append({"state": abbrev, "name": name, "senators": sen, "house": house, "members": len(s),
                     "dem": dem, "rep": rep, "ind": ind, "seats_line": seats_line, "mix": party_mix(dem, rep, ind),
                     "short": party_short(dem, rep, ind),
                     # Share of the delegation that is Republican, 0 to 1: the map's color
                     "rep_share": rep / len(s) if len(s) else 0.5})
    return pd.DataFrame(rows).sort_values("name").reset_index(drop=True)


def state_map(summary: pd.DataFrame, height: int = 470) -> go.Figure:
    """Each state shaded by its delegation's party mix, blue (all Democrats) through gray (even) to red (all
    Republicans), in the visitor's light or dark colors. customdata[0] is the state code, for click handling."""
    from theme import mode, tokens
    t = tokens()  # already the light or dark set, so the scale needs no recoloring later
    middle = "#C3C6CC" if mode() == "light" else "#8A8580"  # a neutral gray for an evenly split delegation
    dem, rep = t["dem"], t["rep"]
    on_map = summary[~summary["state"].isin(OFF_MAP)]
    fig = go.Figure(go.Choropleth(
        locations=on_map["state"], locationmode="USA-states", z=on_map["rep_share"], zmin=0, zmax=1,
        colorscale=[[0, dem], [0.5, middle], [1, rep]],
        customdata=on_map[["state", "name", "members", "seats_line", "mix"]].values,
        hovertemplate=("<b>%{customdata[1]}</b><br>%{customdata[2]} members of Congress<br>%{customdata[3]}<br>"
                       "%{customdata[4]}<br><i>Click to see every member</i><extra></extra>"),
        marker=dict(line=dict(color=t["bg"], width=1.2)),
        colorbar=dict(orientation="h", x=0.5, xanchor="center", y=-0.02, yanchor="top", len=0.5, thickness=10,
                      tickvals=[0, 0.5, 1], ticktext=["All Democrats", "Evenly split", "All Republicans"],
                      tickfont=dict(color=t["muted"], size=12), outlinewidth=0),
    ))
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, b=40),
        geo=dict(scope="usa", projection_type="albers usa", bgcolor="rgba(0,0,0,0)", showlakes=False,
                 showland=False, showframe=False, showcoastlines=False),
        dragmode=False,
    )
    return fig


def show_state_map(key: str, title: str = "Members of Congress by state", height: int = 470) -> None:
    """Draw the map with its caption and the off-map delegates. A click on a state, or a pick below the map, opens
    the States page for that place. key keeps each page's map and picker separate."""
    import streamlit as st

    import find_members
    from chart_utils import show_chart

    seats, _ = find_members.load_cached()
    summary = state_summary(seats)
    clicks = f"{key}_clicks"
    event = show_chart(state_map(summary, height), title, "members_by_state",
                       key=f"{key}_{st.session_state.get(clicks, 0)}", on_select="rerun")
    st.caption("Each state is shaded by its delegation's party mix. Hover a state for its senators and "
               "representatives; click it to see every member and their voting record.")
    points = (event or {}).get("selection", {}).get("points", []) if event else []
    code = points[0].get("location") if points else None
    other = st.pills("Delegates from places that are not states", OFF_MAP, format_func=lambda a: STATES[a],
                     key=f"{key}_other_{st.session_state.get(clicks, 0)}")
    code = code or other
    if code:
        st.session_state[clicks] = st.session_state.get(clicks, 0) + 1  # a fresh map, with no selection, next visit
        st.switch_page("views/16_States.py", query_params={"state": code})
