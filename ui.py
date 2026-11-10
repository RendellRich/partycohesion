"""Shared page building blocks that mirror the PartyCohesion Figma design system: cards, metric cards,
party tags, pattern badges and name/place formatting. Every helper escapes its text."""

import re
from html import escape

import pandas as pd
import streamlit as st

from chart_utils import PATTERN_COLORS
from theme import text_on, to_mode, tokens

PARTY_VARS = {"Democrat": "var(--pc-dem)", "Republican": "var(--pc-rep)", "Independent": "var(--pc-ind)"}
VOTE_VARS = {"Yea": "var(--pc-yea)", "Nay": "var(--pc-nay)"}

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

# Type: Public Sans (the U.S. Web Design System's typeface, made for government data) for everything, and
# Source Serif 4 for the big questions and page titles, so headings read like the public record they come from.
FONTS = ("https://fonts.googleapis.com/css2?family=Public+Sans:ital,wght@0,400;0,600;0,700;1,400"
         "&family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&display=swap")
SERIF = "'Source Serif 4', Georgia, serif"
SANS = "'Public Sans', 'Segoe UI', system-ui, sans-serif"

CSS = f"""
<style>
@import url('{FONTS}');
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button,
.stApp [data-testid="stMarkdownContainer"] {{ font-family: {SANS}; }}
.stApp h1 {{ font-family: {SERIF}; font-weight: 700; letter-spacing: -0.01em; }}
.stApp h2, .stApp h3 {{ font-family: {SANS}; font-weight: 700; }}
.stApp [data-testid="stMetricValue"], .pc-stat, .pc-metric-value {{ font-variant-numeric: tabular-nums; }}
.stApp a:focus-visible, .stApp button:focus-visible {{ outline: 2px solid var(--pc-accent); outline-offset: 2px; }}
.stApp [data-testid="stMain"] [data-testid="stPageLink-NavLink"] p {{ color: var(--pc-accent); font-weight: 600; }}
.stApp [data-testid="stMain"] [data-testid="stPageLink-NavLink"]:hover p {{ text-decoration: underline; }}
.pc-hero {{ font-family: {SERIF}; font-size: 2.6rem; font-weight: 700; line-height: 1.15; max-width: 22ch;
            margin: 0.5rem 0 1rem 0; letter-spacing: -0.01em; }}
.pc-intro {{ color: var(--pc-muted); font-size: 1.05rem; line-height: 1.6; max-width: 72ch; margin-bottom: 1.25rem; }}
.pc-card {{ background: var(--pc-surface); border: 1px solid var(--pc-border); border-radius: 10px; padding: 20px; height: 100%; }}
.pc-eyebrow {{ color: var(--pc-accent); font-size: 0.9rem; font-weight: 600; }}
.pc-stat {{ font-size: 2.4rem; font-weight: 700; line-height: 1.2; margin: 6px 0 8px 0; }}
.pc-body {{ color: var(--pc-muted); font-size: 1rem; line-height: 1.5; }}
.pc-metric {{ background: var(--pc-surface); border: 1px solid var(--pc-border); border-radius: 10px; padding: 14px 16px; height: 100%; }}
.pc-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin: 4px 0 16px 0; }}
.pc-metric-label {{ color: var(--pc-muted); font-size: 0.85rem; font-weight: 600; }}
.pc-metric-value {{ font-size: 2rem; line-height: 1.25; margin: 4px 0; }}
.pc-metric-value.pc-long {{ font-size: 1.35rem; padding: 6px 0 5px 0; }}
.pc-metric-note {{ color: var(--pc-muted); font-size: 0.85rem; }}
.pc-name {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; font-size: 1.6rem; font-weight: 600; }}
.pc-place {{ color: var(--pc-muted); font-size: 1rem; margin: 4px 0 12px 0; }}
.pc-tag {{ display: inline-flex; align-items: center; gap: 6px; font-size: 0.85rem; font-weight: 600; }}
.pc-dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
.pc-badge {{ display: inline-block; padding: 2px 10px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; }}
.pc-table {{ width: 100%; border-collapse: separate; border-spacing: 0; background: var(--pc-surface);
             border: 1px solid var(--pc-border); border-radius: 10px; overflow: hidden; margin-bottom: 0.5rem; }}
.pc-table th {{ color: var(--pc-muted); font-size: 0.85rem; font-weight: 600; text-align: left; padding: 12px 16px; }}
.pc-table td {{ padding: 12px 16px; border-top: 1px solid var(--pc-border); }}
.pc-table td.pc-muted {{ color: var(--pc-muted); }}
.pc-bars {{ display: grid; grid-template-columns: 130px minmax(120px, 1fr) 140px; gap: 10px 12px; align-items: center; margin: 14px 0 8px 0; }}
.pc-bar {{ display: flex; gap: 2px; height: 22px; }}
.pc-bar span {{ display: block; height: 100%; border-radius: 3px; }}
.pc-chips {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
.pc-explain {{ border-left: 3px solid var(--pc-accent); background: var(--pc-surface); border-radius: 0 8px 8px 0; padding: 12px 16px;
               max-width: 72ch; color: var(--pc-body); font-size: 0.98rem; line-height: 1.55; margin: 0 0 18px 0; }}
.pc-explain-title {{ color: var(--pc-accent); font-weight: 600; font-size: 0.9rem; margin-bottom: 4px; }}
.pc-share {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 8px 0 4px 0; }}
.pc-share span {{ color: var(--pc-muted); font-size: 0.9rem; margin-right: 4px; }}
.pc-share a {{ border: 1px solid var(--pc-border); border-radius: 999px; padding: 4px 12px; font-size: 0.9rem; font-weight: 600;
              color: var(--pc-text) !important; text-decoration: none; }}
.pc-share a:hover {{ border-color: var(--pc-accent); }}
.pc-person {{ display: grid; grid-template-columns: 112px 1fr; gap: 18px; align-items: start; margin: 6px 0 14px 0; }}
.pc-person img {{ width: 112px; border-radius: 8px; border: 1px solid var(--pc-border); }}
.pc-facts {{ color: var(--pc-muted); font-size: 0.95rem; line-height: 1.7; }}
.pc-facts b {{ color: var(--pc-text); font-weight: 600; }}
.pc-facts a {{ color: var(--pc-accent); }}
@media (max-width: 640px) {{ .pc-person {{ grid-template-columns: 80px 1fr; }} .pc-person img {{ width: 80px; }}
                             .pc-hero {{ font-size: 2rem; }} }}
.pc-chip {{ border: 1px solid var(--pc-border); border-radius: 999px; padding: 3px 10px; font-size: 0.85rem; font-weight: 600; }}
</style>
"""


def inject_css() -> None:
    """Site styles plus the color variables for the visitor's light or dark theme."""
    t = tokens()
    names = {"bg": "bg", "surface": "surface", "border": "border", "text": "text", "body": "body", "muted": "muted",
             "accent": "accent", "dem": "dem", "rep": "rep", "ind": "ind", "yea": "yea", "nay": "nay"}
    root = "".join(f"--pc-{css}: {t[key]}; " for key, css in names.items())
    st.markdown(f"<style>:root {{ {root}}}</style>" + CSS, unsafe_allow_html=True)


def intro(text: str) -> None:
    st.markdown(f'<div class="pc-intro">{escape(text)}</div>', unsafe_allow_html=True)


def explainer(text: str) -> None:
    """A short plain-language note for first-time visitors, shown under a page's intro."""
    st.markdown(f'<div class="pc-explain"><div class="pc-explain-title">What this means</div>{escape(text)}</div>',
                unsafe_allow_html=True)


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
    color = PARTY_VARS.get(party, "var(--pc-muted)")
    return f'<span class="pc-tag"><span class="pc-dot" style="background:{color}"></span>{escape(party)}</span>'


def pattern_badge(label: str) -> str:
    if label not in PATTERN_COLORS:
        return f'<span style="color:var(--pc-muted)">{escape(label)}</span>'
    fill = to_mode(PATTERN_COLORS[label])
    return f'<span class="pc-badge" style="background:{fill};color:{text_on(fill)}">{escape(label)}</span>'


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


SITE = "https://partycohesion.streamlit.app"


def share_bar(text: str, path: str = "", params: dict | None = None) -> None:
    """Share links for LinkedIn, X, Facebook, Reddit, email and Instagram (through the share cards), plus the page
    link to copy. path is the page's URL path
    (e.g. "Members"); params are query parameters that open the same view (e.g. a member's profile)."""
    from urllib.parse import quote, urlencode
    url = f"{SITE}/{path}".rstrip("/") + (f"?{urlencode(params)}" if params else "")
    u, t = quote(url, safe=""), quote(text, safe="")
    links = [("LinkedIn", f"https://www.linkedin.com/sharing/share-offsite/?url={u}"),
             ("X", f"https://twitter.com/intent/tweet?text={t}&url={u}"),
             ("Facebook", f"https://www.facebook.com/sharer/sharer.php?u={u}"),
             ("Reddit", f"https://www.reddit.com/submit?url={u}&title={t}"),
             ("Email", f"mailto:?subject={t}&body={quote(text + chr(10) + chr(10) + url, safe='')}"),
             # Instagram has no share link, so this opens the card page with images sized for it and a share button
             ("Instagram", "https://rendellrich.github.io/partycohesion/cards/")]
    st.markdown('<div class="pc-share"><span>Share</span>' + "".join(
        f'<a href="{escape(h)}" target="_blank" rel="noopener" aria-label="Share on {n}">{n}</a>' for n, h in links)
        + "</div>", unsafe_allow_html=True)
    st.caption("Or copy this link:")
    st.code(url, language=None)


BILL_PREFIXES = (("HCONRES", "H.Con.Res. "), ("SCONRES", "S.Con.Res. "), ("HJRES", "H.J.Res. "), ("SJRES", "S.J.Res. "),
                 ("HRES", "H.Res. "), ("SRES", "S.Res. "), ("HR", "H.R. "), ("S", "S. "))


def bill_label(bill: str) -> str:
    """HR8404 -> H.R. 8404"""
    for raw, nice in BILL_PREFIXES:
        if str(bill).startswith(raw) and str(bill)[len(raw):].isdigit():
            return nice + str(bill)[len(raw):]
    return str(bill)


def last_name(name: str) -> str:
    return str(name).split(",")[0].strip()


def congress_years(first: int, last: int, newest: int) -> str:
    start = 2 * int(first) + 1787
    end = "now" if int(last) == int(newest) else str(2 * int(last) + 1788)
    return f"{start} to {end}"


def member_header(name: str, party: str, state: str, chamber: str, first: int, last: int, newest: int) -> None:
    from chart_utils import ordinal
    place = f"{STATES.get(state, state)}, {chamber}, {ordinal(first)} to {ordinal(last)} Congress " \
            f"({congress_years(first, last, newest)})" + ("; data starts in 2007" if int(first) == 110 else "")
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
        seg = "".join(f'<span style="width:{max(cnt / widest * 100, 1.2 if cnt else 0):.1f}%;background:{VOTE_VARS[k]}"></span>'
                      for cnt, k in ((y, "Yea"), (n, "Nay")) if cnt)
        bars += f'<div>{party_tag(party)}</div><div class="pc-bar">{seg}</div>' \
                f'<div class="pc-body">{int(y)} Yea · {int(n)} Nay</div>'
    legend = " ".join(f'<span class="pc-tag" style="margin-right:14px"><span class="pc-dot" style="border-radius:2px;'
                      f'background:{VOTE_VARS[k]}"></span>{k}</span>' for k in ("Yea", "Nay"))
    eyebrow = f"{v['chamber']} · {fmt_date(v['date'])} · roll call {int(v['rollnumber'])}"
    result = f"{v['vote_question']} · {v['vote_result']}, {int(v['yea_count'])} Yea to {int(v['nay_count'])} Nay"
    if broke.empty:
        who = '<div class="pc-body" style="margin-top:12px">No Democrat or Republican voted against their party\'s majority.</div>'
    else:
        names = [f"{last_name(r.name)} ({r.party[0]}-{r.state_abbrev})" for r in broke.sort_values(["party", "name"]).itertuples()]
        who = (f'<div style="margin-top:14px;font-weight:600">{len(broke)} member{"s" if len(broke) != 1 else ""} voted '
               f"against their party's majority</div>{chips(names)}")
    source = (f'<div style="margin-top:14px"><a href="{escape(link)}" target="_blank" rel="noopener" '
              f'style="color:var(--pc-accent)">Full record on Voteview</a></div>') if link else ""
    st.markdown(f'<div class="pc-card"><div class="pc-eyebrow">{escape(eyebrow)}</div>'
                f'<div style="font-size:1.4rem;font-weight:600;margin:6px 0 4px 0">{escape(str(v["label"]))}</div>'
                f'<div class="pc-body">{escape(result)}</div><div class="pc-bars">{bars}</div>'
                f'<div class="pc-body" style="font-size:0.85rem">{legend}</div>{who}{source}</div>', unsafe_allow_html=True)


EARLY_MIN_VOTES, EARLY_SHARE = 50, 0.8  # same rule as the member spotlights (scripts/member_spotlights.py)


def early_congress(members: pd.DataFrame) -> int | None:
    """The newest Congress if it has only just begun: fewer than 80% of its members have 50 party-line votes yet.
    Rates built on a handful of votes swing a lot, so pages default to the Congress before and say why."""
    newest = int(members["congress"].max())
    cur = members[members["congress"] == newest].drop_duplicates(["chamber", "icpsr"])
    if (members["congress"] == newest - 1).sum() == 0 or len(cur) == 0:
        return None
    ready = (cur["unity_votes_cast"] >= EARLY_MIN_VOTES).sum() >= EARLY_SHARE * len(cur)
    return None if ready else newest


def early_congress_note(members: pd.DataFrame) -> str | None:
    from chart_utils import ordinal
    newest = early_congress(members)
    if newest is None:
        return None
    cur = members[members["congress"] == newest]
    most = int(cur["unity_votes_cast"].max()) if len(cur) else 0
    return (f"The {ordinal(newest)} Congress has only just begun: no member has more than {most} party-line votes in "
            f"it yet, so its rates will swing a lot in the first weeks. Until most members pass 50, the headline numbers "
            f"use the {ordinal(newest - 1)} Congress's full two-year record. You can still pick the {ordinal(newest)} "
            "in the Congress menu.")
