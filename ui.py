"""Shared page building blocks that mirror the PartyCohesion Figma design system: cards, metric cards,
party tags, pattern badges and name/place formatting. Every helper escapes its text."""

import re
from html import escape

import pandas as pd
import streamlit as st

from chart_utils import ACCENT, MUTED, PARTY_COLORS, PATTERN_COLORS, VOTE_COLORS

SURFACE = "#21201D"
BORDER = "#3A3733"

STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia", "PR": "Puerto Rico", "GU": "Guam",
    "VI": "U.S. Virgin Islands", "AS": "American Samoa", "MP": "Northern Mariana Islands", "USA": "United States",
}

CSS = f"""
<style>
.pc-hero {{ font-size: 2.5rem; font-weight: 700; line-height: 1.2; max-width: 900px; margin: 0.5rem 0 1rem 0; }}
.pc-intro {{ color: {MUTED}; font-size: 1.05rem; line-height: 1.6; max-width: 900px; margin-bottom: 1.25rem; }}
.pc-card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; padding: 20px; height: 100%; }}
.pc-eyebrow {{ color: {ACCENT}; font-size: 0.8rem; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase; }}
.pc-stat {{ font-size: 2.4rem; font-weight: 700; line-height: 1.2; margin: 6px 0 8px 0; }}
.pc-body {{ color: {MUTED}; font-size: 1rem; line-height: 1.5; }}
.pc-metric {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px; padding: 14px 16px; height: 100%; }}
.pc-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin: 4px 0 16px 0; }}
.pc-metric-label {{ color: {MUTED}; font-size: 0.85rem; font-weight: 600; }}
.pc-metric-value {{ font-size: 2rem; line-height: 1.25; margin: 4px 0; }}
.pc-metric-value.pc-long {{ font-size: 1.35rem; padding: 6px 0 5px 0; }}
.pc-metric-note {{ color: {MUTED}; font-size: 0.85rem; }}
.pc-name {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; font-size: 1.6rem; font-weight: 600; }}
.pc-place {{ color: {MUTED}; font-size: 1rem; margin: 4px 0 12px 0; }}
.pc-tag {{ display: inline-flex; align-items: center; gap: 6px; font-size: 0.85rem; font-weight: 600; }}
.pc-dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
.pc-badge {{ display: inline-block; padding: 2px 10px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; color: #171614; }}
.pc-table {{ width: 100%; border-collapse: separate; border-spacing: 0; background: {SURFACE};
             border: 1px solid {BORDER}; border-radius: 10px; overflow: hidden; margin-bottom: 0.5rem; }}
.pc-table th {{ color: {MUTED}; font-size: 0.85rem; font-weight: 600; text-align: left; padding: 12px 16px; }}
.pc-table td {{ padding: 12px 16px; border-top: 1px solid {BORDER}; }}
.pc-table td.pc-muted {{ color: {MUTED}; }}
.pc-bars {{ display: grid; grid-template-columns: 130px minmax(120px, 1fr) 140px; gap: 10px 12px; align-items: center; margin: 14px 0 8px 0; }}
.pc-bar {{ display: flex; gap: 2px; height: 22px; }}
.pc-bar span {{ display: block; height: 100%; border-radius: 3px; }}
.pc-chips {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
.pc-chip {{ border: 1px solid {BORDER}; border-radius: 999px; padding: 3px 10px; font-size: 0.85rem; font-weight: 600; }}
</style>
"""


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def intro(text: str) -> None:
    st.markdown(f'<div class="pc-intro">{escape(text)}</div>', unsafe_allow_html=True)


def card(eyebrow: str, stat: str, body: str) -> None:
    st.markdown(f'<div class="pc-card"><div class="pc-eyebrow">{escape(eyebrow)}</div>'
                f'<div class="pc-stat">{escape(stat)}</div><div class="pc-body">{escape(body)}</div></div>',
                unsafe_allow_html=True)


def metric_html(label: str, value: str, note: str = "") -> str:
    long = " pc-long" if len(value) > 12 else ""
    return (f'<div class="pc-metric"><div class="pc-metric-label">{escape(label)}</div>'
            f'<div class="pc-metric-value{long}">{escape(value)}</div>'
            f'<div class="pc-metric-note">{escape(note)}</div></div>')


def metric_card(label: str, value: str, note: str = "") -> None:
    st.markdown(metric_html(label, value, note), unsafe_allow_html=True)


def metric_row(items: list[tuple[str, str, str]]) -> None:
    """Cards in a grid that wraps to fewer per row on narrow screens instead of squeezing the numbers."""
    st.markdown('<div class="pc-grid">' + "".join(metric_html(*i) for i in items) + "</div>", unsafe_allow_html=True)


def party_tag(party: str) -> str:
    color = PARTY_COLORS.get(party, MUTED)
    return f'<span class="pc-tag"><span class="pc-dot" style="background:{color}"></span>{escape(party)}</span>'


def pattern_badge(label: str) -> str:
    if label not in PATTERN_COLORS:
        return f'<span style="color:{MUTED}">{escape(label)}</span>'
    return f'<span class="pc-badge" style="background:{PATTERN_COLORS[label]}">{escape(label)}</span>'


def html_table(header: list[str], rows: list[list[str]], raw_cols: tuple[int, ...] = (), muted_cols: tuple[int, ...] = ()) -> None:
    """Small table with design-system styling. Cells in raw_cols are trusted HTML (badges); others are escaped."""
    head = "".join(f"<th>{escape(h)}</th>" for h in header)
    body = ""
    for r in rows:
        cells = []
        for i, c in enumerate(r):
            cls = ' class="pc-muted"' if i in muted_cols else ""
            cells.append(f"<td{cls}>{c if i in raw_cols else escape(str(c))}</td>")
        body += "<tr>" + "".join(cells) + "</tr>"
    st.markdown(f'<table class="pc-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>',
                unsafe_allow_html=True)


def display_name(name: str) -> str:
    """'Schumer, Charles Ellis (Chuck)' -> 'Chuck Schumer'; 'King, Angus Stanley, Jr.' -> 'Angus King Jr.'"""
    parts = [p.strip() for p in str(name).split(",")]
    if len(parts) < 2:
        return str(name)
    last, given = parts[0], parts[1]
    nick = re.search(r"\(([^)]+)\)", given)
    first = nick.group(1) if nick else given.split()[0] if given.split() else ""
    tail = parts[2] if len(parts) > 2 else ""
    if tail.lower() in {"ii", "iii", "iv"}:  # Voteview writes "Iii"
        tail = tail.upper()
    suffix = f" {tail}" if tail else ""
    return f"{first} {last}{suffix}".strip()


def last_name(name: str) -> str:
    return str(name).split(",")[0].strip()


def congress_years(first: int, last: int, newest: int) -> str:
    start = 2 * int(first) + 1787
    end = "now" if int(last) == int(newest) else str(2 * int(last) + 1788)
    return f"{start} to {end}"


def member_header(name: str, party: str, state: str, chamber: str, first: int, last: int, newest: int) -> None:
    from chart_utils import ordinal
    place = f"{STATES.get(state, state)} · {chamber} · {ordinal(first)} to {ordinal(last)} Congress " \
            f"({congress_years(first, last, newest)})" + (" · data starts in 2007" if int(first) == 110 else "")
    st.markdown(f'<div class="pc-name">{escape(display_name(name))} {party_tag(party)}</div>'
                f'<div class="pc-place">{escape(place)}</div>', unsafe_allow_html=True)


def chips(items: list[str]) -> str:
    return '<div class="pc-chips">' + "".join(f'<span class="pc-chip">{escape(i)}</span>' for i in items) + "</div>"


def fmt_date(value) -> str:
    """e.g. Sep 30, 2026 (portable: %-d is not supported on Windows)."""
    ts = pd.Timestamp(value)
    return f"{ts:%b} {ts.day}, {ts.year}"


def vote_card(v: pd.Series, broke: pd.DataFrame, link: str | None = None) -> None:
    """One vote: what it was, how each party split, and who broke with their party. broke needs name, party and
    state_abbrev columns. link, if given, is shown at the bottom (e.g. the vote's full record on Voteview)."""
    parties = [("Democrat", v["dem_yea"], v["dem_nay"]), ("Republican", v["rep_yea"], v["rep_nay"]),
               ("Independent", v["other_yea"], v["other_nay"])]
    widest = max(y + n for _, y, n in parties) or 1
    bars = ""
    for party, y, n in parties:
        if y + n == 0:
            continue
        seg = "".join(f'<span style="width:{max(cnt / widest * 100, 1.2 if cnt else 0):.1f}%;background:{VOTE_COLORS[k]}"></span>'
                      for cnt, k in ((y, "Yea"), (n, "Nay")) if cnt)
        bars += f'<div>{party_tag(party)}</div><div class="pc-bar">{seg}</div>' \
                f'<div class="pc-body">{int(y)} Yea · {int(n)} Nay</div>'
    legend = " ".join(f'<span class="pc-tag" style="margin-right:14px"><span class="pc-dot" style="border-radius:2px;'
                      f'background:{VOTE_COLORS[k]}"></span>{k}</span>' for k in ("Yea", "Nay"))
    eyebrow = f"{v['chamber']} · {fmt_date(v['date'])} · roll call {int(v['rollnumber'])}"
    result = f"{v['vote_question']} · {v['vote_result']}, {int(v['yea_count'])} Yea to {int(v['nay_count'])} Nay"
    if broke.empty:
        who = '<div class="pc-body" style="margin-top:12px">No Democrat or Republican voted against their party\'s majority.</div>'
    else:
        names = [f"{last_name(r.name)} ({r.party[0]}-{r.state_abbrev})" for r in broke.sort_values(["party", "name"]).itertuples()]
        who = (f'<div style="margin-top:14px;font-weight:600">{len(broke)} member{"s" if len(broke) != 1 else ""} voted '
               f"against their party's majority</div>{chips(names)}")
    source = (f'<div style="margin-top:14px"><a href="{escape(link)}" target="_blank" rel="noopener" '
              f'style="color:{ACCENT}">Full record on Voteview →</a></div>') if link else ""
    st.markdown(f'<div class="pc-card"><div class="pc-eyebrow">{escape(eyebrow)}</div>'
                f'<div style="font-size:1.4rem;font-weight:600;margin:6px 0 4px 0">{escape(str(v["label"]))}</div>'
                f'<div class="pc-body">{escape(result)}</div><div class="pc-bars">{bars}</div>'
                f'<div class="pc-body" style="font-size:0.85rem">{legend}</div>{who}{source}</div>', unsafe_allow_html=True)
