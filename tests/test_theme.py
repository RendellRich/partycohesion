import plotly.graph_objects as go
import pytest

import theme
from chart_utils import PARTY_COLORS, PATTERN_COLORS, _recolor
from seat_map import seat_positions


def test_every_dark_token_has_a_light_partner():
    assert set(theme.DARK) == set(theme.LIGHT)
    for color in list(PARTY_COLORS.values()) + list(PATTERN_COLORS.values()):
        assert color.lower() in theme.TO_LIGHT


def test_light_swap_reaches_traces_and_shapes(monkeypatch):
    monkeypatch.setattr(theme, "mode", lambda: "light")
    fig = go.Figure(go.Scatter(x=[1], y=[1], marker=dict(color=PARTY_COLORS["Democrat"], line=dict(color="#171614")),
                               line=dict(color=PARTY_COLORS["Republican"])))
    fig.add_shape(type="line", x0=0, x1=1, y0=0, y1=1, line=dict(color=theme.DARK["accent"]))
    _recolor(fig.data[0])
    _recolor(fig.layout.shapes[0])
    assert fig.data[0].marker.color == theme.LIGHT["dem"]
    assert fig.data[0].marker.line.color == theme.LIGHT["bg"]
    assert fig.data[0].line.color == theme.LIGHT["rep"]
    assert fig.layout.shapes[0].line.color == theme.LIGHT["accent"]


@pytest.mark.parametrize("fill", [t[k] for t in (theme.DARK, theme.LIGHT)
                                  for k in ("consistent", "partly", "changed", "opposite")])
def test_pattern_badge_text_passes_contrast(fill):
    hi, lo = sorted([theme._lum(fill), theme._lum(theme.text_on(fill))], reverse=True)
    assert (hi + 0.05) / (lo + 0.05) >= 4.5


def test_home_seat_map_renders():
    from streamlit.testing.v1 import AppTest
    from pathlib import Path
    at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=120)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("one dot per member" in c.value.lower() for c in at.caption)


@pytest.mark.parametrize("n,rows", [(450, 12), (104, 6), (3, 2)])
def test_seat_positions_one_seat_each(n, rows):
    seats = seat_positions(n, rows)
    assert len(seats) == n
    assert seats[["x", "y"]].round(6).drop_duplicates().shape[0] == n
    assert seats["y"].min() >= 0 and seats["x"].between(-1, 1).all()


def test_long_chart_titles_wrap_for_phones():
    from chart_utils import TITLE_CHARS, wrap_title
    text, lines = wrap_title("Share of party-line votes cast with their own party, average member, by Congress")
    assert lines == 2 and all(len(line) <= TITLE_CHARS for line in text.split("<br>"))
    assert wrap_title("The House, 119th Congress") == ("The House, 119th Congress", 1)
