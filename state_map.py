"""Members of Congress by state: a summary per state from data/current_seats.csv, and the clickable U.S. map
used on Home and the States page. Hover a state for its delegation; click it to open the States page."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from ui import STATES

DATA_DIR = Path(__file__).parent / "data"

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


def member_records(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Each member's latest party unity, missed votes and Position Flips label, keyed by Bioguide ID."""
    from flip_utils import add_chamber_control, flip_scores
    members = pd.read_csv(data_dir / "members_processed.csv")
    latest = members.sort_values("congress").drop_duplicates("icpsr", keep="last")
    missed = pd.read_csv(data_dir / "missed_votes.csv")
    missed = missed.sort_values("congress").drop_duplicates(["icpsr"], keep="last")
    missed["missed_pct"] = 100 * missed["missed"] / missed["eligible"]
    flips = flip_scores(add_chamber_control(pd.read_csv(data_dir / "flip_member_votes.csv"), members))
    out = (latest[["icpsr", "bioguide_id", "congress", "party_unity_pct"]]
           .merge(missed[["icpsr", "missed_pct"]], on="icpsr", how="left")
           .merge(flips[["icpsr", "label"]], on="icpsr", how="left"))
    return out.dropna(subset=["bioguide_id"]).drop_duplicates("bioguide_id", keep="last").set_index("bioguide_id")


_cached_records = None


def load_records() -> pd.DataFrame:
    """member_records(), cached for the life of the server (cleared when the data files change)."""
    global _cached_records
    if _cached_records is None:
        import streamlit as st
        _cached_records = st.cache_data(member_records)
    return _cached_records()


def state_summary(seats: pd.DataFrame, records: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per state or territory: senators, House members (or delegate), party counts, the hover text and,
    when records are given, the delegation's averages for the map's other colorings."""
    if records is not None:
        seats = seats.join(records[["party_unity_pct", "missed_pct", "label"]], on="bioguide_id")
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
        row = {"state": abbrev, "name": name, "senators": sen, "house": house, "members": len(s),
               "dem": dem, "rep": rep, "ind": ind, "seats_line": seats_line, "mix": party_mix(dem, rep, ind),
               "short": party_short(dem, rep, ind),
               # Share of the delegation that is Republican, 0 to 1: the default coloring
               "rep_share": rep / len(s) if len(s) else 0.5}
        if records is not None:
            # Delegates don't cast roll-call votes, so a delegate-only place has no averages
            voting = s if abbrev not in DELEGATE_PLACES else s.iloc[0:0]
            unity, missed = voting["party_unity_pct"].dropna(), voting["missed_pct"].dropna()
            scored = voting["label"][voting["label"].notna() & (voting["label"] != "Not enough votes")]
            row.update({
                "avg_unity": unity.mean() if len(unity) else None, "n_unity": len(unity),
                "avg_missed": missed.mean() if len(missed) else None, "n_missed": len(missed),
                # Too few comparable votes in a delegation would make the share swing on one member
                "consistent": 100 * (scored == "Consistent").mean() if len(scored) >= 2 else None,
                "n_consistent": int((scored == "Consistent").sum()), "n_flip": len(scored),
            })
        rows.append(row)
    return pd.DataFrame(rows).sort_values("name").reset_index(drop=True)


# The map's colorings. Party mix runs between the two party colors; the others are one hue, light to dark, with
# darker meaning more of what the label names.
COLOR_BY = {
    "Party mix": {"title": "Members of Congress by state", "column": "rep_share",
                  "caption": "Each state is shaded by its delegation's party mix."},
    "Party unity": {"title": "Average party unity of each state's members", "column": "avg_unity", "fmt": "{:.1f}%",
                    "line": "Average party unity: {value}, across {n} members",
                    "low": "Breaks with party more", "high": "Votes with party more",
                    "caption": "Party unity is the share of party-line votes each member cast with their own party, "
                               "from their latest Congress, averaged across the state's members. Every state is "
                               "high, so the colors stretch across the actual range."},
    "Missed votes": {"title": "Share of roll calls missed by each state's members", "column": "avg_missed",
                     "fmt": "{:.1f}%", "line": "Missed votes: {value} on average, across {n} members",
                     "low": "Misses fewer votes", "high": "Misses more votes",
                     "caption": "The share of roll calls held while they served that each member did not vote on, "
                                "from their latest Congress, averaged across the state's members."},
    "Position Flips": {"title": "Share of each state's members who vote the same way under either party's president",
                       "column": "consistent", "fmt": "{:.0f}%", "line": "Consistent on Position Flips: {value} "
                       "({c} of {n} members with enough comparable votes)",
                       "low": "Fewer consistent", "high": "More consistent",
                       "caption": "The share of members, among those with enough comparable votes, who cast the same "
                                  "vote on debt limits, government funding, disaster aid and war powers under "
                                  "presidents of both parties. States with fewer than two such members are gray."},
}


def _metric_line(row, spec: dict) -> str:
    value = row[spec["column"]]
    if value is None or pd.isna(value):
        return ("Delegates don't vote on final passage, so no voting record" if row["state"] in DELEGATE_PLACES
                else "Not enough comparable votes yet")
    n = {"avg_unity": row.get("n_unity"), "avg_missed": row.get("n_missed"), "consistent": row.get("n_flip")}
    return spec["line"].format(value=spec["fmt"].format(value), n=n[spec["column"]], c=row.get("n_consistent"))


def state_map(summary: pd.DataFrame, color_by: str = "Party mix", height: int = 470) -> go.Figure:
    """Each state shaded by color_by (a key of COLOR_BY), in the visitor's light or dark colors. Party mix runs from
    blue (all Democrats) through gray (even) to red (all Republicans); the averages use one purple, darker for more.
    customdata[0] is the state code, for click handling."""
    from theme import mode, tokens
    t = tokens()  # already the light or dark set, so the scale needs no recoloring later
    light = mode() == "light"
    spec = COLOR_BY[color_by]
    on_map = summary[~summary["state"].isin(OFF_MAP)].copy()
    tick = dict(tickfont=dict(color=t["muted"], size=12), outlinewidth=0, orientation="h", x=0.5, xanchor="center",
                y=-0.02, yanchor="top", len=0.5, thickness=10)
    hover = ("<b>%{customdata[1]}</b><br>%{customdata[2]} members of Congress<br>%{customdata[3]}<br>"
             "%{customdata[4]}<br>%{customdata[5]}<br><i>Click to see every member</i><extra></extra>")
    border = dict(line=dict(color=t["bg"], width=1.2))
    fig = go.Figure()
    if color_by == "Party mix":
        middle = "#C3C6CC" if light else "#8A8580"  # a neutral gray for an evenly split delegation
        on_map["metric"] = ""
        fig.add_trace(go.Choropleth(
            locations=on_map["state"], locationmode="USA-states", z=on_map["rep_share"], zmin=0, zmax=1,
            colorscale=[[0, t["dem"]], [0.5, middle], [1, t["rep"]]],
            customdata=on_map[["state", "name", "members", "seats_line", "mix", "metric"]].values,
            hovertemplate=hover.replace("<br>%{customdata[5]}", ""), marker=border,
            colorbar=dict(tickvals=[0, 0.5, 1], ticktext=["All Democrats", "Evenly split", "All Republicans"], **tick)))
    else:
        col = spec["column"]
        on_map["metric"] = [_metric_line(r, spec) for _, r in on_map.iterrows()]
        have = on_map[on_map[col].notna()]
        none = on_map[on_map[col].isna()]
        lo, hi = float(have[col].min()), float(have[col].max())
        ramp = [[0, "#D9CFEF"], [1, "#4B2E8C"]] if light else [[0, "#3D3654"], [1, "#D8C9FF"]]
        fig.add_trace(go.Choropleth(
            locations=have["state"], locationmode="USA-states", z=have[col], zmin=lo, zmax=hi, colorscale=ramp,
            customdata=have[["state", "name", "members", "seats_line", "mix", "metric"]].values,
            hovertemplate=hover, marker=border,
            colorbar=dict(tickvals=[lo, hi], ticktext=[f"{spec['low']} ({spec['fmt'].format(lo)})",
                                                       f"{spec['high']} ({spec['fmt'].format(hi)})"], **tick)))
        if len(none):
            fig.add_trace(go.Choropleth(
                locations=none["state"], locationmode="USA-states", z=[0] * len(none), showscale=False,
                colorscale=[[0, t["grid"]], [1, t["grid"]]],
                customdata=none[["state", "name", "members", "seats_line", "mix", "metric"]].values,
                hovertemplate=hover, marker=border))
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, b=40), showlegend=False,
        geo=dict(scope="usa", projection_type="albers usa", bgcolor="rgba(0,0,0,0)", showlakes=False,
                 showland=False, showframe=False, showcoastlines=False),
        dragmode=False,
    )
    return fig


def show_state_map(key: str, title: str | None = None, height: int = 470) -> None:
    """Draw the map with its "Color by" switch, caption and the off-map delegates. A click on a state, or a pick
    below the map, opens the States page for that place. key keeps each page's map and picker separate; title
    replaces the coloring's own title."""
    import streamlit as st

    import find_members
    from chart_utils import show_chart

    seats, _ = find_members.load_cached()
    summary = state_summary(seats, load_records())
    color_by = st.segmented_control("Color by", list(COLOR_BY), default="Party mix", key=f"{key}_color") or "Party mix"
    spec = COLOR_BY[color_by]
    clicks = f"{key}_clicks"
    event = show_chart(state_map(summary, color_by, height), title or spec["title"],
                       f"states_{color_by.lower().replace(' ', '_')}",
                       key=f"{key}_{color_by}_{st.session_state.get(clicks, 0)}", on_select="rerun")
    st.caption(spec["caption"] + " Hover a state for its senators and representatives; click it to see every "
               "member and their voting record.")
    points = (event or {}).get("selection", {}).get("points", []) if event else []
    code = points[0].get("location") if points else None
    other = st.pills("Delegates from places that are not states", OFF_MAP, format_func=lambda a: STATES[a],
                     key=f"{key}_other_{st.session_state.get(clicks, 0)}")
    code = code or other
    if code:
        st.session_state[clicks] = st.session_state.get(clicks, 0) + 1  # a fresh map, with no selection, next visit
        st.switch_page("views/16_States.py", query_params={"state": code})


def _blend(c1: str, c2: str, t: float) -> str:
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def outline_svg(state: str, rep_share: float, width: int = 132) -> str:
    """The state's outline as inline SVG, filled with its party-mix color from the map (blue, gray or red), or ''
    for a place with no outline (the territories). Shapes come from data/state_shapes.json."""
    import json

    from theme import mode, tokens
    global _shapes
    try:
        _shapes
    except NameError:
        _shapes = json.loads((DATA_DIR / "state_shapes.json").read_text())
    shape = _shapes.get(state)
    if not shape:
        return ""
    t = tokens()
    middle = "#C3C6CC" if mode() == "light" else "#8A8580"
    fill = (_blend(t["dem"], middle, rep_share / 0.5) if rep_share <= 0.5
            else _blend(middle, t["rep"], (rep_share - 0.5) / 0.5))
    w, h = shape["w"], shape["h"]
    return (f'<svg viewBox="-2 -2 {w + 4} {h + 4}" width="{width}" height="{round(width * (h + 4) / (w + 4))}" '
            f'role="img" aria-label="Outline of {STATES.get(state, state)}"><path d="{shape["d"]}" fill="{fill}" '
            f'stroke="{t["text"]}" stroke-width="0.8" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></svg>')
