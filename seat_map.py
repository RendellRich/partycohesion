"""The Home page's chamber seat map: one dot per member, arranged left to right by ideology score."""

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from chart_utils import ACCENT, BG, MUTED, PARTY_COLORS


def seat_positions(n: int, rows: int, inner: float = 0.45) -> pd.DataFrame:
    """x, y and angle for n seats in a half circle of `rows` rows, seats spread in proportion to row length."""
    radii = np.linspace(inner, 1.0, rows)
    counts = np.floor(n * radii / radii.sum()).astype(int)
    counts[-1] += n - counts.sum()  # rounding leftovers go to the outer row
    seats = []
    for r, c in zip(radii, counts):
        for i in range(c):
            a = math.pi * (1 - (i + 0.5) / c) if c > 1 else math.pi / 2
            seats.append((r * math.cos(a), r * math.sin(a), a, r))
    out = pd.DataFrame(seats, columns=["x", "y", "angle", "r"])
    # Fill seats from the left edge to the right, inner rows first within each slice of the arc
    return out.sort_values(["angle", "r"], ascending=[False, True]).reset_index(drop=True)


def seat_map(members: pd.DataFrame, chamber: str, highlight=None, highlight_name: str = "") -> go.Figure:
    """members: one row per member with icpsr, name, party, state_abbrev, nominate_dim1, party_unity_pct, bioguide_id
    and label. With highlight (an icpsr), that member's seat is enlarged and ringed, the rest are dimmed, and
    highlight_name labels the seat."""
    m = members.sort_values("nominate_dim1", na_position="last").reset_index(drop=True)
    rows = 12 if chamber == "House" else 6
    seats = seat_positions(len(m), rows)
    m = pd.concat([m, seats], axis=1)
    size = 10 if chamber == "House" else 17
    fig = go.Figure()
    for party in ("Democrat", "Independent", "Republican"):
        p = m[m["party"] == party]
        if p.empty:
            continue
        unity = p["party_unity_pct"].map(lambda v: f"{v:.0f}%" if pd.notna(v) else "not available")
        fig.add_trace(go.Scatter(
            x=p["x"], y=p["y"], mode="markers", name=f"{party}s ({len(p)})" if party != "Independent" else f"Independents ({len(p)})",
            marker=dict(size=size, color=PARTY_COLORS[party], line=dict(color=BG, width=1.5),
                        opacity=0.35 if highlight is not None else 1),
            customdata=np.stack([p["label"], unity, p["bioguide_id"].fillna("")], axis=1),
            hovertemplate="<b>%{customdata[0]}</b><br>Votes with own party: %{customdata[1]}"
                          "<br>Click to open their record<extra></extra>"))
    top = 1.06
    if highlight is not None and (m["icpsr"] == highlight).any():
        me = m[m["icpsr"] == highlight].iloc[0]
        unity = f"{me['party_unity_pct']:.0f}%" if pd.notna(me["party_unity_pct"]) else "not available"
        fig.add_trace(go.Scatter(
            x=[me["x"]], y=[me["y"]], mode="markers", showlegend=False, name=highlight_name,
            marker=dict(size=size + 8, color=PARTY_COLORS.get(me["party"], MUTED), line=dict(color=ACCENT, width=3)),
            customdata=[[me["label"], unity, ""]],
            hovertemplate="<b>%{customdata[0]}</b><br>Votes with own party: %{customdata[1]}<extra></extra>"))
        fig.add_annotation(x=me["x"], y=me["y"], text=f"<b>{highlight_name}</b>", showarrow=True, arrowhead=0,
                           arrowcolor=ACCENT, arrowwidth=2, ax=60 * math.cos(me["angle"]), ay=-60 * math.sin(me["angle"]),
                           font=dict(size=14, color=ACCENT), bgcolor=BG, borderpad=3)
        top = 1.2
    fig.add_annotation(x=0, y=0.1, text=f"<b>{len(m)}</b>", showarrow=False, font=dict(size=38), yanchor="bottom")
    fig.add_annotation(x=0, y=0.08, text="members", showarrow=False, font=dict(size=14, color=MUTED), yanchor="top")
    fig.update_layout(height=430 if chamber == "House" else 380, margin=dict(l=10, r=10, t=80, b=60),
                      legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.02, yanchor="top"),
                      clickmode="event+select", dragmode=False, hoverdistance=8)
    fig.update_xaxes(visible=False, range=[-1.06, 1.06], fixedrange=True)
    fig.update_yaxes(visible=False, range=[-0.08, top], fixedrange=True, scaleanchor="x", scaleratio=1)
    fig.add_annotation(x=-1.0, y=-0.06, text="Lower score", showarrow=False, xanchor="left",
                       font=dict(size=12, color=MUTED))
    fig.add_annotation(x=1.0, y=-0.06, text="Higher score", showarrow=False, xanchor="right",
                       font=dict(size=12, color=MUTED))
    return fig
