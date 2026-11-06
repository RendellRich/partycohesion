"""Shared chart styling so every chart on the site is ready to post.

Each chart gets a title, a small source line (site + Voteview), a fixed dark background that
matches the app theme, and a camera button that downloads a PNG sized for the platform picked
in the sidebar (X or Instagram).
"""

import streamlit as st

BG = "#171614"  # matches the app background set in .streamlit/config.toml
FG = "#fafafa"
GRID = "#2e2c29"
SOURCE = "partycohesion.streamlit.app · Data: Voteview"

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
        yshift=34, showarrow=False, font=dict(size=11, color="#9aa0a6"),
    )
    width, height = EXPORT_SIZES[st.session_state.get("export_size", DEFAULT_EXPORT)]
    config = {
        "displaylogo": False,
        "toImageButtonOptions": {"format": "png", "filename": filename, "width": width, "height": height, "scale": 2},
    }
    st.plotly_chart(fig, width="stretch", config=config, key=key)
