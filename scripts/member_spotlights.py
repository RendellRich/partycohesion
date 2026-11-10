"""Member spotlight cards: one member's voting record in the current Congress, as a share image and a caption.

Who gets featured is decided by a fixed rule, never by hand: every current member with enough party-line votes
is shuffled with a published seed, then the order alternates parties and mixes in senators, so no party or person
is singled out. See spotlight_order().

  python scripts/member_spotlights.py --sample           render three samples to docs/social/members/
  python scripts/member_spotlights.py --bioguide R000575  render one member

Images use the same style as scripts/make_social_cards.py. No photos of members: the highlighted seat on the
chamber map is the visual.
"""

from __future__ import annotations

import argparse
import random
import sys
from html import escape
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
import make_social_cards as mc  # noqa: E402
from seat_map import seat_positions  # noqa: E402
from ui import STATES, display_name  # noqa: E402

DATA = ROOT / "data"
OUT = ROOT / "docs" / "social" / "members"
MIN_VOTES = 50  # members with fewer party-line votes this Congress (new arrivals) aren't featured yet
SEED = 119  # published so anyone can reproduce the order


def member_url(bioguide: str) -> str:
    return f"{mc.SITE}/Member_Explorer?member={bioguide}"


def load() -> dict:
    members = pd.read_csv(DATA / "members_processed.csv")
    latest = int(members["congress"].max())
    cur = (members[members["congress"] == latest].sort_values("unity_votes_cast")
           .drop_duplicates(["chamber", "icpsr"], keep="last"))
    missed = pd.read_csv(DATA / "missed_votes.csv")
    missed = missed[missed["congress"] == latest][["chamber", "icpsr", "eligible", "missed"]]
    changes = pd.read_csv(DATA / "vote_changes.csv")
    apart = changes[changes["apart"]].groupby("icpsr").size().rename("changed_apart")
    cur = cur.merge(missed, on=["chamber", "icpsr"], how="left").merge(apart, on="icpsr", how="left")
    cur["changed_apart"] = cur["changed_apart"].fillna(0).astype(int)
    summary = pd.read_csv(DATA / "unity_summary.csv")
    return {"members": cur, "latest": latest, "through": mc.fmt_date(summary["latest_vote_date"].max())}


def stats(d: dict, bioguide: str) -> dict:
    m = d["members"]
    row = m[m["bioguide_id"] == bioguide].iloc[0]
    same = m[(m["chamber"] == row["chamber"]) & (m["caucus"] == row["caucus"])]
    peers = same[same["unity_votes_cast"] >= MIN_VOTES]
    below = (peers["party_unity_pct"] < row["party_unity_pct"]).mean() * 100
    return {
        "row": row, "name": display_name(row["name"]), "party": row["caucus"], "chamber": row["chamber"],
        "state": STATES.get(row["state_abbrev"], row["state_abbrev"]), "abbrev": row["state_abbrev"],
        "pct": float(row["party_unity_pct"]), "with": int(row["votes_with_party"]), "cast": int(row["unity_votes_cast"]),
        # same average as the Overview page and the Senate card
        "avg": float(same["party_unity_pct"].mean()), "peers": len(peers), "below": below,
        "missed_pct": float(row["missed"] / row["eligible"] * 100) if row.get("eligible", 0) else None,
        "changed": int(row["changed_apart"]), "latest": d["latest"], "through": d["through"],
    }


def spotlight_order(d: dict, seed: int = SEED) -> list[str]:
    """Bioguide ids in posting order: shuffled with a fixed seed, then interleaved so parties alternate
    (Democrat, Republican, ...) and every fourth spotlight is a senator. Independents join the party they caucus with."""
    m = d["members"][d["members"]["unity_votes_cast"] >= MIN_VOTES]
    rng = random.Random(seed)
    queues = {}
    for (chamber, party), g in m.groupby(["chamber", "caucus"]):
        ids = sorted(g["bioguide_id"])
        rng.shuffle(ids)
        queues[(chamber, party)] = ids
    order, parties, i = [], ["Democrat", "Republican"], 0
    while any(queues.values()):
        chamber = "Senate" if len(order) % 4 == 3 else "House"
        party = parties[i % 2]
        q = queues.get((chamber, party)) or queues.get(("House" if chamber == "Senate" else "Senate", party))
        if not q:
            q = next(v for v in queues.values() if v)
        order.append(q.pop(0))
        i += 1
    return order


def seat_svg(d: dict, s: dict, width: int) -> str:
    m = d["members"]
    m = m[(m["chamber"] == s["chamber"]) & (m["unity_votes_cast"] >= MIN_VOTES)]
    m = m.sort_values("nominate_dim1", na_position="last").reset_index(drop=True)
    seats = pd.concat([m, seat_positions(len(m), 12 if s["chamber"] == "House" else 6)], axis=1)
    h, r = width * 0.52, width / 2 * 0.97
    dot = width / (120 if s["chamber"] == "House" else 48)
    out = []
    for x, y, p, b in zip(seats["x"], seats["y"], seats["party"], seats["bioguide_id"]):
        if b == s["row"]["bioguide_id"]:
            continue
        out.append(f'<circle cx="{width / 2 + x * r:.1f}" cy="{h - 4 - y * r:.1f}" r="{dot:.1f}" '
                   f'fill="{mc.PARTY.get(p, mc.C["ind"])}" fill-opacity="0.28"/>')
    me = seats[seats["bioguide_id"] == s["row"]["bioguide_id"]].iloc[0]
    cx, cy = width / 2 + me["x"] * r, h - 4 - me["y"] * r
    out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{dot * 2.6:.1f}" fill="none" stroke="{mc.C["accent"]}" '
               f'stroke-width="{max(2, dot * 0.6):.1f}"/>')
    out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{dot * 1.3:.1f}" fill="{mc.PARTY.get(me["party"], mc.C["ind"])}"/>')
    return f'<svg width="{width}" height="{h:.0f}" viewBox="0 0 {width} {h:.0f}">{"".join(out)}</svg>'


ADJ = {"Democrat": "Democratic", "Republican": "Republican", "Independent": "Independent"}


def compare_bar(s: dict, width: int, fs: int) -> str:
    """Member's rate as a bar on an 80 to 100% scale (clamped), with a tick and label for the party average."""
    lo = 80

    def x(v):
        return max(0.0, min(1.0, (v - lo) / (100 - lo))) * width

    col = mc.PARTY.get(s["party"], mc.C["ind"])
    ax = x(s["avg"])
    anchor, tx = ("end", width) if ax > width * 0.7 else ("start", 0) if ax < width * 0.3 else ("middle", ax)
    label = f"{s['chamber']} {ADJ[s['party']]} average {s['avg']:.1f}%  ·  scale 80 to 100%"
    h = fs * 2.6
    return (f'<svg width="{width}" height="{h:.0f}" viewBox="0 0 {width} {h:.0f}">'
            f'<rect x="0" y="{fs * 0.4:.0f}" width="{width}" height="{fs * 0.5:.0f}" rx="{fs * 0.25:.0f}" fill="{mc.C["border"]}"/>'
            f'<rect x="0" y="{fs * 0.4:.0f}" width="{x(s["pct"]):.1f}" height="{fs * 0.5:.0f}" rx="{fs * 0.25:.0f}" fill="{col}"/>'
            f'<line x1="{ax:.1f}" x2="{ax:.1f}" y1="0" y2="{fs * 1.3:.0f}" stroke="{mc.C["text"]}" stroke-width="2"/>'
            f'<text x="{tx:.1f}" y="{fs * 2.3:.0f}" text-anchor="{anchor}" font-family="Public Sans" '
            f'font-size="{fs * 0.8:.0f}" fill="{mc.C["muted"]}">{escape(label)}</text></svg>')


def facts_list(s: dict) -> list[str]:
    plural = f"{s['chamber']} {s['party']}s"
    out = [f"Voted with their party more often than {s['below']:.0f}% of {plural}"]
    if s["missed_pct"] is not None:
        out.append(f"Missed {s['missed_pct']:.1f}% of roll calls this Congress")
    times = "time" if s["changed"] == 1 else "times"
    out.append(f"Changed their vote on the same bill while their party didn't: {s['changed']} {times} since 2007")
    return out


def card(d: dict, s: dict, size: str) -> str:
    years = f"{2 * s['latest'] + 1787} to {2 * s['latest'] + 1788}"
    label = f"Member spotlight · {s['chamber']} · {years} Congress"
    who = f"{s['party']} · {s['state']}"
    big = f"{s['pct']:.1f}%"
    line = f"voted with their party on {s['with']} of {s['cast']} party-line votes"
    src = f"Voteview roll calls through {s['through']}. Members featured in a fixed random rotation."
    items = "".join(f'<li>{escape(t)}</li>' for t in facts_list(s))
    seat_note = f"Their seat, among {s['chamber']} members ordered by voting record"
    css = (".facts{list-style:none;margin:0;padding:0}.facts li{padding:8px 0;border-top:1px solid "
           f"{mc.C['border']};color:{mc.C['body']}}}")
    if size == "wide":
        body = f"""
<div class="muted" style="font-size:18px">{escape(label)}</div>
<div style="display:flex;gap:44px;margin-top:8px;flex:1">
  <div style="flex:1.1">
    <h1 style="font-size:46px;line-height:1.05">{escape(s['name'])}</h1>
    <div class="body" style="font-size:21px;margin-top:6px">{escape(who)}</div>
    <div style="display:flex;align-items:baseline;gap:14px;margin-top:16px">
      <div class="accent" style="font-family:'Source Serif 4';font-weight:700;font-size:72px;line-height:1">{big}</div>
      <div class="body" style="font-size:19px;line-height:1.35;max-width:300px">{escape(line)}</div></div>
    <div style="margin-top:12px">{compare_bar(s, 560, 18)}</div>
  </div>
  <div style="flex:0.9;display:flex;flex-direction:column;align-items:center;justify-content:center">
    {seat_svg(d, s, 440)}
    <div class="muted" style="font-size:15px;margin-top:8px">{escape(seat_note)}</div>
  </div>
</div>
<ul class="facts" style="font-size:17px;margin-bottom:10px">{items}</ul>{mc.foot(src, size)}"""
    else:
        body = f"""
<div class="muted" style="font-size:24px;margin-top:16px">{escape(label)}</div>
<h1 style="font-size:66px;line-height:1.05;margin-top:12px">{escape(s['name'])}</h1>
<div class="body" style="font-size:30px;margin-top:8px">{escape(who)}</div>
<div class="accent" style="font-family:'Source Serif 4';font-weight:700;font-size:128px;line-height:1;margin-top:34px">{big}</div>
<div class="body" style="font-size:30px;line-height:1.35;margin-top:8px">{escape(line)}</div>
<div style="margin-top:22px">{compare_bar(s, 920, 26)}</div>
<div style="display:flex;flex-direction:column;align-items:center;margin-top:20px">{seat_svg(d, s, 560)}
<div class="muted" style="font-size:20px;margin-top:8px">{escape(seat_note)}</div></div>
<ul class="facts" style="font-size:23px;margin-top:18px">{items}</ul>{mc.foot(src, size)}"""
    return mc.page(body, size, css)


def caption(s: dict) -> str:
    abbr = s["party"][0]
    lines = [
        f"Member spotlight: {s['name']} ({abbr}-{s['abbrev']}), {s['chamber']}.",
        f"In the current Congress, {s['name']} voted with the {ADJ[s['party']]} majority on {s['with']} of {s['cast']} "
        f"party-line votes ({s['pct']:.1f}%). The {s['chamber']} {ADJ[s['party']]} average is {s['avg']:.1f}%.",
        "",
        "Members are featured in a fixed random rotation, not chosen by hand.",
        "Data: Voteview",
        member_url(s["row"]["bioguide_id"]),
    ]
    return "\n".join(lines)


def render(d: dict, bioguides: list[str]) -> list[Path]:
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    paths = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for b in bioguides:
            s = stats(d, b)
            for size, (w, h) in mc.SIZES.items():
                pg = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
                pg.set_content(card(d, s, size), wait_until="networkidle")
                pg.evaluate("document.fonts.ready")
                pg.wait_for_timeout(300)
                path = OUT / f"{b}-{size}.png"
                pg.screenshot(path=str(path))
                if size == "tall":
                    pg.screenshot(path=str(OUT / f"{b}-tall.jpg"), type="jpeg", quality=92)
                paths.append(path)
                pg.close()
            (OUT / f"{b}.txt").write_text(caption(s) + "\n")
        browser.close()
    return paths


def samples(d: dict) -> list[str]:
    """First House Democrat, first House Republican and first senator in the rotation."""
    order, m = spotlight_order(d), d["members"].set_index("bioguide_id")
    pick = {}
    for b in order:
        key = "Senate" if m.loc[b, "chamber"] == "Senate" else m.loc[b, "caucus"]
        pick.setdefault(key, b)
        if len(pick) == 3:
            break
    return [pick["Democrat"], pick["Republican"], pick["Senate"]]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--bioguide", nargs="*", default=[])
    a = ap.parse_args()
    d = load()
    ids = samples(d) if a.sample else a.bioguide
    for path in render(d, ids):
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
