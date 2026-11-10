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
import re
import sys
from html import escape
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
import make_social_cards as mc  # noqa: E402
from seat_map import seat_positions  # noqa: E402
from chart_utils import ordinal  # noqa: E402
from ui import STATES, bill_label, display_name  # noqa: E402
import floor_remarks  # noqa: E402
from vote_index import load_matrix  # noqa: E402

DATA = ROOT / "data"
OUT = ROOT / "docs" / "social" / "members"
MIN_VOTES = 50  # members with fewer party-line votes this Congress (new arrivals) aren't featured yet
SEED = 119  # published so anyone can reproduce the order


def member_url(bioguide: str) -> str:
    return f"{mc.SITE}/Member_Explorer?member={bioguide}"


READY_SHARE = 0.8  # a new Congress is used once this share of its members have MIN_VOTES party-line votes


def spotlight_congress(members: pd.DataFrame) -> tuple[int, bool]:
    """(Congress, is it the newest one). A new Congress starts every member's count at zero, so for its first weeks
    the spotlights keep using the one before, labeled as its final record, until most members have enough votes."""
    newest = int(members["congress"].max())
    cur = members[members["congress"] == newest].drop_duplicates(["chamber", "icpsr"])
    ready = (cur["unity_votes_cast"] >= MIN_VOTES).sum() >= READY_SHARE * len(cur)
    if ready or (members["congress"] == newest - 1).sum() == 0:
        return newest, True
    return newest - 1, False


def load(congress: int | None = None) -> dict:
    members = pd.read_csv(DATA / "members_processed.csv")
    latest, current = (congress, congress == int(members["congress"].max())) if congress else spotlight_congress(members)
    cur = (members[members["congress"] == latest].sort_values("unity_votes_cast")
           .drop_duplicates(["chamber", "icpsr"], keep="last"))
    missed = pd.read_csv(DATA / "missed_votes.csv")
    missed = missed[missed["congress"] == latest][["chamber", "icpsr", "eligible", "missed"]]
    changes = pd.read_csv(DATA / "vote_changes.csv")
    apart = changes[changes["apart"]].groupby("icpsr").size().rename("changed_apart")
    cur = cur.merge(missed, on=["chamber", "icpsr"], how="left").merge(apart, on="icpsr", how="left")
    cur["changed_apart"] = cur["changed_apart"].fillna(0).astype(int)
    # The name members go by ("Raja Krishnamoorthi"), from Congress.gov, where Voteview has "Krishnamoorthi, S. Raja".
    details = pd.read_csv(DATA / "member_details.csv", usecols=["bioguide_id", "full_name"])
    cur = cur.merge(details.drop_duplicates("bioguide_id"), on="bioguide_id", how="left")
    summary = pd.read_csv(DATA / "unity_summary.csv")
    votes = pd.read_csv(DATA / "all_votes.csv")
    votes = all_votes = votes[votes["congress"] == latest]
    titles = pd.read_csv(DATA / "bill_titles.csv")  # hand-checked titles win over ones read from vote descriptions
    titles = dict(zip(titles.loc[titles["congress"] == latest, "bill_number"], titles.loc[titles["congress"] == latest, "title"]))
    votes = votes[votes["party_unity_vote"]]
    remarks = floor_remarks.load_index()
    remarks = remarks[remarks["congress"] == latest]
    through = summary.loc[summary["congress"] == latest, "latest_vote_date"].max()
    return {"members": cur, "latest": latest, "current": current, "through": mc.fmt_date(through),
            "votes": votes, "titles": titles, "title_votes": title_votes(all_votes), "remarks": remarks}


# Questions whose vote description is the bill's own title (others describe an amendment or motion instead).
TITLE_QUESTIONS = re.compile(r"passage|suspend the rules|motion to proceed|joint resolution|concurrent resolution|"
                             r"^on (?:agreeing to )?the resolution|conference report|veto|motion to commit|recommit", re.I)
# Votes on an amendment or motion, where the vote description says what that amendment or motion would do.
PURPOSE_QUESTIONS = re.compile(r"(?<!concur in the senate )(?<!concur in senate )amendment|^on the motion$|motion to table|motion to waive|point of order", re.I)
RULE = re.compile(r"^providing for (?:the )?consideration of (?:the )?(?:bill|joint resolution|concurrent resolution|"
                  r"resolution)s? \(([^)]+)\)", re.I)
HOUSE_AMENDMENT = re.compile(r"^(.+?) of [A-Z][A-Za-z ]+? (?:Part [A-Z] )?Amendment No\. \d+ to [^:]+:\s*", re.I)


def bill_key(text: str) -> str:
    """'H.R. 2913' -> 'HR2913', as in the bill_number column."""
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def title_votes(votes: pd.DataFrame) -> pd.DataFrame:
    """Votes whose description is the bill's own title: passage, taking it up, and the like. Not the final-version
    votes (concurring, conference reports), whose description keeps the original title even when the other chamber
    replaced the bill's text, and not rules."""
    q = votes["vote_question"].fillna("")
    v = votes[q.str.contains(TITLE_QUESTIONS) & ~q.str.contains(r"concur|conference", case=False)
              & votes["bill_number"].notna() & votes["vote_desc"].notna()
              & ~votes["vote_desc"].fillna("").map(lambda t: bool(RULE.search(t)))]
    return v[["bill_number", "date", "chamber", "vote_desc"]].assign(n=v["vote_desc"].str.len())


LONG_TITLE = re.compile(r"^(?:A|An) (?:original )?(?:bill|act|joint resolution|concurrent resolution|resolution)\b", re.I)


def title_for(d: dict, bill: str, date: str) -> str | None:
    """The bill's title as of a vote: from the latest vote on the bill itself on or before that day (the Senate can
    swap a whole new text into a House bill), preferring a short title over a long "A bill to ..." one, and the
    House's on a tie. Hand-checked titles win."""
    if bill in d["titles"]:
        return d["titles"][bill]
    t = d["title_votes"]
    t = t[t["bill_number"] == bill]
    if t.empty:
        return None
    before = t[t["date"] <= date]
    t = before if len(before) else t
    short = t[~t["vote_desc"].str.match(LONG_TITLE)]  # "Ukraine Support Act" reads better than "A bill to ..."
    t = short if len(short) else t
    t = t[t["date"] == t["date"].max()]
    return t.sort_values(["chamber", "n"], key=lambda c: c.map({"House": 0, "Senate": 1}) if c.name == "chamber" else c)["vote_desc"].iloc[0]


SUBSTANTIVE = re.compile(r"^on passage|suspend the rules and pass|^on (?:the )?joint resolution$|conference report|"
                         r"concur in the|overriding the veto|objections of the president|^on the nomination|"
                         r"^on (?:agreeing to )?the (?:concurrent )?resolution(?:, as amended)?$", re.I)
NOT_SHOWN = re.compile(r"^election of the speaker", re.I)  # counted, but a vote for a person, not a measure


def apart_votes(d: dict, row: pd.Series) -> pd.DataFrame:
    """Every party-line vote this Congress where the member voted against most of their own party, with what it was
    and whether they spoke on the floor about that bill. Yea and Nay only, as in the party unity rate."""
    ids, rolls, matrix = load_matrix(d["latest"], row["chamber"])
    mine = pd.DataFrame({"rollnumber": rolls, "v": matrix[list(ids).index(row["icpsr"])]})
    mine = mine[mine["v"] != 0].copy()
    mine["vote"] = mine["v"].map({1: "Yea", -1: "Nay"})
    v = d["votes"][d["votes"]["chamber"] == row["chamber"]]
    x = mine.merge(v, on="rollnumber")
    x["party_vote"] = x["dem_position"] if row["caucus"] == "Democrat" else x["rep_position"]
    if row["caucus"] not in ("Democrat", "Republican"):
        x["party_vote"] = x["dem_position"]
    x = x[x["vote"] != x["party_vote"]].copy()
    x["remarks_url"] = floor_remarks.attach(x, row["bioguide_id"], d["remarks"])
    q = x["vote_question"].fillna("")
    # A special rule ("Providing for consideration of the bill (H.R. 2913) ...") is procedure on another bill.
    rule = x["vote_desc"].fillna("").str.extract(RULE, expand=False)
    x["rule_for"] = rule.map(lambda b: bill_key(b) if isinstance(b, str) else None)
    x["substantive"] = q.str.contains(SUBSTANTIVE) & x["rule_for"].isna()
    x["shown"] = ~q.str.contains(NOT_SHOWN)
    return x


KINDS = [(re.compile(r"cloture on the motion to proceed", re.I), "Cloture on taking up"),
         (re.compile(r"motion to proceed", re.I), "Taking up"),
         (re.compile(r"motion to discharge", re.I), "Discharging"),
         (re.compile(r"motion to table", re.I), "Tabling"),
         (re.compile(r"cloture", re.I), "Cloture on"),
         (re.compile(r"conference report|concur in", re.I), "Final version of"),
         (re.compile(r"amendment", re.I), "An amendment to"),
         (re.compile(r"veto|objections of the president", re.I), "Overriding the veto of"),
         (re.compile(r"nomination", re.I), "Nomination:"),
         (re.compile(r"passage|suspend the rules and pass|joint resolution|resolution", re.I), "Passing"),
         (re.compile(r"recommit", re.I), "Sending back to committee"),
         (re.compile(r"previous question", re.I), "Ending debate on"),
         (re.compile(r"^on the motion$", re.I), "A motion on")]


def kind(question: str) -> str:
    return next((k for pat, k in KINDS if pat.search(str(question))), str(question).removeprefix("On ").strip())


def pick(x: pd.DataFrame, n: int) -> pd.DataFrame:
    """Which apart votes to show, by a fixed rule: votes on a bill, resolution or nomination itself before
    procedural ones, then ones the member spoke about on the floor, then the most recent. One vote per bill."""
    x = x[x["shown"]].copy()
    x["has_remarks"] = x["remarks_url"].notna()
    x = x.sort_values(["substantive", "has_remarks", "date"], ascending=False)
    x["key"] = x["rule_for"].fillna(x["bill_number"]).fillna(x["vote_desc"].fillna("") + x["date"])
    return x.drop_duplicates("key").head(n)


def short(text: str, n: int) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip().rstrip(".")
    return text if len(text) <= n else text[:n - 3].rsplit(" ", 1)[0].rstrip(",;:") + "..."


def describe(d: dict, r: pd.Series, n: int = 70) -> str:
    """What the vote was on: the kind of vote, the bill and the bill's title."""
    desc = r["vote_desc"] if isinstance(r["vote_desc"], str) else ""
    if isinstance(r.get("rule_for"), str):
        bill, what = r["rule_for"], "The rule for debating"
        if str(r["vote_question"]).lower().startswith("on ordering the previous question"):
            what = "Ending debate on the rule for"
    else:
        bill, what = (r["bill_number"] if isinstance(r["bill_number"], str) else ""), kind(r["vote_question"])
    title = title_for(d, bill, r["date"]) if bill else None
    title = title or ("" if PURPOSE_QUESTIONS.search(str(r["vote_question"])) else desc)
    label = bill_label(bill) if bill else ""
    if label and title:
        return f"{what} {label}, {short(title, n)}"
    return f"{what} {label or short(title or desc or r['vote_question'], n)}"


def purpose(r: pd.Series, n: int = 180) -> str | None:
    """For a vote on an amendment or motion, what the vote record says it would do, and whose amendment it was."""
    desc = r["vote_desc"] if isinstance(r["vote_desc"], str) else ""
    if not desc or isinstance(r.get("rule_for"), str) or not PURPOSE_QUESTIONS.search(str(r["vote_question"])):
        return None
    m = HOUSE_AMENDMENT.match(desc)
    text = short(desc[m.end():] if m else desc, n)
    return f"{text} (amendment by Rep. {m.group(1)})" if m else text


def spoken_name(row: pd.Series) -> str:
    """'Jason Crow'. When Voteview's first name is only an initial ("S. Krishnamoorthi"), the Congress.gov name with
    middle initials dropped ("Raja Krishnamoorthi")."""
    name = display_name(row["name"])
    full = row.get("full_name")
    if re.match(r"^[A-Z]\.\s", name) and isinstance(full, str):
        return re.sub(r"\s+", " ", re.sub(r"\b[A-Z]\.\s", "", full).replace(", Jr.", " Jr.")).strip()
    return name


def stats(d: dict, bioguide: str) -> dict:
    m = d["members"]
    row = m[m["bioguide_id"] == bioguide].iloc[0]
    same = m[(m["chamber"] == row["chamber"]) & (m["caucus"] == row["caucus"])]
    peers = same[same["unity_votes_cast"] >= MIN_VOTES]
    below = (peers["party_unity_pct"] < row["party_unity_pct"]).mean() * 100
    return {
        "row": row,
        "name": spoken_name(row), "party": row["caucus"], "chamber": row["chamber"],
        "state": STATES.get(row["state_abbrev"], row["state_abbrev"]), "abbrev": row["state_abbrev"],
        "pct": float(row["party_unity_pct"]), "with": int(row["votes_with_party"]), "cast": int(row["unity_votes_cast"]),
        # same average as the Overview page and the Senate card
        "avg": float(same["party_unity_pct"].mean()), "peers": len(peers), "below": below,
        "missed_pct": float(row["missed"] / row["eligible"] * 100) if row.get("eligible", 0) else None,
        "changed": int(row["changed_apart"]), "latest": d["latest"], "through": d["through"], "current": d["current"],
        "apart": apart_votes(d, row),
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
    """Member's rate as a bar on an 80 to 100% scale, with a tick and label for the party average. The scale starts
    lower (70, 60, ...) when the member's rate is below 80%, so the bar is never empty."""
    lo = min(80, 10 * int((min(s["pct"], s["avg"]) - 2) // 10))

    def x(v):
        return max(0.0, min(1.0, (v - lo) / (100 - lo))) * width

    col = mc.PARTY.get(s["party"], mc.C["ind"])
    ax = x(s["avg"])
    anchor, tx = ("end", width) if ax > width * 0.7 else ("start", 0) if ax < width * 0.3 else ("middle", ax)
    label = f"{s['chamber']} {ADJ[s['party']]} average {s['avg']:.1f}%  ·  scale {lo} to 100%"
    h = fs * 2.6
    return (f'<svg width="{width}" height="{h:.0f}" viewBox="0 0 {width} {h:.0f}">'
            f'<rect x="0" y="{fs * 0.4:.0f}" width="{width}" height="{fs * 0.5:.0f}" rx="{fs * 0.25:.0f}" fill="{mc.C["border"]}"/>'
            f'<rect x="0" y="{fs * 0.4:.0f}" width="{x(s["pct"]):.1f}" height="{fs * 0.5:.0f}" rx="{fs * 0.25:.0f}" fill="{col}"/>'
            f'<line x1="{ax:.1f}" x2="{ax:.1f}" y1="0" y2="{fs * 1.3:.0f}" stroke="{mc.C["text"]}" stroke-width="2"/>'
            f'<text x="{tx:.1f}" y="{fs * 2.3:.0f}" text-anchor="{anchor}" font-family="Public Sans" '
            f'font-size="{fs * 0.8:.0f}" fill="{mc.C["muted"]}">{escape(label)}</text></svg>')


def apart_lines(d: dict, s: dict, n: int) -> list[dict]:
    out = []
    plural = f"{s['party']}s"
    for _, r in pick(s["apart"], n).iterrows():
        out.append({"what": describe(d, r), "full": describe(d, r, 140), "purpose": purpose(r),
                    "date": mc.fmt_date(r["date"]), "vote": r["vote"],
                    "party_vote": r["party_vote"], "plural": plural, "remarks": r["remarks_url"]})
    return out


def apart_html(d: dict, s: dict, n: int, fs: int) -> str:
    total = len(s["apart"])
    group = f"{s['chamber']} {s['party']}s"
    if total == 0:
        return f'<div class="body" style="font-size:{fs}px">Voted with most {group} on every party-line vote {when(s)}.</div>'
    head = (f'<div class="accent" style="font-size:{fs}px;font-weight:600">Voted apart from most {group} on {total} of '
            f'{s["cast"]} party-line votes, including:</div>')
    items = []
    for a in apart_lines(d, s, n):
        meta = f"{a['date']} · Voted {a['vote']}; most {a['plural']} voted {a['party_vote']}"
        if isinstance(a["remarks"], str):
            meta += " · Spoke about it in the Congressional Record"
        items.append(f'<li><div class="body">{escape(a["what"])}</div>'
                     f'<div class="muted" style="font-size:{fs * 0.82:.0f}px;margin-top:2px">{escape(meta)}</div></li>')
    return head + f'<ul class="facts" style="font-size:{fs}px;margin-top:6px">{"".join(items)}</ul>'


def when(s: dict) -> str:
    return "this Congress" if s["current"] else f"in the {ordinal(s['latest'])} Congress"


def in_congress(s: dict) -> str:
    """'In the current Congress (votes through Sep 30, 2026)' or, once it has ended,
    'In the 119th Congress (2025 to 2026, final record)'."""
    if s["current"]:
        return f"In the current Congress (votes through {s['through']})"
    return f"In the {ordinal(s['latest'])} Congress ({2 * s['latest'] + 1787} to {2 * s['latest'] + 1788}, final record)"


def missed_line(s: dict) -> str:
    if s["missed_pct"] is None:
        return ""
    return (f"Missed {s['missed_pct']:.1f}% of roll calls {when(s)}. Roll call records don't give reasons "
            "for absences.")


def card(d: dict, s: dict, size: str) -> str:
    years = f"{2 * s['latest'] + 1787} to {2 * s['latest'] + 1788}"
    label = f"Member spotlight · {s['chamber']} · {years} Congress" + ("" if s["current"] else ", final record")
    who = f"{s['party']} · {s['state']}"
    big = f"{s['pct']:.1f}%"
    line = f"voted with their party on {s['with']} of {s['cast']} party-line votes"
    src = f"Voteview roll calls through {s['through']}; Congressional Record. Fixed random rotation."
    css = (".facts{list-style:none;margin:0;padding:0}.facts li{padding:7px 0;border-top:1px solid "
           f"{mc.C['border']}}}")
    if size == "wide":
        body = f"""
<div style="display:flex;gap:36px">
  <div style="flex:1.15">
    <div class="muted" style="font-size:17px">{escape(label)}</div>
    <h1 style="font-size:42px;line-height:1.05;margin-top:6px">{escape(s['name'])}</h1>
    <div class="body" style="font-size:19px;margin-top:4px">{escape(who)}</div>
    <div style="display:flex;align-items:baseline;gap:14px;margin-top:12px">
      <div class="accent" style="font-family:'Source Serif 4';font-weight:700;font-size:62px;line-height:1">{big}</div>
      <div class="body" style="font-size:17px;line-height:1.35;max-width:300px">{escape(line)}</div></div>
    <div style="margin-top:8px">{compare_bar(s, 560, 15)}</div>
  </div>
  <div style="flex:0.85;display:flex;align-items:center;justify-content:center">{seat_svg(d, s, 380)}</div>
</div>
<div style="margin-top:6px">{apart_html(d, s, 2, 16)}</div>
<div class="muted" style="font-size:14px;margin:6px 0 10px">{escape(missed_line(s))}</div>{mc.foot(src, size)}"""
    else:
        body = f"""
<div class="muted" style="font-size:22px;margin-top:8px">{escape(label)}</div>
<h1 style="font-size:58px;line-height:1.05;margin-top:10px">{escape(s['name'])}</h1>
<div class="body" style="font-size:26px;margin-top:6px">{escape(who)}</div>
<div class="accent" style="font-family:'Source Serif 4';font-weight:700;font-size:104px;line-height:1;margin-top:24px">{big}</div>
<div class="body" style="font-size:26px;line-height:1.35;margin-top:6px">{escape(line)}</div>
<div style="margin-top:16px">{compare_bar(s, 920, 22)}</div>
<div style="margin-top:18px">{apart_html(d, s, 3, 22)}</div>
<div class="muted" style="font-size:19px;margin-top:12px;line-height:1.4">{escape(missed_line(s))}</div>
<div style="margin-top:auto;padding-top:16px;display:flex;flex-direction:column;align-items:center">{seat_svg(d, s, 420)}
<div class="muted" style="font-size:18px;margin-top:6px">Their seat, among {s['chamber']} members ordered by voting record</div></div>
{mc.foot(src, size)}"""
    return mc.page(body, size, css)


def caption(d: dict, s: dict) -> str:
    abbr = s["party"][0]
    group = f"{s['chamber']} {s['party']}s"
    lines = [
        f"Member spotlight: {s['name']} ({abbr}-{s['abbrev']}), {s['chamber']}.",
        f"{in_congress(s)}, {s['name']} voted with the {ADJ[s['party']]} majority on {s['with']} of {s['cast']} "
        f"party-line votes ({s['pct']:.1f}%). The {s['chamber']} {ADJ[s['party']]} average is {s['avg']:.1f}%.",
        "",
    ]
    if len(s["apart"]):
        lines.append(f"Votes apart from most {group} ({len(s['apart'])} in all) included:")
        for a in apart_lines(d, s, 3):
            lines.append(f"- {a['full']} ({a['date']}): voted {a['vote']}; most {a['plural']} voted {a['party_vote']}.")
            if a["purpose"]:
                lines.append(f"  From the vote record: {a['purpose']}")
            if isinstance(a["remarks"], str):
                lines.append(f"  In their own words: {a['remarks']}")
    else:
        lines.append(f"Voted with most {group} on every party-line vote {when(s)}.")
    lines += ["", missed_line(s), "",
              f"Full voting record: {member_url(s['row']['bioguide_id'])}",
              f"Look up how your own members vote: {mc.SITE}",
              "Members are featured in a fixed random rotation, not chosen by hand. Data: Voteview, Congressional Record."]
    return "\n".join(l for l in lines if l is not None)


def alt_text(d: dict, s: dict) -> str:
    """What the card image shows, for screen readers (sent as the post's alt text)."""
    parts = [f"Member spotlight card for {s['name']}, {s['party']}, {s['state']}, {s['chamber']}. Large number: "
             f"{s['pct']:.1f}%, voted with their party on {s['with']} of {s['cast']} party-line votes. A bar compares "
             f"it with the {s['chamber']} {ADJ[s['party']]} average of {s['avg']:.1f}%."]
    lines = apart_lines(d, s, 2)
    if lines:
        parts.append(f"Votes apart from most of their party, {len(s['apart'])} in all, including: " + "; ".join(
            f"{a['what']}, {a['date']}, voted {a['vote']} while most {a['plural']} voted {a['party_vote']}" for a in lines) + ".")
    if missed_line(s):
        parts.append(missed_line(s))
    parts.append(f"A half-circle chart of the {s['chamber']} with their seat circled.")
    return " ".join(parts)


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
                # Facebook gets the wide PNG, Instagram the tall JPEG; no tall PNG, to keep the repository small.
                path = OUT / (f"{b}-wide.png" if size == "wide" else f"{b}-tall.jpg")
                if size == "wide":
                    pg.screenshot(path=str(path))
                else:
                    pg.screenshot(path=str(path), type="jpeg", quality=90)
                paths.append(path)
                pg.close()
            (OUT / f"{b}.txt").write_text(caption(d, s) + "\n")
            (OUT / f"{b}.alt.txt").write_text(alt_text(d, s)[:1000] + "\n")
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
