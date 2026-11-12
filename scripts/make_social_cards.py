"""Share images for social posts and link previews, built from the site's data so the numbers stay current.

Writes PNGs to docs/social/ in two sizes:
  *-wide.png  1200 x 627   LinkedIn and X posts, and link previews
  *-tall.png  1080 x 1350  portrait posts (LinkedIn and Instagram feeds)
and the link-preview pages in docs/ (one per card), which GitHub Pages can serve so a shared link shows the card.

Run from the project root after a data refresh:  python scripts/make_social_cards.py
Needs Playwright with Chromium (pip install playwright && python -m playwright install chromium); not used by the app.
"""

import hashlib
import os
import json
from datetime import date
from html import escape
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from seat_map import seat_positions  # noqa: E402
from ui import display_name  # noqa: E402

DATA = ROOT / "data"
OUT = ROOT / "docs" / "social"
PAGES = ROOT / "docs"
SITE = "https://partycohesion.streamlit.app"
PAGES_URL = "https://rendellrich.github.io/partycohesion"
SIZES = {"wide": (1200, 627), "tall": (1080, 1350)}

THEMES = {
    "dark": {"bg": "#171614", "surface": "#21201D", "border": "#3A3733", "text": "#FAFAFA", "body": "#E7E5E4",
             "muted": "#A8A29E", "accent": "#E9C46A", "dem": "#5A97D2", "rep": "#E06C6C", "ind": "#A8A29E"},
    # Every text color passes WCAG AA (4.5:1) on the background.
    "light": {"bg": "#FBFAF8", "surface": "#F2F0EC", "border": "#DDD8D0", "text": "#1C1A17", "body": "#3B3732",
              "muted": "#6B655E", "accent": "#946300", "dem": "#2563A8", "rep": "#B73A34", "ind": "#6B655E"},
}
C = THEMES[os.environ.get("CARD_THEME", "light")]
PARTY = {"Democrat": C["dem"], "Republican": C["rep"], "Independent": C["ind"]}
FONTS = ("https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;600;700&"
         "family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&display=swap")


def fmt_date(value) -> str:
    ts = pd.Timestamp(value)
    return f"{ts:%b} {ts.day}, {ts.year}"


# ---------------------------------------------------------------- data

def facts(today: date | None = None) -> dict:
    members = pd.read_csv(DATA / "members_processed.csv")
    summary = pd.read_csv(DATA / "unity_summary.csv")
    changes = pd.read_csv(DATA / "vote_changes.csv")
    bills = pd.read_csv(DATA / "vote_change_bills.csv")
    floor = pd.read_csv(DATA / "floor_statements.csv")
    latest = int(members["congress"].max())
    through = fmt_date(summary["latest_vote_date"].max())

    house = (members[(members["congress"] == latest) & (members["chamber"] == "House")]
             .sort_values("party_unity_pct").drop_duplicates("icpsr", keep="last"))

    apart = changes[changes["apart"]]
    by_congress = apart.groupby("congress").size().reindex(range(110, latest + 1), fill_value=0)

    rfma = changes[(changes["congress"] == 117) & (changes["chamber"] == "House") & (changes["bill_number"] == "HR8404")]
    rfma_bill = bills[(bills["congress"] == 117) & (bills["chamber"] == "House") & (bills["bill_number"] == "HR8404")].iloc[0]
    r_yea, r_yea_ids = {}, {}
    for roll in (int(rfma_bill["first_roll"]), int(rfma_bill["final_roll"])):
        v = pd.read_csv(DATA / "raw" / "H117_votes.csv") if (DATA / "raw" / "H117_votes.csv").exists() else None
        if v is not None:
            m = members[(members["congress"] == 117) & (members["chamber"] == "House")][["icpsr", "caucus"]]
            t = v[(v["rollnumber"] == roll) & (v["cast_code"] == 1)].merge(m, on="icpsr")
            r_yea[roll] = int((t["caucus"] == "Republican").sum())
            r_yea_ids[roll] = set(t.loc[t["caucus"] == "Republican", "icpsr"])
    rfma_skipped = 0
    if r_yea_ids:
        first_r, final_r = int(rfma_bill["first_roll"]), int(rfma_bill["final_roll"])
        cast_final = v[v["rollnumber"] == final_r].set_index("icpsr")["cast_code"]
        rfma_skipped = sum(1 for i in r_yea_ids[first_r] if cast_final.get(i) not in (1, 6))

    sup, opp = {"Supports more aid", "Supports the bill"}, {"Opposes more aid", "Opposes the bill"}
    g = floor[floor["stance"].isin(sup | opp) & floor["vote_final"].isin(["Yea", "Nay"])].copy()
    g["match"] = (g["stance"].isin(sup) & (g["vote_final"] == "Yea")) | (g["stance"].isin(opp) & (g["vote_final"] == "Nay"))
    fr = g.groupby("chamber")["match"].agg(["sum", "size"]).astype(int)
    exceptions = g[~g["match"]]

    senate = (members[members["chamber"] == "Senate"].groupby(["congress", "caucus"])["party_unity_pct"].mean()
              .unstack()[["Democrat", "Republican"]].round(1))

    chances = int(bills["voted_twice"].sum())
    done = completed_congress(latest, today or date.today())
    unity = (members[members["congress"].isin([done, done - 1])].groupby(["congress", "chamber", "caucus"])
             ["party_unity_pct"].mean().round(1))
    final = {"congress": done, "votes": summary[summary["congress"] == done].set_index("chamber")["party_unity_votes"],
             "unity": unity}
    return {"final": final,
        "latest": latest, "through": through, "house": house,
        "changes": len(changes), "apart": len(apart), "apart_members": apart["icpsr"].nunique(),
        "chances": chances, "bills": len(bills), "by_congress": by_congress,
        "rfma": rfma, "rfma_bill": rfma_bill, "rfma_r_yea": r_yea, "rfma_skipped": rfma_skipped,
        "floor": fr, "floor_exceptions": exceptions, "senate": senate,
    }


def completed_congress(latest: int, today: date) -> int:
    """The newest Congress that has ended. Each one ends on January 3 of the year after its second year."""
    c = latest
    while date(2 * c + 1789, 1, 3) > today:
        c -= 1
    return c


def ordinal(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


# ---------------------------------------------------------------- drawing helpers

def hemicycle_svg(house: pd.DataFrame, width: int) -> str:
    m = house.sort_values("nominate_dim1", na_position="last").reset_index(drop=True)
    seats = seat_positions(len(m), 12)
    m = pd.concat([m, seats], axis=1)
    h = width * 0.52
    r = width / 2 * 0.97
    dot = width / 120
    circles = "".join(
        f'<circle cx="{width / 2 + x * r:.1f}" cy="{h - 4 - y * r:.1f}" r="{dot:.1f}" fill="{PARTY.get(p, C["ind"])}"/>'
        for x, y, p in zip(m["x"], m["y"], m["party"]))
    return f'<svg width="{width}" height="{h:.0f}" viewBox="0 0 {width} {h:.0f}">{circles}</svg>'


def bars_svg(series: pd.Series, width: int, height: int, latest: int) -> str:
    top = series.max()
    n = len(series)
    gap = 10
    bw = (width - gap * (n - 1)) / n
    label_h, value_h = 26, 26
    plot_h = height - label_h - value_h
    out = []
    for i, (congress, v) in enumerate(series.items()):
        x = i * (bw + gap)
        bh = max(2, plot_h * v / top)
        y = value_h + plot_h - bh
        fill = C["accent"] if congress != latest else C["muted"]
        start = 2 * congress + 1787
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="3" fill="{fill}"/>')
        out.append(f'<text x="{x + bw / 2:.1f}" y="{y - 8:.1f}" text-anchor="middle" class="v">{v:,}</text>')
        out.append(f'<text x="{x + bw / 2:.1f}" y="{height - 4}" text-anchor="middle" class="l">{start}</text>')
    return (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<style>.v{{font:600 15px "Public Sans";fill:{C["body"]}}}.l{{font:400 14px "Public Sans";'
            f'fill:{C["muted"]}}}</style>{"".join(out)}</svg>')


def dots_svg(total: int, filled: int, color: str, width: int, per_row: int) -> str:
    gap = width / per_row
    rad = gap * 0.36
    rows = -(-total // per_row)
    h = rows * gap
    out = []
    for i in range(total):
        cx, cy = (i % per_row) * gap + gap / 2, (i // per_row) * gap + gap / 2
        if i < filled:
            out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{rad:.1f}" fill="{color}"/>')
        else:
            out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{rad - 1.5:.1f}" fill="none" stroke="{C["muted"]}" '
                       f'stroke-width="2"/>')
    return f'<svg width="{width}" height="{h:.0f}" viewBox="0 0 {width} {h:.0f}">{"".join(out)}</svg>'

# Party of the president for most of each Congress (each Congress starts in January of an odd year).
PRESIDENTS = [(110, 110, "Bush", "Republican"), (111, 114, "Obama", "Democrat"), (115, 116, "Trump", "Republican"),
              (117, 118, "Biden", "Democrat"), (119, 119, "Trump", "Republican")]


NUMBER_WORDS = {2: "two", 3: "three", 4: "four", 5: "five"}


def president_party(congress: int) -> str:
    return next(p for a, b, _, p in PRESIDENTS if a <= congress <= b)


def handoffs(senate: pd.DataFrame, since: int = 114) -> list[tuple[int, str, float, float]]:
    """Each change of president from the given Congress on: (new Congress, party, before, after) for both parties."""
    out = []
    congresses = list(senate.index)
    for prev, cur in zip(congresses, congresses[1:]):
        if prev >= since and president_party(prev) != president_party(cur):
            for party in ("Democrat", "Republican"):
                out.append((cur, party, senate.loc[prev, party], senate.loc[cur, party]))
    return out

def senate_summary(sen: pd.DataFrame) -> str:
    """The card's one-sentence finding, stated only when every change of president since 2015 fits it."""
    moves = handoffs(sen)
    years = ", ".join(str(2 * c + 1787) for c in sorted({c for c, *_ in moves}))
    if moves and all((after > before) == (president_party(c) == party) for c, party, before, after in moves):
        n = len(moves) // 2
        return (f"At each of the last {NUMBER_WORDS.get(n, n)} changes of president ({years}), senators from the new "
                "president's party voted with their party more often than in the Congress before, and the other "
                "party's senators less often.")
    return "How often each party's senators voted with their party, Congress by Congress, next to who was president."



def lines_svg(senate: pd.DataFrame, width: int, height: int, latest: int, fs: int) -> str:
    left, right, top, band = int(fs * 3.2), int(fs * 10.5), 12, int(fs * 2.1)
    lab = fs * 1.6
    plot_w, plot_h = width - left - right, height - top - band - lab - fs * 0.6
    lo, hi = 80, 100
    xs = list(senate.index)
    step = plot_w / (len(xs) - 1)

    def x(c):
        return left + (c - xs[0]) * step

    def y(v):
        return top + plot_h * (hi - v) / (hi - lo)

    out = []
    for g in (80, 85, 90, 95, 100):
        out.append(f'<line x1="{left}" x2="{left + plot_w}" y1="{y(g):.1f}" y2="{y(g):.1f}" stroke="{C["border"]}"/>')
        out.append(f'<text x="{left - 10}" y="{y(g) + fs * 0.35:.1f}" text-anchor="end" class="l">{g}%</text>')
    for c in xs:
        out.append(f'<text x="{x(c):.1f}" y="{top + plot_h + lab:.1f}" text-anchor="middle" class="l">{2 * c + 1787}</text>')
    by = top + plot_h + lab + fs * 0.6
    for a, b, name, party in PRESIDENTS:
        x0, x1 = max(0, x(a) - step / 2 + 2), x(b) + step / 2 - 2
        out.append(f'<rect x="{x0:.1f}" y="{by}" width="{x1 - x0:.1f}" height="{band - 8}" rx="4" '
                   f'fill="{PARTY[party]}" fill-opacity="0.22"/>')
        out.append(f'<text x="{(x0 + x1) / 2:.1f}" y="{by + (band - 8) / 2 + fs * 0.35:.1f}" text-anchor="middle" '
                   f'class="b">{name}</text>')
    for party in ("Republican", "Democrat"):
        col = PARTY[party]
        pts = " ".join(f"{x(c):.1f},{y(v):.1f}" for c, v in senate[party].items())
        out.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="3" stroke-linejoin="round"/>')
        for c, v in senate[party].items():
            fill = C["bg"] if c == latest else col
            out.append(f'<circle cx="{x(c):.1f}" cy="{y(v):.1f}" r="5.5" fill="{fill}" stroke="{col}" stroke-width="2.5"/>')
        last = senate[party].iloc[-1]
        dy = -10 if party == "Republican" else 16
        out.append(f'<text x="{x(xs[-1]) + 16:.1f}" y="{y(last) + dy + fs * 0.35:.1f}" class="e">'
                   f'{"Republicans" if party == "Republican" else "Democrats"} {last:.1f}%</text>')
    return (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            f'<style>.l{{font:400 {fs - 2}px "Public Sans";fill:{C["muted"]}}}.b{{font:600 {fs - 2}px "Public Sans";'
            f'fill:{C["body"]}}}.e{{font:600 {fs}px "Public Sans";fill:{C["body"]}}}</style>{"".join(out)}</svg>')



# ---------------------------------------------------------------- cards

def page(body: str, size: str, extra_css: str = "") -> str:
    w, h = SIZES[size]
    pad = 64 if size == "wide" else 80
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="{FONTS}">
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ width: {w}px; height: {h}px; background: {C['bg']}; color: {C['text']};
  font-family: 'Public Sans', sans-serif; }}
.card {{ width: {w}px; height: {h}px; padding: {pad}px; display: flex; flex-direction: column; position: relative;
  border-top: 6px solid {C['accent']}; }}
h1 {{ font-family: 'Source Serif 4', serif; font-weight: 700; color: {C['text']}; letter-spacing: -0.01em; text-wrap: balance; }}
.body {{ color: {C['body']}; }}
p {{ text-wrap: pretty; }}
.muted {{ color: {C['muted']}; }}
.accent {{ color: {C['accent']}; }}
.foot {{ margin-top: auto; display: flex; justify-content: space-between; align-items: flex-end;
  font-size: 18px; color: {C['muted']}; border-top: 1px solid {C['border']}; padding-top: 18px; }}
.brand {{ font-family: 'Source Serif 4', serif; font-weight: 700; font-size: 24px; color: {C['text']}; }}
.brand span {{ color: {C['accent']}; }}
{extra_css}
</style></head><body><div class="card">{body}</div></body></html>"""


def foot(source: str, size: str) -> str:
    url = SITE.replace("https://", "")
    if size == "wide":
        return (f'<div class="foot"><div class="brand">Party<span>Cohesion</span></div>'
                f'<div style="text-align:right">{escape(source)}<br>{url}</div></div>')
    return (f'<div class="foot" style="flex-direction:column;align-items:flex-start;gap:6px">'
            f'<div class="brand">Party<span>Cohesion</span> <span style="font-family:Public Sans;font-weight:400;'
            f'font-size:20px;color:{C["muted"]}">· {url}</span></div><div>{escape(source)}</div></div>')


def card_home(f: dict, size: str) -> str:
    src = f"Data: Voteview (UCLA), every roll call through {f['through']}"
    if size == "wide":
        body = f"""
<div style="display:flex;gap:48px;align-items:center;flex:1">
  <div style="flex:1.05">
    <h1 style="font-size:50px;line-height:1.08">Do members of Congress vote the same way no matter who is president?</h1>
    <p class="body" style="font-size:23px;line-height:1.45;margin-top:22px">Every House and Senate roll call since
    2007, from the official record. How often each member votes with their party, and when that changes.</p>
  </div>
  <div style="flex:0.95;display:flex;flex-direction:column;align-items:center">
    {hemicycle_svg(f['house'], 470)}
    <div class="muted" style="font-size:17px;margin-top:10px">One dot per House member, ordered by voting record</div>
  </div>
</div>{foot(src, size)}"""
    else:
        body = f"""
<h1 style="font-size:66px;line-height:1.07;margin-top:24px">Do members of Congress vote the same way no matter who is president?</h1>
<p class="body" style="font-size:30px;line-height:1.45;margin-top:30px">Every House and Senate roll call since 2007,
from the official record. How often each member votes with their party, and when that changes.</p>
<div style="margin-top:60px;display:flex;flex-direction:column;align-items:center">{hemicycle_svg(f['house'], 900)}
<div class="muted" style="font-size:22px;margin-top:14px">One dot per House member, ordered by voting record</div></div>
{foot(src, size)}"""
    return page(body, size)


def card_same_bill(f: dict, size: str) -> str:
    latest = f["latest"]
    src = f"Voteview roll calls, 2007 through {f['through']}. Passage, final-version and veto-override votes only."
    note = (f"Bars: each Congress (two years), labeled by the year it began. The {2 * latest + 1787} bar is a "
            "Congress still in session.")
    stat = f"{f['apart']:,}"
    line = ("times a member of Congress voted for a bill at one stage and against it at another, "
            "while most of their own party voted the same way both times.")
    if size == "wide":
        body = f"""
<h1 style="font-size:46px;line-height:1.1">Same bill, different vote</h1>
<div style="display:flex;gap:56px;margin-top:26px;flex:1">
  <div style="flex:0.9">
    <div class="accent" style="font-family:'Source Serif 4';font-weight:700;font-size:96px;line-height:1">{stat}</div>
    <p class="body" style="font-size:23px;line-height:1.42;margin-top:14px">{line}</p>
  </div>
  <div style="flex:1.1">{bars_svg(f['by_congress'], 560, 250, latest)}
    <p class="muted" style="font-size:16px;margin-top:10px;line-height:1.4">{note}</p></div>
</div>{foot(src, size)}"""
    else:
        body = f"""
<h1 style="font-size:64px;line-height:1.08;margin-top:24px">Same bill, different vote</h1>
<div class="accent" style="font-family:'Source Serif 4';font-weight:700;font-size:150px;line-height:1;margin-top:48px">{stat}</div>
<p class="body" style="font-size:32px;line-height:1.42;margin-top:18px">{line}</p>
<div style="margin-top:56px">{bars_svg(f['by_congress'], 920, 330, latest)}</div>
<p class="muted" style="font-size:21px;margin-top:12px;line-height:1.4">{note}</p>
{foot(src, size)}"""
    return page(body, size)


def card_marriage(f: dict, size: str) -> str:
    rf, bill = f["rfma"], f["rfma_bill"]
    first, final = int(bill["first_roll"]), int(bill["final_roll"])
    yea_first, yea_final = f["rfma_r_yea"].get(first), f["rfma_r_yea"].get(final)
    to_nay = [f"{display_name(n)} ({s})" for n, s in rf[rf["direction"] == "Yea to Nay"][["name", "state_abbrev"]].itertuples(index=False)]
    to_yea = [f"{display_name(n)} ({s})" for n, s in rf[rf["direction"] == "Nay to Yea"][["name", "state_abbrev"]].itertuples(index=False)]
    src = "Voteview roll calls 373 (July 19, 2022) and 513 (Dec. 8, 2022), House Clerk numbering"
    d1, d2 = fmt_date(bill["first_date"]), fmt_date(bill["final_date"])
    n = len(rf)
    head = f"{n} House Republicans voted differently in December than in July"
    skipped = f["rfma_skipped"]
    note2 = (f" {skipped} other Republicans who voted Yea in July did not vote in December." if skipped else "")

    def stat_block(label, value, sub, fs):
        return (f'<div style="flex:1;background:{C["surface"]};border:1px solid {C["border"]};border-radius:12px;'
                f'padding:{fs * 0.9:.0f}px {fs:.0f}px"><div class="muted" style="font-size:{fs * 0.72:.0f}px">{label}</div>'
                f'<div style="font-family:Source Serif 4;font-weight:700;font-size:{fs * 2.3:.0f}px;line-height:1.1;'
                f'color:{C["rep"]}">{value}</div><div class="body" style="font-size:{fs * 0.72:.0f}px">{sub}</div></div>')

    def names(title, items, fs):
        return (f'<div style="flex:1"><div class="accent" style="font-weight:600;font-size:{fs}px;margin-bottom:6px">'
                f'{title}</div><div class="body" style="font-size:{fs * 0.92:.0f}px;line-height:1.45">'
                f'{"<br>".join(escape(x) for x in items)}</div></div>')

    if size == "wide":
        body = f"""
<div class="muted" style="font-size:19px">Respect for Marriage Act (H.R. 8404)</div>
<h1 style="font-size:36px;line-height:1.15;margin-top:6px">{head}</h1>
<div style="display:flex;gap:34px;margin-top:22px;flex:1">
  <div style="flex:0.9;display:flex;flex-direction:column;gap:14px">
    {stat_block(f"Passage · {d1}", yea_first, "Republicans voted Yea", 22)}
    {stat_block(f"Final version · {d2}", yea_final, "Republicans voted Yea", 22)}
  </div>
  <div style="flex:1.1;display:flex;gap:26px">
    {names("Yea, then Nay", to_nay, 19)}{names("Nay, then Yea", to_yea, 19)}
  </div>
</div>
<p class="muted" style="font-size:16px;margin:10px 0 14px">Between the votes, the Senate added religious-liberty language.{note2}
Every House Democrat who voted both times voted Yea both times.</p>{foot(src, size)}"""
    else:
        body = f"""
<div class="muted" style="font-size:26px;margin-top:16px">Respect for Marriage Act (H.R. 8404)</div>
<h1 style="font-size:52px;line-height:1.12;margin-top:10px">{head}</h1>
<div style="display:flex;gap:24px;margin-top:40px">
  {stat_block(f"Passage · {d1}", yea_first, "Republicans voted Yea", 28)}
  {stat_block(f"Final version · {d2}", yea_final, "Republicans voted Yea", 28)}
</div>
<div style="display:flex;gap:40px;margin-top:44px">{names("Yea, then Nay", to_nay, 28)}{names("Nay, then Yea", to_yea, 28)}</div>
<p class="muted" style="font-size:22px;margin-top:36px;line-height:1.4">Between the votes, the Senate added religious-liberty
language.{note2} Every House Democrat who voted both times voted Yea both times.</p>{foot(src, size)}"""
    return page(body, size)


def card_floor(f: dict, size: str) -> str:
    fr = f["floor"]
    h_ok, h_n = int(fr.loc["House", "sum"]), int(fr.loc["House", "size"])
    s_ok, s_n = int(fr.loc["Senate", "sum"]), int(fr.loc["Senate", "size"])
    exc = f["floor_exceptions"]
    exc_names = ", ".join(display_name(n).split()[-1] for n in exc["name"])
    src = "Congressional Record (GovInfo), floor debate 2022 to 2024, each member's remarks labeled with AI (Claude)"
    head = "Said it on the floor, then voted that way"
    sub = ("Members who took a clear position in floor debate on Ukraine aid (2023 to 2024) or the Respect for "
           "Marriage Act (2022), and how they voted on the final bill.")
    note = (f"The {len(exc)} senators who didn't ({exc_names}) spoke for Ukraine aid and voted against a final package "
            "that also carried aid for Israel and Taiwan.")

    def block(label, ok, n, width, per_row, fs):
        return (f'<div><div style="display:flex;align-items:baseline;gap:12px;margin-bottom:10px">'
                f'<span style="font-family:Source Serif 4;font-weight:700;font-size:{fs * 2:.0f}px" class="accent">{ok} of {n}</span>'
                f'<span class="body" style="font-size:{fs:.0f}px">{label}</span></div>'
                f'{dots_svg(n, ok, C["accent"], width, per_row)}</div>')

    if size == "wide":
        body = f"""
<h1 style="font-size:44px;line-height:1.1">{head}</h1>
<p class="body" style="font-size:20px;line-height:1.4;margin-top:10px;max-width:980px">{sub}</p>
<div style="display:flex;gap:56px;margin-top:22px;flex:1">
  <div style="flex:1.25">{block("House members", h_ok, h_n, 560, 26, 22)}</div>
  <div style="flex:0.75">{block("senators", s_ok, s_n, 320, 12, 22)}</div>
</div>
<p class="muted" style="font-size:16px;line-height:1.4;margin-bottom:14px">{note}</p>{foot(src, size)}"""
    else:
        body = f"""
<h1 style="font-size:60px;line-height:1.08;margin-top:24px">{head}</h1>
<p class="body" style="font-size:28px;line-height:1.42;margin-top:20px">{sub}</p>
<div style="margin-top:48px">{block("House members", h_ok, h_n, 920, 22, 30)}</div>
<div style="margin-top:40px">{block("senators", s_ok, s_n, 920, 22, 30)}</div>
<p class="muted" style="font-size:22px;line-height:1.4;margin-top:32px">{note}</p>{foot(src, size)}"""
    return page(body, size)


def card_senate(f: dict, size: str) -> str:
    sen, latest = f["senate"], f["latest"]
    src = f"Voteview roll calls through {f['through']}. Average party unity of each party's senators, per Congress."
    head = "In the Senate, party unity moves with the White House"
    sub = senate_summary(sen)
    note = (f"Hollow dots: the {2 * latest + 1787} to {2 * latest + 1788} Congress, still in session. Party unity: how "
            "often a senator votes with their party's majority when most Democrats and most Republicans vote on "
            "opposite sides.")
    if size == "wide":
        body = f"""
<h1 style="font-size:40px;line-height:1.1">{head}</h1>
<p class="body" style="font-size:19px;line-height:1.4;margin-top:10px;max-width:1040px">{sub}</p>
<div style="margin-top:14px">{lines_svg(sen, 1072, 300, latest, 16)}</div>
<p class="muted" style="font-size:14px;line-height:1.35;margin:2px 0 12px">{note}</p>{foot(src, size)}"""
    else:
        body = f"""
<h1 style="font-size:58px;line-height:1.08;margin-top:24px">{head}</h1>
<p class="body" style="font-size:28px;line-height:1.42;margin-top:20px">{sub}</p>
<div style="margin-top:44px">{lines_svg(sen, 920, 560, latest, 22)}</div>
<p class="muted" style="font-size:21px;line-height:1.4;margin-top:16px">{note}</p>{foot(src, size)}"""
    return page(body, size)


def final_cells(f: dict) -> list[dict]:
    """Average party unity for each chamber and party in the completed Congress, with the change from the one before."""
    fin = f["final"]
    c, u = fin["congress"], fin["unity"]
    out = []
    for chamber in ("House", "Senate"):
        for party in ("Democrat", "Republican"):
            now = u.get((c, chamber, party))
            before = u.get((c - 1, chamber, party))
            out.append({"chamber": chamber, "party": party, "pct": now,
                        "change": None if before is None or now is None else round(now - before, 1)})
    return out


def change_text(x: float | None, prev: int) -> str:
    if x is None:
        return ""
    if x == 0:
        return f"same as the {ordinal(prev)}"
    return f"{'up' if x > 0 else 'down'} {abs(x):.1f} points from the {ordinal(prev)}"


def card_final(f: dict, size: str) -> str:
    fin = f["final"]
    c = fin["congress"]
    years = f"{2 * c + 1787} to {2 * c + 1788}"
    votes = fin["votes"]
    head = f"The {ordinal(c)} Congress, final record"
    sub = (f"{int(votes.get('House', 0)):,} party-line votes in the House and {int(votes.get('Senate', 0)):,} in the "
           f"Senate, {years}. Average party unity for each party:")
    src = f"Voteview roll calls, {ordinal(c)} Congress ({years}). Party-line votes only."
    note = ("Party unity: how often a member votes with their party's majority when most Democrats and most "
            "Republicans vote on opposite sides. Independents are counted with the party they caucus with.")
    fs = 22 if size == "wide" else 36
    cells = []
    for x in final_cells(f):
        group = f"{x['chamber']} {x['party']}s"
        cells.append(
            f'<div style="background:{C["surface"]};border:1px solid {C["border"]};border-radius:12px;'
            f'padding:{fs * 0.75:.0f}px {fs:.0f}px"><div class="muted" style="font-size:{fs * 0.75:.0f}px">{group}</div>'
            f'<div style="font-family:Source Serif 4;font-weight:700;font-size:{fs * 2.4:.0f}px;line-height:1.1;'
            f'color:{PARTY[x["party"]]}">{x["pct"]:.1f}%</div>'
            f'<div class="body" style="font-size:{fs * 0.72:.0f}px">{escape(change_text(x["change"], c - 1))}</div></div>')
    grid = (f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:{fs * 0.7:.0f}px;margin-top:{fs:.0f}px">'
            f'{"".join(cells)}</div>')
    if size == "wide":
        body = f"""
<h1 style="font-size:44px;line-height:1.1">{head}</h1>
<p class="body" style="font-size:20px;line-height:1.4;margin-top:10px">{sub}</p>
{grid}
<p class="muted" style="font-size:15px;line-height:1.4;margin:12px 0 12px">{note}</p>{foot(src, size)}"""
    else:
        body = f"""
<h1 style="font-size:62px;line-height:1.08;margin-top:24px">{head}</h1>
<p class="body" style="font-size:28px;line-height:1.42;margin-top:20px">{sub}</p>
<div style="margin-top:40px">{grid}</div>
<p class="muted" style="font-size:23px;line-height:1.45;margin-top:44px">{note}</p>{foot(src, size)}"""
    return page(body, size)


CARDS = {
    "partycohesion": (card_home, "PartyCohesion",
                      "Do members of Congress vote the same way no matter who is president? Every House and Senate "
                      "roll call since 2007, from the official record.", ""),
    "same-bill-different-vote": (card_same_bill, "Same bill, different vote · PartyCohesion",
                                 "Members of Congress who voted for a bill at one stage and against it at another, "
                                 "while most of their party didn't change. From the official roll-call record.",
                                 "Same_Bill_Different_Vote"),
    "respect-for-marriage-act": (card_marriage, "Respect for Marriage Act: House votes that changed · PartyCohesion",
                                 "Nine House Republicans voted differently on the final version (December 2022) than on "
                                 "passage (July 2022). From the official roll-call record.",
                                 "Same_Bill_Different_Vote"),
    "senate-unity": (card_senate, "Senate party unity and the White House · PartyCohesion",
                     "How often each party's senators voted with their party in every Congress since 2007, next to "
                     "who was president. From the official roll-call record.", "Overview"),
    "floor-remarks": (card_floor, "Said it on the floor, then voted that way · PartyCohesion",
                      "What members said in floor debate on Ukraine aid and the Respect for Marriage Act, next to "
                      "how they voted. From the Congressional Record.", "Campaign_Statements"),
    "congress-final": (card_final, "A Congress's final record · PartyCohesion",
                       "Average party unity for each party in the most recent completed Congress, House and Senate, "
                       "from the official roll-call record.", "Overview"),
}

def share_url(slug: str) -> str:
    return f"{PAGES_URL}/" if slug == "partycohesion" else f"{PAGES_URL}/{slug}/"


def captions(f: dict) -> dict[str, str]:
    """Post text for each card, built from the same numbers as the images. Facebook gets the link; the Instagram
    version (see scripts/post_social.py) swaps the link for "Link in bio" because Instagram captions can't link."""
    bill = f["rfma_bill"]
    first, final = f["rfma_r_yea"][int(bill["first_roll"])], f["rfma_r_yea"][int(bill["final_roll"])]
    fr, sen = f["floor"], f["senate"]
    latest = sen.iloc[-1]
    text = {
        "partycohesion": (
            "Do members of Congress vote the same way no matter who is president? PartyCohesion shows how often each "
            "member votes with their own party, using every House and Senate roll call since 2007 from the official "
            "record.\n\nData: Voteview"),
        "same-bill-different-vote": (
            f"Most bills get more than one floor vote. Since 2007, members of Congress voted for a bill at one stage "
            f"and against it at another {f['apart']:,} times while most of their own party voted the same way both "
            "times. Bills often change between votes, so a different vote is not a contradiction.\n\nData: Voteview"),
        "respect-for-marriage-act": (
            f"The Respect for Marriage Act had two House votes in 2022. In July, {first} House Republicans voted Yea. "
            f"In December, after the Senate added religious-liberty language, {final} did. Of the Republicans who "
            f"voted both times, {len(f['rfma'])} voted differently the second time.\n\nData: Voteview, House roll calls 373 and 513"),
        "senate-unity": (
            f"How often do senators vote with their own party? {senate_summary(sen)} In the current Congress, still "
            f"in session: Senate Republicans {latest['Republican']:.1f}%, Senate Democrats "
            f"{latest['Democrat']:.1f}%.\n\nData: Voteview"),
        "floor-remarks": (
            "Members who took a clear position in floor debate on Ukraine aid (2023 to 2024) or the Respect for "
            f"Marriage Act (2022), and how they voted on the final bill: {int(fr.loc['House', 'sum'])} of "
            f"{int(fr.loc['House', 'size'])} House members and {int(fr.loc['Senate', 'sum'])} of "
            f"{int(fr.loc['Senate', 'size'])} senators voted the way they spoke.\n\nData: Congressional Record "
            "(GovInfo), Voteview"),
        "congress-final": final_caption(f),
    }
    return {slug: f"{body}\n{share_url(slug)}" for slug, body in text.items()}


def final_caption(f: dict) -> str:
    fin = f["final"]
    c = fin["congress"]
    cells = {(x["chamber"], x["party"]): x for x in final_cells(f)}
    parts = ", ".join(f"{ch} {p}s {cells[(ch, p)]['pct']:.1f}%" for ch in ("House", "Senate") for p in ("Democrat", "Republican"))
    return (f"The {ordinal(c)} Congress ({2 * c + 1787} to {2 * c + 1788}) is complete. Its final party unity record, "
            f"the average share of party-line votes on which members sided with their own party: {parts}. That's over "
            f"{int(fin['votes'].get('House', 0)):,} House and {int(fin['votes'].get('Senate', 0)):,} Senate "
            "party-line votes, where most Democrats and most Republicans voted on opposite sides.\n\nData: Voteview")



def alt_texts(f: dict) -> dict[str, str]:
    """A description of each card image for screen readers, sent as the post's alt text (scripts/post_social.py).
    It says what the picture shows, built from the same numbers, so it doesn't just repeat the caption."""
    by = f["by_congress"]
    bars = ", ".join(f"{2 * c + 1787}: {n:,}" for c, n in by.items())
    sen = f["senate"]
    first, last = sen.index[0], sen.index[-1]
    fr = f["floor"]
    rf, bill = f["rfma"], f["rfma_bill"]
    names = lambda d: ", ".join(f"{display_name(n)} ({s})" for n, s in rf[rf["direction"] == d][["name", "state_abbrev"]].itertuples(index=False))
    return {
        "partycohesion": ("PartyCohesion card. Headline: Do members of Congress vote the same way no matter who is "
                          "president? Beside it, a half-circle chart of every House member as one dot, colored by "
                          "party and ordered by voting record. Source: Voteview."),
        "same-bill-different-vote": (f"Card titled Same bill, different vote. Large number: {f['apart']:,} times a "
                                     "member voted for a bill at one stage and against it at another while most of "
                                     f"their party voted the same way both times. Bar chart by Congress, labeled by "
                                     f"starting year: {bars}. The last bar is a Congress still in session."),
        "respect-for-marriage-act": (f"Card about the Respect for Marriage Act, H.R. 8404. Headline: {len(rf)} House "
                                     "Republicans voted differently in December than in July 2022. Two boxes: "
                                     f"{f['rfma_r_yea'].get(int(bill['first_roll']))} Republicans voted Yea on passage "
                                     f"in July, and {f['rfma_r_yea'].get(int(bill['final_roll']))} on the final "
                                     f"version in December. Yea, then Nay: {names('Yea to Nay')}. Nay, then Yea: "
                                     f"{names('Nay to Yea')}."),
        "senate-unity": (f"Line chart titled In the Senate, party unity moves with the White House. Two lines, "
                         f"Senate Democrats and Senate Republicans, showing average party unity per Congress from "
                         f"{2 * first + 1787} to {2 * last + 1787}. Democrats go from {sen.loc[first, 'Democrat']:.1f}% "
                         f"to {sen.loc[last, 'Democrat']:.1f}%, Republicans from {sen.loc[first, 'Republican']:.1f}% "
                         f"to {sen.loc[last, 'Republican']:.1f}%. {senate_summary(sen)}"),
        "congress-final": (f"Card titled The {ordinal(f['final']['congress'])} Congress, final record. Four boxes with "
                           "average party unity: " + "; ".join(
                               f"{x['chamber']} {x['party']}s {x['pct']:.1f}%, {change_text(x['change'], f['final']['congress'] - 1)}"
                               for x in final_cells(f)) + "."),
        "floor-remarks": ("Card titled Said it on the floor, then voted that way. Two grids of dots, one per member "
                          "who took a clear position in floor debate on Ukraine aid or the Respect for Marriage Act. "
                          f"Filled dots voted the way they spoke: {int(fr.loc['House', 'sum'])} of "
                          f"{int(fr.loc['House', 'size'])} House members and {int(fr.loc['Senate', 'sum'])} of "
                          f"{int(fr.loc['Senate', 'size'])} senators."),
    }


def share_links(url: str, text: str) -> list[tuple[str, str]]:
    from urllib.parse import quote
    u, t = quote(url, safe=""), quote(text, safe="")
    return [("LinkedIn", f"https://www.linkedin.com/sharing/share-offsite/?url={u}"),
            ("Facebook", f"https://www.facebook.com/sharer/sharer.php?u={u}"),
            ("X", f"https://twitter.com/intent/tweet?text={t}&url={u}")]


PAGE_CSS = f"""
body {{ margin: 0; background: {C['bg']}; color: {C['text']}; font: 18px/1.5 'Public Sans', system-ui, sans-serif; }}
main {{ max-width: 760px; margin: 0 auto; padding: 32px 20px 48px; text-align: center; }}
img {{ width: 100%; height: auto; border-radius: 10px; border: 1px solid {C['border']}; }}
p {{ color: {C['body']}; }}
a.button, button {{ display: inline-block; margin: 6px 4px 0; padding: 10px 18px; border-radius: 8px; font: 600 16px/1.2
  'Public Sans', system-ui, sans-serif; text-decoration: none; cursor: pointer; border: 1px solid {C['border']};
  background: transparent; color: {C['text']}; }}
a.primary {{ background: {C['accent']}; border-color: {C['accent']}; color: {C['bg']}; font-weight: 700; }}
a.button:focus-visible, button:focus-visible {{ outline: 3px solid {C['text']}; outline-offset: 3px; }}
.share {{ margin-top: 28px; padding-top: 20px; border-top: 1px solid {C['border']}; }}
.share h2 {{ font-size: 16px; font-weight: 600; color: {C['muted']}; margin: 0 0 6px; }}
.hint {{ font-size: 14px; color: {C['muted']}; margin-top: 10px; }}
[hidden] {{ display: none !important; }}
"""

SHARE_JS = """<script>
document.querySelectorAll('[data-share-image]').forEach(function (btn) {
  var img = btn.getAttribute('data-share-image'), text = btn.getAttribute('data-text');
  if (!navigator.canShare) return;
  try { if (!navigator.canShare({ files: [new File([''], 'card.jpg', { type: 'image/jpeg' })] })) return; }
  catch (e) { return; }
  btn.hidden = false;
  btn.addEventListener('click', function () {
    fetch(img).then(function (r) { return r.blob(); }).then(function (b) {
      return navigator.share({ files: [new File([b], img.split('/').pop(), { type: 'image/jpeg' })], text: text });
    }).catch(function () {});
  });
});
document.querySelectorAll('[data-copy]').forEach(function (btn) {
  btn.addEventListener('click', function () {
    navigator.clipboard.writeText(btn.getAttribute('data-copy')).then(function () {
      var old = btn.textContent; btn.textContent = 'Copied'; setTimeout(function () { btn.textContent = old; }, 1500);
    });
  });
});
</script>"""


def share_block(slug: str, caption: str) -> str:
    """Buttons anyone can use to post the card: link shares for LinkedIn, Facebook and X, and for Instagram (which
    has no share link) the phone's share sheet with the image, or a download of the 4:5 image plus the caption."""
    url, tall = share_url(slug), f"{PAGES_URL}/social/{slug}-tall.jpg"
    links = "".join(f'<a class="button" href="{escape(h)}" target="_blank" rel="noopener">{n}</a>'
                    for n, h in share_links(url, caption.split(chr(10))[0]))
    c = escape(caption)
    return f"""<div class="share"><h2>Share this card</h2>{links}
<button type="button" data-share-image="{tall}" data-text="{c}" hidden>Share image (Instagram, Facebook)</button>
<a class="button" href="{tall}" download="{slug}-partycohesion.jpg">Download for Instagram</a>
<button type="button" data-copy="{c}">Copy caption</button>
<p class="hint">For Instagram: on a phone, use Share image. On a computer, download the image and copy the caption.</p>
</div>"""


def share_page(slug: str, title: str, description: str, app_path: str, caption: str) -> str:
    """A small page whose link preview shows the card, with a button into the matching page of the app and buttons
    for sharing the card."""
    target = f"{SITE}/{app_path}".rstrip("/?") if app_path else SITE
    image = f"{PAGES_URL}/social/{slug}-wide.png"
    url = share_url(slug)
    t, d = escape(title), escape(description)
    gallery = "" if slug == "cards" else f'<a class="button" href="{PAGES_URL}/cards/">More cards</a>'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t}</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="PartyCohesion">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="627">
<meta property="og:image:alt" content="{d}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{t}">
<meta name="twitter:description" content="{d}">
<meta name="twitter:image" content="{image}">
<style>{PAGE_CSS}</style></head>
<body><main>
<img src="{image}" alt="{d}" width="1200" height="627">
<p>{d}</p>
<a class="button primary" href="{target}">Open PartyCohesion</a>{gallery}
{share_block(slug, caption)}
</main>{SHARE_JS}</body></html>
"""


def gallery_page(caps: dict[str, str]) -> str:
    """docs/cards/: every card with its share buttons, for anyone who wants to post about PartyCohesion."""
    items = "".join(
        f'<section style="margin-top:48px"><a href="{share_url(slug)}"><img src="{PAGES_URL}/social/{slug}-wide.png" '
        f'alt="{escape(CARDS[slug][2])}" width="1200" height="627" loading="lazy"></a>'
        f'<p>{escape(CARDS[slug][2])}</p>{share_block(slug, caps[slug])}</section>'
        for slug in CARDS)
    url = f"{PAGES_URL}/cards/"
    image = f"{PAGES_URL}/social/partycohesion-wide.png"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Share PartyCohesion</title>
<meta name="description" content="Cards with findings from PartyCohesion, ready to post on LinkedIn, Facebook, X or Instagram.">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:title" content="Share PartyCohesion">
<meta property="og:description" content="Cards with findings from the congressional roll-call record, ready to post.">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{image}">
<meta name="twitter:card" content="summary_large_image">
<style>{PAGE_CSS}</style></head>
<body><main>
<h1 style="font-family:Georgia,serif;font-size:36px;margin:8px 0 4px">Share PartyCohesion</h1>
<p>Each card is built from the official roll-call record and updates when the data does. Post any of them, with the
caption or your own words.</p>
<a class="button primary" href="{SITE}">Open PartyCohesion</a>
{items}
</main>{SHARE_JS}</body></html>
"""


def main() -> None:
    from playwright.sync_api import sync_playwright

    f = facts()
    OUT.mkdir(parents=True, exist_ok=True)
    # A fingerprint of what the cards say. PNG bytes can differ between machines even when nothing changed, so the
    # weekly workflow compares this file, not the images, to decide whether the cards need an update.
    caps = captions(f)
    html = "".join(fn(f, size) + title + desc for fn, title, desc, _ in CARDS.values() for size in SIZES)
    alts = alt_texts(f)
    html += json.dumps(caps, sort_keys=True) + json.dumps(alts, sort_keys=True)
    (OUT / "alt.json").write_text(json.dumps(alts, indent=2) + "\n")
    (OUT / "cards.sha256").write_text(hashlib.sha256(html.encode()).hexdigest() + "\n")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for slug, (fn, title, desc, path) in CARDS.items():
            for size, (w, h) in SIZES.items():
                pg = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
                pg.set_content(fn(f, size), wait_until="networkidle")
                pg.evaluate("document.fonts.ready")
                pg.wait_for_timeout(300)
                pg.screenshot(path=str(OUT / f"{slug}-{size}.png"))
                if size == "tall":  # Instagram only takes JPEG; 1080 x 1350 is its 4:5 feed size
                    pg.screenshot(path=str(OUT / f"{slug}-tall.jpg"), type="jpeg", quality=92)
                pg.close()
            folder = PAGES if slug == "partycohesion" else PAGES / slug
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "index.html").write_text(share_page(slug, title, desc, path, caps[slug]))
            print(f"Wrote {slug}: 3 images and a share page")
        browser.close()
    (PAGES / "cards").mkdir(parents=True, exist_ok=True)
    (PAGES / "cards" / "index.html").write_text(gallery_page(caps))
    (OUT / "captions.json").write_text(json.dumps(caps, indent=2) + "\n")


if __name__ == "__main__":
    main()
