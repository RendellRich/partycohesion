"""Shared chart styling so every chart on the site is ready to post.

Each chart gets a title, a small source line (site + Voteview), a fixed dark background that
matches the app theme, and a camera button that downloads a PNG sized for the platform picked
in the sidebar (X or Instagram).
"""

from pathlib import Path

import streamlit as st

DATA_DIR = Path(__file__).parent / "data"

BG = "#171614"  # matches the app background set in .streamlit/config.toml
FG = "#fafafa"
GRID = "#3A3733"
SOURCE = "partycohesion.streamlit.app · Data: Voteview"

# Design tokens (mirror the PartyCohesion Figma design system). Every color passes WCAG 3:1 for
# chart marks on BG; text colors pass 4.5:1. Colors never carry meaning alone.
MUTED = "#A8A29E"
ACCENT = "#E9C46A"          # highlights "this member" and links
PARTY_COLORS = {"Democrat": "#5B9BD5", "Republican": "#E06C6C", "Independent": "#A8A29E"}
# Position Flips: one hue at different strengths, so no pattern reads as good or bad
PATTERN_COLORS = {"Consistent": "#E7DFF5", "Partly changed": "#B9A6E3", "Changed with the White House": "#8C6BD1",
                  "Opposite pattern": "#7A8597"}
VOTE_COLORS = {"Yea": "#8ECAE6", "Nay": "#577590"}
PAIR_COLORS = [ACCENT, "#8ECAE6"]  # two members side by side (deliberately not party colors)

EXPORT_SIZES = {
    "X / Twitter (1200×675)": (1200, 675),
    "Instagram (1080×1080)": (1080, 1080),
}
DEFAULT_EXPORT = "X / Twitter (1200×675)"


def ordinal(n: int) -> str:
    n = int(n)
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def chamber_label(chamber: str) -> str:
    return {"Both": "House and Senate", "All": "House and Senate"}.get(chamber, chamber)


def show_chart(fig, title: str, filename: str, key: str | None = None) -> None:
    """Style a Plotly figure for the site and social sharing, then render it."""
    top = max(fig.layout.margin.t or 0, 80)
    fig.update_layout(
        title=dict(text=title, x=0.01, xanchor="left", y=0.97, yanchor="top", font=dict(size=17)),
        paper_bgcolor=BG,
        plot_bgcolor=BG,
        font=dict(color=FG),
        margin=dict(t=top),
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID)
    fig.add_annotation(
        text=SOURCE, xref="paper", yref="paper", x=1, y=1, xanchor="right", yanchor="bottom",
        yshift=34, showarrow=False, font=dict(size=11, color=MUTED),
    )
    width, height = EXPORT_SIZES[st.session_state.get("export_size", DEFAULT_EXPORT)]
    config = {
        "displaylogo": False,
        "toImageButtonOptions": {"format": "png", "filename": filename, "width": width, "height": height, "scale": 2},
    }
    st.plotly_chart(fig, width="stretch", config=config, key=key)


# ---------------------------------------------------------------------------
# Keeping cached data in step with the data files
# ---------------------------------------------------------------------------
# Pages cache what they read from data/ (st.cache_data), and that cache lives as long as the server. When the
# twice-weekly refresh commits new data, Streamlit Cloud pulls the files but the cache would keep serving the old
# numbers until the app restarted. app.py calls clear_cache_if_data_changed() on every run to prevent that.
_seen_data_version: float | None = None


def data_version(data_dir: Path = DATA_DIR) -> float:
    """Latest modification time of any file under data/ (changes whenever a refresh or a merge updates the data)."""
    return max((p.stat().st_mtime for p in data_dir.rglob("*") if p.is_file()), default=0.0)


def clear_cache_if_data_changed(data_dir: Path = DATA_DIR) -> bool:
    """Clear st.cache_data when the data files changed since the last run. Returns True if it cleared."""
    global _seen_data_version
    version = data_version(data_dir)
    changed = _seen_data_version is not None and version != _seen_data_version
    if changed:
        st.cache_data.clear()
    _seen_data_version = version
    return changed
