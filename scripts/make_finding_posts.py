"""Finding posts for the PartyCohesion Facebook Page about states: how often members from the same state vote
opposite ways (Same State, Different Vote) and how each state's delegation votes (the map on Home and the States
page). One card per post, in the same look as scripts/make_social_cards.py, with its caption and alt text.

Writes docs/social/findings/<slug>-wide.png (1200 x 627, Facebook), <slug>.txt (caption) and <slug>.alt.txt.
A post in social/posts.yml uses card: finding/<slug>. The numbers are a snapshot of the data on the day this runs,
and each caption says so.

  python scripts/make_finding_posts.py            render every card
  python scripts/make_finding_posts.py --list     print the slugs and headlines without rendering
"""

from __future__ import annotations

import argparse
import sys
from html import escape
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
import make_social_cards as msc  # noqa: E402
from make_social_cards import C, fmt_date, foot, ordinal, page  # noqa: E402
from state_map import member_records, state_summary  # noqa: E402
from state_splits import MIN_SHARED, find_pairs, load_inputs, member_summary  # noqa: E402
from ui import STATES, display_name  # noqa: E402

OUT = ROOT / "docs" / "social" / "findings"
SITE = msc.SITE
TAGS = "#StopTheDivide #Congress #VotingRecord"
PURPLE_LO, PURPLE_HI = "#D9CFEF", "#4B2E8C"
GRAY = "#C3C6CC"


def year(congress: int) -> int:
    return 2 * int(congress) + 1787


# Names as the members use them, where the roll-call record's form differs
KNOWN_AS = {"Perez, Marie Gluesenkamp": "Marie Gluesenkamp Perez", "Roy, Charles": "Chip Roy",
            "Luna, Anna": "Anna Paulina Luna"}
ADJ = {"Democrat": "Democratic", "Republican": "Republican"}


def last(n: str) -> str:
    """Last name as people say it: 'King, Angus Stanley, Jr.' -> 'King'."""
    return str(n).split(",")[0].strip()


def name(n: str) -> str:
    return KNOWN_AS.get(n, display_name(n))


def blend(c1: str, c2: str, t: float) -> str:
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    t = max(0.0, min(1.0, t))
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def dark(color: str) -> bool:
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.299 * r + 0.587 * g + 0.114 * b < 140


# ---------------------------------------------------------------- charts (SVG)

def line_svg(series: list[tuple[str, dict, str, bool]], width: int, height: int, fs: int = 16) -> str:
    """Lines over Congresses. series: (label, {congress: percent}, color, dashed). The y axis starts at 0."""
    congresses = sorted({c for _, d, _, _ in series for c in d})
    top = max(v for _, d, _, _ in series for v in d.values())
    ymax = max(10, 10 * (int(top // 10) + 1))
    left, right, up, down = 48, 160, 14, 34
    pw, ph = width - left - right, height - up - down
    x = lambda c: left + (congresses.index(c) / max(1, len(congresses) - 1)) * pw
    y = lambda v: up + ph - v / ymax * ph
    parts = [f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="Public Sans">']
    for t in range(0, ymax + 1, 10 if ymax <= 50 else 20):
        parts.append(f'<line x1="{left}" x2="{left + pw}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="{C["border"]}"/>'
                     f'<text x="{left - 8}" y="{y(t) + fs / 3:.1f}" text-anchor="end" font-size="{fs - 2}" '
                     f'fill="{C["muted"]}">{t}%</text>')
    for c in congresses:
        parts.append(f'<text x="{x(c):.1f}" y="{height - 8}" text-anchor="middle" font-size="{fs - 2}" '
                     f'fill="{C["muted"]}">{year(c)}</text>')
    for label, d, color, dashed in series:
        pts = [(x(c), y(v)) for c, v in sorted(d.items())]
        path = " ".join(f"{'M' if i == 0 else 'L'}{px:.1f},{py:.1f}" for i, (px, py) in enumerate(pts))
        dash = ' stroke-dasharray="6 6"' if dashed else ""
        parts.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="{2 if dashed else 3.5}"{dash}/>')
        if not dashed:
            parts += [f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4.5" fill="{color}"/>' for px, py in pts]
        lx, ly = pts[-1]
        parts.append(f'<text x="{lx + 12:.1f}" y="{ly + fs / 3:.1f}" font-size="{fs}" font-weight="600" '
                     f'fill="{color if not dashed else C["muted"]}">{escape(label)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def hbar_svg(rows: list[tuple[str, float, str]], width: int, fs: int = 17, color: str | None = None) -> str:
    """Horizontal bars, largest first. rows: (label, percent, note beside the value)."""
    color = color or C["accent"]
    rh, gap, label_w = 30, 14, 300
    height = len(rows) * (rh + gap)
    top = max(v for _, v, _ in rows)
    bar_w = width - label_w - 150
    parts = [f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="Public Sans">']
    for i, (label, v, note) in enumerate(rows):
        y0 = i * (rh + gap)
        w = max(4, v / top * bar_w)
        parts.append(f'<text x="{label_w - 12}" y="{y0 + rh / 2 + fs / 3:.1f}" text-anchor="end" font-size="{fs}" '
                     f'fill="{C["body"]}">{escape(label)}</text>'
                     f'<rect x="{label_w}" y="{y0}" width="{w:.1f}" height="{rh}" rx="3" fill="{color}"/>'
                     f'<text x="{label_w + w + 10:.1f}" y="{y0 + rh / 2 + fs / 3:.1f}" font-size="{fs}" '
                     f'font-weight="700" fill="{C["text"]}">{v:.1f}%'
                     f'<tspan font-weight="400" fill="{C["muted"]}">{escape(note)}</tspan></text>')
    parts.append("</svg>")
    return "".join(parts)


def hist_svg(values: pd.Series, width: int, height: int, fs: int = 16) -> str:
    """Count of members in 2.5-point bins of average split, 0 to 30%."""
    edges = [i * 2.5 for i in range(13)]
    counts = pd.cut(values.clip(upper=29.99), edges, right=False).value_counts(sort=False).tolist()
    left, down = 40, 34
    pw, ph = width - left - 30, height - down - 34
    bw = pw / len(counts)
    top = max(counts)
    parts = [f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="Public Sans">']
    for i, n in enumerate(counts):
        h = n / top * ph
        fill = C["accent"] if edges[i] < 5 else blend(C["accent"], C["bg"], 0.55)
        parts.append(f'<rect x="{left + i * bw + 2:.1f}" y="{34 + ph - h:.1f}" width="{bw - 4:.1f}" height="{h:.1f}" '
                     f'rx="2" fill="{fill}"/>')
        if n:
            parts.append(f'<text x="{left + i * bw + bw / 2:.1f}" y="{34 + ph - h - 6:.1f}" text-anchor="middle" '
                         f'font-size="{fs - 3}" fill="{C["muted"]}">{n}</text>')
    for i in range(0, 13, 2):
        parts.append(f'<text x="{left + i * bw:.1f}" y="{height - 8}" text-anchor="middle" font-size="{fs - 2}" '
                     f'fill="{C["muted"]}">{edges[i]:g}%</text>')
    parts.append("</svg>")
    return "".join(parts)


# A tile map: one square per state, roughly where it sits.
TILES = {
    "AK": (0, 0), "ME": (10, 0), "VT": (9, 1), "NH": (10, 1),
    "WA": (0, 2), "ID": (1, 2), "MT": (2, 2), "ND": (3, 2), "MN": (4, 2), "IL": (5, 2), "WI": (6, 2), "MI": (7, 2),
    "NY": (8, 2), "RI": (9, 2), "MA": (10, 2),
    "OR": (0, 3), "NV": (1, 3), "WY": (2, 3), "SD": (3, 3), "IA": (4, 3), "IN": (5, 3), "OH": (6, 3), "PA": (7, 3),
    "NJ": (8, 3), "CT": (9, 3),
    "CA": (0, 4), "UT": (1, 4), "CO": (2, 4), "NE": (3, 4), "MO": (4, 4), "KY": (5, 4), "WV": (6, 4), "VA": (7, 4),
    "MD": (8, 4), "DE": (9, 4),
    "AZ": (1, 5), "NM": (2, 5), "KS": (3, 5), "AR": (4, 5), "TN": (5, 5), "NC": (6, 5), "SC": (7, 5),
    "OK": (3, 6), "LA": (4, 6), "MS": (5, 6), "AL": (6, 6), "GA": (7, 6),
    "HI": (0, 7), "TX": (3, 7), "FL": (8, 7),
}


def tile_map_svg(colors: dict[str, str], width: int, marked: set[str] = frozenset()) -> str:
    cell = width / 11
    s = cell - 5
    height = 8 * cell
    parts = [f'<svg width="{width}" height="{height:.0f}" viewBox="0 0 {width} {height:.0f}" font-family="Public Sans">']
    for st, (cx, cy) in TILES.items():
        fill = colors.get(st, C["surface"])
        ink = "#FFFFFF" if dark(fill) else C["text"]
        ring = f' stroke="{C["text"]}" stroke-width="3"' if st in marked else ""
        parts.append(f'<rect x="{cx * cell:.1f}" y="{cy * cell:.1f}" width="{s:.1f}" height="{s:.1f}" rx="5" '
                     f'fill="{fill}"{ring}/><text x="{cx * cell + s / 2:.1f}" y="{cy * cell + s / 2 + 6:.1f}" '
                     f'text-anchor="middle" font-size="{s * 0.36:.0f}" font-weight="600" fill="{ink}">{st}</text>')
    parts.append("</svg>")
    return "".join(parts)


def scale_svg(lo_label: str, hi_label: str, lo: str, hi: str, width: int, mid: str | None = None) -> str:
    stops = (f'<stop offset="0" stop-color="{lo}"/>' + (f'<stop offset="0.5" stop-color="{mid}"/>' if mid else "")
             + f'<stop offset="1" stop-color="{hi}"/>')
    return (f'<svg width="{width}" height="44" viewBox="0 0 {width} 44" font-family="Public Sans"><defs>'
            f'<linearGradient id="g">{stops}</linearGradient></defs><rect x="0" y="0" width="{width}" height="12" '
            f'rx="6" fill="url(#g)"/><text x="0" y="36" font-size="15" fill="{C["muted"]}">{escape(lo_label)}</text>'
            f'<text x="{width}" y="36" text-anchor="end" font-size="15" fill="{C["muted"]}">{escape(hi_label)}</text>'
            "</svg>")


# ---------------------------------------------------------------- card layout

def card(kicker: str, head: str, stat: str, line: str, visual: str, source: str, note: str = "",
         stat_color: str | None = None) -> str:
    """Wide card: words on the left, the chart or map on the right."""
    note_html = f'<p class="muted" style="font-size:15px;line-height:1.4;margin-top:10px">{escape(note)}</p>' if note else ""
    body = f"""
<div class="muted" style="font-size:19px;font-weight:600">{escape(kicker)}</div>
<div style="display:flex;gap:44px;margin-top:10px;flex:1;min-height:0">
  <div style="flex:0.92">
    <h1 style="font-size:38px;line-height:1.12">{escape(head)}</h1>
    <div style="font-family:'Source Serif 4';font-weight:700;font-size:78px;line-height:1;margin-top:20px;
      color:{stat_color or C['accent']}">{escape(stat)}</div>
    <p class="body" style="font-size:20px;line-height:1.42;margin-top:12px">{escape(line)}</p>
  </div>
  <div style="flex:1.08;display:flex;flex-direction:column;justify-content:center">{visual}{note_html}</div>
</div>{foot(source, "wide")}"""
    return page(body, "wide")


# ---------------------------------------------------------------- the posts

def build() -> list[dict]:
    members, rollcalls, matrices = load_inputs()
    S = find_pairs(members, matrices["Senate"], "Senate")
    H = find_pairs(members, matrices["House"], "House")
    hs = member_summary(H)
    latest = int(S["congress"].max())
    through = fmt_date(rollcalls[rollcalls["congress"] == latest]["date"].max())
    seats = pd.read_csv(ROOT / "data" / "current_seats.csv")
    ss = state_summary(seats, member_records()).set_index("state")
    states = ss[~ss.index.isin(["DC", "PR", "GU", "VI", "AS", "MP"])]

    s_ok = S[S["both_voted"] >= MIN_SHARED["Senate"]]
    # Same definitions as the Same State, Different Vote page, so the numbers match it
    typ_sen = S[S["same_side"]].groupby("congress")["split_pct"].median()
    mix_sen = S[~S["same_side"]].groupby("congress")["split_pct"].median()
    h_ok = hs[hs["colleagues"] >= 2]
    typ_house = h_ok.groupby("congress")["avg_split"].median()
    now_h = h_ok[h_ok["congress"] == latest]
    src_votes = f"Voteview roll calls, through {through}. Only Yea and Nay votes count."
    so_far = f"{ordinal(latest)} Congress so far ({year(latest)} to now, through {through})"
    posts = []

    def add(slug, kicker, head, stat, line, visual, caption, alt, link, note="", source=src_votes, stat_color=None):
        posts.append({"slug": slug, "head": head,
                      "html": card(kicker, head, stat, line, visual, source, note, stat_color),
                      "caption": f"{caption}\n\n{'See the map' if slug.startswith('map-') else 'See the votes'}: "
                                 f"{link}\n\nData: Voteview, through {through}.\n{TAGS}",
                      "alt": alt})

    def pair(df, a, b):
        x = df[(df["name_a"].str.startswith(a) & df["name_b"].str.startswith(b))
               | (df["name_a"].str.startswith(b) & df["name_b"].str.startswith(a))]
        return x.set_index("congress").sort_index()

    def link_state(st, chamber="senate"):
        return f"{SITE}/Same_State_Different_Vote?state={st}" + ("&chamber=house" if chamber == "house" else "")

    def pair_post(slug, st, a, b, kicker_party, typ):
        p = pair(S, a, b)
        p = p[p["both_voted"] >= MIN_SHARED["Senate"]]
        cur = p.loc[latest]
        na, nb = name(cur["name_a"]), name(cur["name_b"])
        first = int(p.index.min())
        series = [("These two", p["split_pct"].to_dict(), C["accent"], False),
                  ("Typical pair", typ.loc[first:].to_dict(), C["muted"], True)]
        rng = f"{p['split_pct'].min():.0f}% to {p['split_pct'].max():.0f}%"
        head = f"{na} and {nb}: same state, same party, opposite votes on {cur['split_pct']:.0f}% of roll calls"
        line = (f"of the votes both of {STATES[st]}'s {ADJ[kicker_party]} senators cast in the {ordinal(latest)} Congress went "
                f"opposite ways ({int(cur['splits'])} of {int(cur['both_voted'])}). Each Congress since "
                f"{year(first)}: {rng}.")
        add(slug, f"Same state, different vote: {STATES[st]}", head, f"{cur['split_pct']:.1f}%", line,
            line_svg(series, 560, 300),
            (f"{na} and {nb} both represent {STATES[st]} as {kicker_party}s. In the {so_far}, they cast opposite "
             f"votes on {int(cur['splits'])} of the {int(cur['both_voted'])} roll calls both voted on "
             f"({cur['split_pct']:.1f}%). A typical pair of same-party senators from one state splits on about "
             f"{typ.loc[latest]:.0f}% of votes. Since {year(first)}, they have split on {rng} of votes each Congress. "
             "A split is a fact about the record, not a judgment: a roll call can't show a senator's reasons."),
            (f"Card titled {head}. Large number: {cur['split_pct']:.1f}% of shared votes went opposite ways in the "
             f"{ordinal(latest)} Congress. Line chart by Congress from {year(first)}: their split share each Congress "
             f"({', '.join(f'{year(c)}: {v:.0f}%' for c, v in p['split_pct'].items())}), above a dashed line for "
             "the typical same-party pair."),
            link_state(st), note="Share of roll calls both voted on where one voted Yea and the other Nay.")

    # 1 to 3: Senate pairs over time
    pair_post("ky-mcconnell-paul", "KY", "McConnell", "Paul", "Republican", typ_sen)
    pair_post("ak-murkowski-sullivan", "AK", "Murkowski", "Sullivan", "Republican", typ_sen)
    pair_post("va-kaine-warner", "VA", "Kaine", "Warner", "Democrat", typ_sen)

    # 4: same party vs different parties, over time
    cur_same, cur_mix = typ_sen.loc[latest], mix_sen.loc[latest]
    add("senate-same-vs-mixed", "Same state, different vote: Senate",
        "Two senators from one state: how often they split depends on party",
        f"{cur_same:.1f}% vs {cur_mix:.0f}%",
        f"Median share of votes split by same-party senator pairs, and by pairs from different parties, in the "
        f"{ordinal(latest)} Congress.",
        line_svg([("Different parties", mix_sen.to_dict(), "#8A8580", False),
                  ("Same party", typ_sen.to_dict(), C["accent"], False)], 560, 300),
        (f"Every state has two senators who answer to the same voters. When they're from the same party, they "
         f"rarely split: the typical same-party pair voted opposite ways on {cur_same:.1f}% of shared votes in the "
         f"{so_far}. When they're from different parties, the typical pair split on {cur_mix:.0f}%. That gap has "
         f"been there in every Congress since {year(int(typ_sen.index.min()))}."),
        (f"Card comparing same-party and different-party senator pairs from one state. Large text: {cur_same:.1f}% vs "
         f"{cur_mix:.0f}%. Line chart by Congress: different-party pairs from {mix_sen.min():.0f}% to "
         f"{mix_sen.max():.0f}%, same-party pairs from {typ_sen.min():.1f}% to {typ_sen.max():.1f}%."),
        link_state("KY"), note="Lines: the median pair in each group, each Congress.")

    # 5: top same-party senate pairs now
    top_s = s_ok[(s_ok["congress"] == latest) & s_ok["same_side"]].sort_values("split_pct", ascending=False).head(6)
    rows = [(f"{r.state}: {last(r.name_a)} and {last(r.name_b)}", r.split_pct,
             f"  {r.side[0]}") for r in top_s.itertuples()]
    t0 = top_s.iloc[0]
    add("senate-top-same-party-pairs", "Same state, different vote: Senate",
        "The same-party senator pairs who split most often", f"{len(s_ok[(s_ok['congress'] == latest) & s_ok['same_side']])}",
        f"same-party senator pairs from one state in the {ordinal(latest)} Congress. These six split most often.",
        hbar_svg(rows, 600),
        (f"Of the {len(s_ok[(s_ok['congress'] == latest) & s_ok['same_side']])} pairs of same-party senators from "
         f"one state in the {so_far}, these split most often: " + "; ".join(
             f"{name(r.name_a)} and {name(r.name_b)} ({r.state}, {r.side[0]}) {r.split_pct:.1f}%"
             for r in top_s.itertuples()) + f". The typical pair: {typ_sen.loc[latest]:.1f}%."),
        "Bar chart of the six same-party senator pairs who split most often: " + "; ".join(
            f"{r.state} {name(r.name_a)} and {name(r.name_b)}, {r.split_pct:.1f}%" for r in top_s.itertuples()) + ".",
        link_state(t0["state"]), note="R and D: the pair's party. Share of shared roll calls where one voted Yea and "
                                     "the other Nay.")

    # 6: different-party delegations now
    mixed = s_ok[(s_ok["congress"] == latest) & ~s_ok["same_side"]].sort_values("split_pct", ascending=False)
    rows = [(f"{r.state}: {last(r.name_a)} and {last(r.name_b)}", r.split_pct, "")
            for r in mixed.itertuples()]
    add("senate-split-delegations", "Same state, different vote: Senate",
        f"Only {len(mixed)} states have one senator from each party", f"{mixed['split_pct'].min():.0f}% to "
                                                                       f"{mixed['split_pct'].max():.0f}%",
        f"of shared votes went opposite ways for those {len(mixed)} pairs in the {ordinal(latest)} Congress.",
        hbar_svg(rows, 600, color="#8A8580"),
        (f"In the {so_far}, {len(mixed)} states have one Democratic (or Democratic-caucusing) senator and one "
         "Republican: " + "; ".join(f"{STATES[r.state]}, {name(r.name_a)} and {name(r.name_b)}, split on "
                                    f"{r.split_pct:.1f}% of shared votes" for r in mixed.itertuples())
         + ". Angus King is an Independent who caucuses with Democrats."),
        "Bar chart of the senator pairs from different parties: " + "; ".join(
            f"{r.state} {name(r.name_a)} and {name(r.name_b)}, {r.split_pct:.1f}%" for r in mixed.itertuples()) + ".",
        link_state(mixed.iloc[-1]["state"]))

    # 7 and 8: House members over time
    def member_post(slug, who, st, side_word):
        m = hs[hs["name"].str.startswith(who) & (hs["state"] == st)].set_index("congress").sort_index()
        cur = m.loc[latest]
        assert cur["rank"] == 1, f"{who} is not the most split member of the {st} delegation"
        nm = name(cur["name"])
        first = int(m.index.min())
        series = [(last(cur["name"]), m["avg_split"].to_dict(), C["accent"], False),
                  ("Typical member", typ_house.loc[first:].to_dict(), C["muted"], True)]
        head = f"{nm} splits from fellow {STATES[st]} {side_word}s more than anyone in the delegation"
        line = (f"average share of votes where {last(cur['name'])} voted opposite a {STATES[st]} {ADJ[side_word]} colleague, "
                f"across {int(cur['colleagues'])} colleagues in the {ordinal(latest)} Congress.")
        add(slug, f"Same state, different vote: House, {STATES[st]}", head, f"{cur['avg_split']:.1f}%", line,
            line_svg(series, 560, 300),
            (f"{nm} ({side_word[0]}-{st}) votes the opposite way from other {STATES[st]} House {side_word}s more often "
             f"than anyone else in that group. In the {so_far}, his average split with his {int(cur['colleagues'])} "
             f"{side_word} colleagues from {STATES[st]} was {cur['avg_split']:.1f}%, most of all with "
             f"{name(cur['most_split_with'])} ({cur['most_split_pct']:.1f}%). The typical House member splits with "
             f"their state's party colleagues on about {typ_house.loc[latest]:.0f}% of votes. A split is a fact about "
             "the record, not a judgment."),
            (f"Card about {nm}. Large number: {cur['avg_split']:.1f}% average split with {STATES[st]} {side_word} "
             f"colleagues in the {ordinal(latest)} Congress. Line chart by Congress: "
             + ", ".join(f"{year(c)}: {v:.0f}%" for c, v in m["avg_split"].items())
             + ", above a dashed line for the typical member."),
            link_state(st, "house"), note="Average, over each colleague, of the share of shared roll calls where one "
                                          "voted Yea and the other Nay.")

    member_post("house-massie", "Massie", "KY", "Republican")
    member_post("house-cuellar", "Cuellar", "TX", "Democrat")

    # 9: top House members now
    top_h = now_h.head(8)
    rows = [(f"{name(r.name)} ({r.party[0]}-{r.state})", r.avg_split, "") for r in top_h.itertuples()]
    add("house-top-members", "Same state, different vote: House",
        "House members who split most from their own state's party", f"{typ_house.loc[latest]:.1f}%",
        f"is the typical member's average split with their state's party colleagues in the {ordinal(latest)} "
        "Congress. These eight split most.",
        hbar_svg(rows, 600),
        (f"Most House members vote with their state's party colleagues nearly all the time: the typical member split "
         f"on {typ_house.loc[latest]:.1f}% of shared votes in the {so_far}. These members split most often: "
         + "; ".join(f"{name(r.name)} ({r.party[0]}-{r.state}) {r.avg_split:.1f}%" for r in top_h.itertuples())
         + ". Members with fewer than two same-party colleagues from their state aren't ranked."),
        "Bar chart of the eight House members with the highest average split from same-party colleagues from their "
        "state: " + "; ".join(f"{name(r.name)} {r.avg_split:.1f}%" for r in top_h.itertuples()) + ".",
        f"{SITE}/Same_State_Different_Vote?chamber=house")

    # 10: Fitzpatrick and Perry over time
    fp = pair(H, "Fitzpatrick", "Perry")
    fp = fp[fp["both_voted"] >= MIN_SHARED["House"]]
    cur = fp.loc[latest]
    typ_pair_h = H.groupby("congress")["split_pct"].median()
    first = int(fp.index.min())
    add("house-fitzpatrick-perry", "Same state, different vote: House, Pennsylvania",
        f"Brian Fitzpatrick and Scott Perry: two Pennsylvania Republicans, opposite votes on up to {fp['split_pct'].max():.0f}% of roll calls",
        f"{fp['split_pct'].max():.0f}%",
        f"of shared votes went opposite ways at the peak, in the {ordinal(int(fp['split_pct'].idxmax()))} Congress. "
        f"So far in the {ordinal(latest)}: {cur['split_pct']:.1f}%.",
        line_svg([("These two", fp["split_pct"].to_dict(), C["accent"], False),
                  ("Typical pair", typ_pair_h.loc[first:].to_dict(), C["muted"], True)], 560, 300),
        (f"Brian Fitzpatrick and Scott Perry are both Pennsylvania Republicans in the House. In the "
         f"{ordinal(int(fp['split_pct'].idxmax()))} Congress they voted opposite ways on "
         f"{fp['split_pct'].max():.1f}% of the votes both cast; in the {so_far}, {cur['split_pct']:.1f}% "
         f"({int(cur['splits'])} of {int(cur['both_voted'])}). A typical pair of same-party House members from one "
         f"state splits on about {typ_pair_h.loc[latest]:.0f}%."),
        ("Card about Brian Fitzpatrick and Scott Perry. Line chart by Congress of the share of shared votes they "
         "split: " + ", ".join(f"{year(c)}: {v:.0f}%" for c, v in fp["split_pct"].items())
         + ", above a dashed line for the typical same-party pair."),
        link_state("PA", "house"))

    # 11: the typical House member
    under5, under10 = (now_h["avg_split"] < 5).mean(), (now_h["avg_split"] < 10).mean()
    add("house-typical-member", "Same state, different vote: House",
        "Most House members rarely split from their own state's party", f"{under10:.0%}",
        f"of House members split with their state's party colleagues on fewer than 1 in 10 votes in the "
        f"{ordinal(latest)} Congress. {under5:.0%} on fewer than 1 in 20.",
        hist_svg(now_h["avg_split"], 560, 290),
        (f"How often do House members vote the opposite way from colleagues of their own party from their own "
         f"state? In the {so_far}, {under10:.0%} of members split on fewer than 1 in 10 shared votes, and "
         f"{under5:.0%} on fewer than 1 in 20. Only {int((now_h['avg_split'] >= 15).sum())} of {len(now_h)} split on "
         "15% or more."),
        (f"Histogram of {len(now_h)} House members by average split with same-party colleagues from their state. Most "
         f"members are under 5%: {under5:.0%}. {under10:.0%} are under 10%."),
        f"{SITE}/Same_State_Different_Vote?chamber=house",
        note=f"Each bar: number of members in a 2.5-point range. {len(now_h)} members with at least two same-party "
             "colleagues from their state.")

    # 12 to 15: single House members now
    def now_post(slug, who, st, side_word):
        r = now_h[now_h["name"].str.startswith(who) & (now_h["state"] == st)].iloc[0]
        assert r["rank"] == 1, f"{who} is not the most split member of the {st} delegation"
        nm = name(r["name"])
        group = h_ok[(h_ok["congress"] == latest) & (h_ok["state"] == st) & (h_ok["side"] == r["side"])]
        rows = [(name(x.name), x.avg_split, "") for x in group.sort_values("avg_split", ascending=False).head(7).itertuples()]
        head = f"{nm} and the other {STATES[st]} House {side_word}s"
        add(slug, f"Same state, different vote: House, {STATES[st]}", head, f"{r['avg_split']:.1f}%",
            f"average split with {int(r['colleagues'])} {STATES[st]} {ADJ[side_word]} colleagues in the "
            f"{ordinal(latest)} Congress, the most in that group of {int(r['delegation'])}.",
            hbar_svg(rows, 600),
            (f"{nm} ({side_word[0]}-{st}) voted the opposite way from other {STATES[st]} House {side_word}s more "
             f"often than anyone else in that group in the {so_far}: an average of {r['avg_split']:.1f}% of shared "
             f"votes, most of all with {name(r['most_split_with'])} ({r['most_split_pct']:.1f}%). The typical House "
             f"member splits on about {typ_house.loc[latest]:.0f}%."),
            (f"Bar chart of {STATES[st]} House {side_word}s by average split with each other: "
             + "; ".join(f"{a} {v:.1f}%" for a, v, _ in rows) + "."),
            link_state(st, "house"), note=f"The {len(rows)} highest of {len(group)} {STATES[st]} {side_word}s compared.")

    now_post("house-davis-nc", "Davis, Don", "NC", "Democrat")
    now_post("house-gluesenkamp-perez", "Perez, Marie", "WA", "Democrat")
    now_post("house-brecheen-ok", "Brecheen", "OK", "Republican")

    # Maine's two House Democrats: a pair, since there is no third member to average over
    gp = pair(H, "Golden", "Pingree")
    cur = gp.loc[latest]
    typ_pair_now = H[H["congress"] == latest]["split_pct"].median()
    add("house-golden-pingree", "Same state, different vote: House, Maine",
        "Jared Golden and Chellie Pingree: Maine's two House Democrats", f"{cur['split_pct']:.1f}%",
        f"of the votes both cast in the {ordinal(latest)} Congress went opposite ways ({int(cur['splits'])} of "
        f"{int(cur['both_voted'])}).",
        hbar_svg([("Golden and Pingree", cur["split_pct"], ""), ("Typical same-party House pair", typ_pair_now, "")],
                 600),
        (f"Maine has two House members, both Democrats: Jared Golden and Chellie Pingree. In the {so_far}, they voted "
         f"opposite ways on {int(cur['splits'])} of the {int(cur['both_voted'])} roll calls both voted on "
         f"({cur['split_pct']:.1f}%). A typical pair of same-party House members from one state splits on about "
         f"{typ_pair_now:.0f}%. A split is a fact about the record, not a judgment."),
        (f"Card about Jared Golden and Chellie Pingree. Two bars: Golden and Pingree split on {cur['split_pct']:.1f}% "
         f"of shared votes; the typical same-party House pair, {typ_pair_now:.1f}%."),
        link_state("ME", "house"))

    # 16: the biggest delegations
    big = []
    for st, side_word in (("CA", "Democrat"), ("TX", "Republican"), ("TX", "Democrat"), ("FL", "Republican"),
                          ("NY", "Democrat")):
        g = now_h[(now_h["state"] == st) & (now_h["side"] == side_word)].sort_values("avg_split", ascending=False)
        if len(g):
            big.append((st, side_word, g.iloc[0], len(g)))
    big.sort(key=lambda b: -b[2]["avg_split"])
    rows = [(f"{STATES[st]} {sw}s ({n}): {name(r['name'])}", r["avg_split"], "") for st, sw, r, n in big]
    add("house-biggest-delegations", "Same state, different vote: House",
        "In the biggest House delegations, who splits most from the group?", f"{len(big)}",
        "of the largest same-party delegations, and the member in each who splits most from the rest.",
        hbar_svg(rows, 600, fs=16),
        ("The largest same-party House delegations, and the member in each who voted opposite their colleagues most "
         f"often in the {so_far}: " + "; ".join(f"{STATES[st]} {sw}s ({n} members), {name(r['name'])}, "
                                                 f"{r['avg_split']:.1f}%" for st, sw, r, n in big) + "."),
        "Bar chart of the member who splits most in each large delegation: " + "; ".join(
            f"{STATES[st]} {sw}s, {name(r['name'])}, {r['avg_split']:.1f}%" for st, sw, r, n in big) + ".",
        f"{SITE}/Same_State_Different_Vote?chamber=house", note="Number of members in the delegation in parentheses.")

    # 17 to 19: the state map
    lo_u, hi_u = states["avg_unity"].min(), states["avg_unity"].max()
    colors = {st: blend(PURPLE_LO, PURPLE_HI, (v - lo_u) / (hi_u - lo_u)) for st, v in states["avg_unity"].items()}
    low3 = states.sort_values("avg_unity").head(3)
    add("map-party-unity", "How each state's members vote",
        "Which states' members vote with their party most?", f"{lo_u:.0f}% to {hi_u:.0f}%",
        "average party unity of each state's current members. Lowest: " + ", ".join(
            f"{STATES[s]} {v:.0f}%" for s, v in low3["avg_unity"].items()) + ".",
        tile_map_svg(colors, 540) + scale_svg(f"Lower ({lo_u:.0f}%)", f"Higher ({hi_u:.0f}%)", PURPLE_LO, PURPLE_HI, 540),
        (f"Party unity is the share of party-line votes on which a member sided with their own party. Averaged across "
         f"each state's current members, every state is between {lo_u:.0f}% and {hi_u:.0f}%. The lowest: "
         + ", ".join(f"{STATES[s]} ({v:.1f}%)" for s, v in low3["avg_unity"].items())
         + ". The highest: " + ", ".join(f"{STATES[s]} ({v:.1f}%)" for s, v in
                                        states.sort_values("avg_unity").tail(3)["avg_unity"].items())
         + ". Darker means higher. Hover any state on the map to see its members."),
        (f"Tile map of the 50 states shaded by average party unity of their members, {lo_u:.0f}% (light) to "
         f"{hi_u:.0f}% (dark). Lowest: " + ", ".join(f"{STATES[s]} {v:.1f}%" for s, v in low3["avg_unity"].items())
         + "."),
        f"{SITE}/", source=f"Voteview roll calls through {through}. Each member's latest Congress.")

    lo_m, hi_m = states["avg_missed"].min(), states["avg_missed"].max()
    colors = {st: blend(PURPLE_LO, PURPLE_HI, (v - lo_m) / (hi_m - lo_m)) for st, v in states["avg_missed"].items()}
    most = states.sort_values("avg_missed", ascending=False).head(3)
    least = states.sort_values("avg_missed").head(3)
    add("map-missed-votes", "How each state's members vote",
        "Which states' members miss the most votes?", f"{lo_m:.1f}% to {hi_m:.1f}%",
        "average share of roll calls missed by each state's current members. Most: " + ", ".join(
            f"{STATES[s]} {v:.1f}%" for s, v in most["avg_missed"].items()) + ".",
        tile_map_svg(colors, 540) + scale_svg(f"Fewer ({lo_m:.1f}%)", f"More ({hi_m:.1f}%)", PURPLE_LO, PURPLE_HI, 540),
        ("How often do members of Congress miss roll calls? Averaged across each state's current members, from "
         f"{lo_m:.1f}% to {hi_m:.1f}% of the roll calls held while they served. Most missed: "
         + ", ".join(f"{STATES[s]} ({v:.1f}%)" for s, v in most["avg_missed"].items()) + ". Fewest: "
         + ", ".join(f"{STATES[s]} ({v:.1f}%)" for s, v in least["avg_missed"].items())
         + ". Absences have many causes, from illness to campaigning, and a roll call doesn't record why."),
        (f"Tile map of the 50 states shaded by the average share of roll calls their members missed, {lo_m:.1f}% "
         f"(light) to {hi_m:.1f}% (dark). Most: " + ", ".join(f"{STATES[s]} {v:.1f}%" for s, v in most["avg_missed"].items())
         + "."),
        f"{SITE}/", source=f"Voteview roll calls through {through}. Each member's latest Congress.")

    one_party = states[(states["dem"] == 0) | (states["rep"] == 0)]
    mid = "#C3C6CC"
    colors = {st: (blend(C["dem"], mid, r / 0.5) if r <= 0.5 else blend(mid, C["rep"], (r - 0.5) / 0.5))
              for st, r in states["rep_share"].items()}
    all_r, all_d = (one_party["dem"] == 0).sum(), (one_party["rep"] == 0).sum()
    add("map-party-mix", "How each state's members vote",
        "In 20 states, every member of Congress is from one party" if len(one_party) == 20 else
        f"In {len(one_party)} states, every member of Congress is from one party", f"{len(one_party)}",
        f"states where all senators and representatives share a party: {all_r} all Republican, {all_d} all Democratic "
        "or Democratic-caucusing.",
        tile_map_svg(colors, 540, marked=set(one_party.index)) + scale_svg("All Democrats", "All Republicans",
                                                                           C["dem"], C["rep"], 540, mid=mid),
        (f"Counting senators and representatives together, {len(one_party)} states send a delegation entirely from "
         f"one party: {all_r} all Republican ({', '.join(STATES[s] for s in one_party[one_party['dem'] == 0].index)}) "
         f"and {all_d} all Democratic or Democratic-caucusing "
         f"({', '.join(STATES[s] for s in one_party[one_party['rep'] == 0].index)}). Most are smaller states with "
         "one or two House seats. Click any state on the map to see its members."),
        (f"Tile map of the 50 states shaded from blue (all Democrats) through gray to red (all Republicans) by their "
         f"delegation's party mix. {len(one_party)} states with a one-party delegation are outlined."),
        f"{SITE}/", note="Outlined: every senator and representative from one party, counting Independents with the party "
                          "they caucus with.",
        source="Current members of Congress, from the unitedstates/congress-legislators project.")

    # 20: what's new
    add("new-same-state-different-vote", "New on PartyCohesion",
        "Same state, different vote: see how often your state's members vote opposite ways",
        f"{typ_sen.loc[latest]:.1f}%", f"of shared votes split by the typical pair of same-party senators from one state "
                                      f"in the {ordinal(latest)} Congress. House members: {typ_house.loc[latest]:.1f}%.",
        hbar_svg([("Senators, different parties", cur_mix, ""), ("House, same party (typical)", typ_house.loc[latest], ""),
                  ("Senators, same party (typical)", cur_same, "")], 600),
        ("New on PartyCohesion: Same State, Different Vote. Pick your state to see how often its two senators, and "
         "its House members of the same party, cast opposite votes, and every roll call where they did, with which "
         "member broke with their party. Each member's page now shows their own numbers too, and the map on the home "
         "page opens every state's delegation."),
        ("Card announcing Same State, Different Vote. Bars: senators from different parties split on "
         f"{cur_mix:.0f}% of shared votes, typical same-party House members {typ_house.loc[latest]:.1f}%, typical "
         f"same-party senators {cur_same:.1f}%."),
        f"{SITE}/Same_State_Different_Vote")
    return posts


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    posts = build()
    if args.list:
        for p in posts:
            print(f"{p['slug']}: {p['head']}")
        return
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    for p in posts:
        if "—" in p["caption"] + p["html"] + p["alt"]:
            raise ValueError(f"{p['slug']}: em dash")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for p in posts:
            pg = browser.new_page(viewport={"width": 1200, "height": 627}, device_scale_factor=1)
            pg.set_content(p["html"], wait_until="networkidle")
            pg.evaluate("document.fonts.ready")
            pg.wait_for_timeout(300)
            pg.screenshot(path=str(OUT / f"{p['slug']}-wide.png"))
            pg.close()
            (OUT / f"{p['slug']}.txt").write_text(p["caption"] + "\n")
            (OUT / f"{p['slug']}.alt.txt").write_text(p["alt"][:1000] + "\n")
            print(f"Wrote {p['slug']}")
        browser.close()


if __name__ == "__main__":
    main()
