"""Index of who spoke about which bill in the Congressional Record (GovInfo), for the "In their own words" links.
One row per member per bill per Record section: data/floor_remarks_index.csv.gz.

Each day's Congressional Record on GovInfo has MODS metadata listing every section (granule) with its title, a
link to the text, every member who spoke (with Bioguide ID) and the bills it references. That metadata is only the
starting point: a member counts as "speaking" in a section even when all they said was "had I been present, I would
have voted yea on Roll Call No. 343". So each candidate is checked against the section's text:

  - the member's own remarks in the section, minus short procedural lines ("I yield back", "I ask unanimous
    consent") and statements explaining a missed vote, must come to at least MIN_WORDS words, and
  - unless the section is about that bill (it's in the section's headline, with at most one other), the member's
    remarks must name the bill, by number (H.R. 2913) or by its short title (Ukraine Support Act). That covers a
    rule for debating several bills at once, and a bill that only comes up in passing.
  - and if they name a different bill from the same section but never this one, they were talking about the other.
  - finally, their remarks have to share some of the bill's vocabulary: a TF-IDF similarity of at least TOPIC_MIN
    with the bill's titles, subjects, summary and amendments (scripts/bill_topics.py, from GovInfo's BILLSTATUS
    data). That catches tributes, schedule announcements and speeches on another subject given during a bill's
    debate time.

It records only that they spoke about the bill and where; it does not code what they said. Stances are coded by
hand separately, in data/floor_statements.csv.

No API key: www.govinfo.gov serves the sitemaps, MODS and text files directly. Downloads are cached in --cache.

  python scripts/floor_remarks_index.py --years 2025 2026
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import functools
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from floor_remarks import granule_url  # noqa: E402
OUT = ROOT / "data" / "floor_remarks_index.csv.gz"
NS = {"m": "http://www.loc.gov/mods/v3"}
M = "{http://www.loc.gov/mods/v3}"
SKIP_TITLES = re.compile(r"^(PRAYER|PLEDGE OF ALLEGIANCE|THE JOURNAL|ADJOURNMENT|RECESS|EXECUTIVE COMMUNICATIONS|"
                         r"PUBLIC BILLS AND RESOLUTIONS|ADDITIONAL SPONSORS|DAILY DIGEST|AMENDMENTS SUBMITTED|"
                         r"TEXT OF AMENDMENTS|STATEMENTS ON INTRODUCED BILLS|PERSONAL EXPLANATION|"
                         r"SUBMITTED RESOLUTIONS|REPORTS? OF COMMITTEES?|CONSTITUTIONAL AUTHORITY|NOTICES? OF HEARINGS?|"
                         r"AUTHORITY FOR COMMITTEES TO MEET|PRIVILEGES? OF THE FLOOR|ORDERS? FOR |"
                         r"UNANIMOUS[- ]CONSENT (?:AGREEMENT|REQUEST)|MEASURES? (?:PLACED|READ)|ENROLLED BILLS?|"
                         r"MESSAGES? FROM THE (?:HOUSE|SENATE|PRESIDENT)|EXECUTIVE AND OTHER COMMUNICATIONS|"
                         r"INTRODUCTION OF BILLS|LEAVE OF ABSENCE|BILLS? PRESENTED|SUBMISSION OF CONCURRENT|LEGISLATIVE PROGRAM|"
                         r"SCHEDULE|ORDER OF BUSINESS|PROGRAM FOR)", re.I)
COLUMNS = ["bioguide_id", "congress", "bill_number", "date", "chamber", "granule"]
MIN_WORDS = 60

# A speaker's turn starts a paragraph: "  Mr. FITZPATRICK. Mr. Speaker, ..." or "  The PRESIDING OFFICER. ..."
TURN = re.compile(r"^ {1,2}((?:Mr|Mrs|Ms|Miss|Madam)\. [A-Z][A-Za-z'\-]*(?: [A-Z][A-Za-z'\-]*)*(?: of [A-Z][A-Za-z .]+?)?"
                  r"|The (?:[A-Z][A-Za-z]* )*?(?:SPEAKER|PRESIDENT|OFFICER|CHAIR|CHAIRMAN|CLERK)"
                  r"(?: pro tempore)?(?: \([^)]*\))?)\. ", re.M)
MISSED_VOTE = re.compile(r"had I been present|would have voted|unable to (?:be present|vote|cast)|I was absent|"
                         r"missed (?:the |a |several |roll ?call)|not present for|was not recorded|"
                         r"inadvertently voted|intended to vote", re.I)


def fetch(url: str, dest: Path, tries: int = 3) -> Path | None:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                dest.write_bytes(r.read())
            return dest
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None


def days(years: list[int], cache: Path) -> list[str]:
    out = set()
    for y in years:
        sm = fetch(f"https://www.govinfo.gov/sitemap/CREC_{y}_sitemap.xml", cache / f"CREC_{y}_sitemap.xml")
        if sm:
            out |= set(re.findall(r"CREC-\d{4}-\d{2}-\d{2}", sm.read_text(errors="ignore")))
    return sorted(out)


def parse(path: Path) -> list[dict]:
    """Candidate rows from one day's MODS: every speaker in a section times every bill it references."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return []
    date = re.search(r"CREC-(\d{4}-\d{2}-\d{2})", path.name).group(1)
    rows = []
    for g in root.findall("m:relatedItem[@type='constituent']", NS):
        title = (g.findtext("m:titleInfo/m:title", default="", namespaces=NS) or "").strip()
        if not title or SKIP_TITLES.match(title):
            continue
        access = g.findtext(".//m:accessId", default="", namespaces=NS)
        if not access:
            continue
        cls = g.findtext(".//m:granuleClass", default="", namespaces=NS)
        speakers = {}
        for c in g.iter(f"{M}congMember"):
            if c.get("role") == "SPEAKING" and c.get("bioGuideId"):
                parsed = next((n.text for n in c.findall("m:name", NS) if n.get("type") == "parsed"), "") or ""
                speakers[c.get("bioGuideId")] = (c.get("chamber"), parsed.strip())
        bills, headline = set(), set()
        for b in g.iter(f"{M}bill"):
            if b.get("congress") and b.get("number"):
                key = (b.get("congress"), f"{b.get('type', '').upper()}{b.get('number')}")
                bills.add(key)
                if b.get("context") == "HEADERLINE":  # the section is about this bill
                    headline.add(key)
        for key in bills - headline:  # the metadata doesn't always mark it; the section title often names the bill
            if names_bill(title, key[1], short_titles().get((int(key[0]), key[1]))):
                headline.add(key)
        for bio, (chamber, parsed) in speakers.items():
            for congress, bill in bills:
                rows.append({"bioguide_id": bio, "congress": int(congress), "bill_number": bill, "date": date,
                             "chamber": {"H": "House", "S": "Senate"}.get(chamber or "", chamber or ""),
                             "granule": access.removeprefix(f"CREC-{date}-"), "parsed": parsed,
                             "extension": cls == "EXTENSIONS", "n_bills": len(bills),
                             "headline": (congress, bill) in headline, "n_headline": len(headline),
                             "others": " ".join(sorted(b for c, b in bills if (c, b) != (congress, bill)))})
    return rows


def text_of(path: Path) -> str:
    raw = path.read_text(errors="ignore")
    m = re.search(r"<pre>(.*)</pre>", raw, re.S)
    return html.unescape(re.sub(r"<[^>]+>", "", m.group(1) if m else raw))


def norm(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().upper()


def turns(text: str) -> list[tuple[str, str]]:
    """(speaker label, what they said) for each turn in a section, in order."""
    marks = list(TURN.finditer(text))
    return [(m.group(1), text[m.end():(marks[i + 1].start() if i + 1 < len(marks) else len(text))])
            for i, m in enumerate(marks)]


# Sentences that run the floor rather than say anything about the bill, and the clerk's narration that follows them.
PROCEDURE = re.compile(r"\byield|reserve the balance|unanimous consent|absence of a quorum|move that the committee|"
                       r"do now rise|motion was agreed to|motion to reconsider|committee rose|recorded vote|yeas and nays|"
                       r"immediate consideration|\bcall up\b|the clerk (?:will|read|designated)|without objection|"
                       r"the question is|\bI move\b|point of order|pursuant to (?:house )?resolution|reported that|"
                       r"assumed the chair|having had under consideration|I thank the (?:gentle|chair|ranking|senator|"
                       r"majority|minority)|necessarily absent|if present and voting|result (?:of the vote )?was "
                       r"announced|vote was taken|minute vote|minutes remaining|\byeas \d|not voting|^so the |"
                       r"^stated (?:for|against)|journal of proceedings|morning hour|calendar no\.|two leaders|"
                       r"deemed expired|invoke cloture|the senate (?:resume|vote|proceed|stand)|\badjourn|"
                       r"printed in the record|ordered to be printed", re.I)


ROLL_NUMBER = re.compile(r"\broll ?call(?: vote)?(?: No\.| number)|\bRoll No\.|\brollcall votes? \d", re.I)


def clean(said: str) -> str:
    """The member's own sentences: quoted documents (indented), page markers and procedural sentences removed."""
    lines = [ln for ln in said.split("\n") if not re.match(r"\s{4,}\S", ln) and "[[Page" not in ln]
    sentences = re.split(r"(?<=[.?!])\s+", re.sub(r"\s+", " ", " ".join(lines)))
    return " ".join(x for x in sentences if not PROCEDURE.search(x))


def substantive(said: str) -> str:
    """A turn's own words, unless it is a short procedural line or explains a missed vote."""
    said = clean(said)
    words = len(said.split())
    if words < 40 or (MISSED_VOTE.search(said) and words < 150):
        return ""
    if MISSED_VOTE.search(said) and len(ROLL_NUMBER.findall(said)) >= 3:  # a list of how they'd have voted
        return ""
    return said


def member_turns(text: str, parsed: str, extension: bool) -> list[str]:
    """Everything this member said in the section, one string per turn ([] if they have no turn in the text)."""
    if extension:  # an Extension of Remarks is one member's written statement
        return [re.split(r"\bin the (?:house of representatives|senate)\b", text, maxsplit=1, flags=re.I)[-1]]
    ts = turns(text)
    want = norm(parsed)
    mine = [s for label, s in ts if norm(label) == want]
    if not mine and want:  # "Mr. GARCIA" in the metadata, "Mr. GARCIA of Texas" in the text, or the other way
        surname = want.split(" OF ")[0]
        labels = {norm(label) for label, _ in ts if norm(label).split(" OF ")[0] == surname}
        if len(labels) == 1:
            mine = [s for label, s in ts if norm(label) in labels]
    return mine


def own_remarks(text: str, parsed: str, extension: bool) -> str:
    """What this member said in the section, procedural lines and missed-vote statements left out."""
    return "\n".join(substantive(s) for s in member_turns(text, parsed, extension)).strip()


PREFIX = {"HR": r"H\.\s?R\.|House Bill", "S": r"S\.|Senate Bill", "HRES": r"H\.\s?Res\.|House Resolution",
          "SRES": r"S\.\s?Res\.|Senate Resolution", "HJRES": r"H\.\s?J\.\s?Res\.|House Joint Resolution",
          "SJRES": r"S\.\s?J\.\s?Res\.|Senate Joint Resolution",
          "HCONRES": r"H\.\s?Con\.\s?Res\.|House Concurrent Resolution",
          "SCONRES": r"S\.\s?Con\.\s?Res\.|Senate Concurrent Resolution"}


def names_bill(said: str, bill: str, title: str | None) -> bool:
    m = re.fullmatch(r"([A-Z]+?)(\d+)", bill)
    if m and m.group(1) in PREFIX and re.search(rf"(?:{PREFIX[m.group(1)]})\s?{m.group(2)}\b", said, re.I):
        return True
    if title and len(title) <= 80:  # a short title such as "Ukraine Support Act", not "A bill to ..."
        core = re.sub(r"\s+of \d{4}$|\s+\d{4}$", "", title.strip().rstrip("."))
        return len(core) >= 8 and core.lower() in re.sub(r"\s+", " ", said).lower()
    return False


@functools.lru_cache(maxsize=1)
def short_titles() -> dict:
    """(congress, bill) -> short title, from House vote descriptions in data/all_votes.csv."""
    path = ROOT / "data" / "all_votes.csv"
    if not path.exists():
        return {}
    v = pd.read_csv(path, usecols=["congress", "chamber", "bill_number", "vote_question", "vote_desc"])
    v = v[(v["chamber"] == "House") & v["bill_number"].notna() & v["vote_desc"].notna()
          & v["vote_question"].str.contains(r"passage|suspend the rules", case=False, na=False)]
    v = v.assign(n=v["vote_desc"].str.len()).sort_values("n")
    return {(c, b): t for c, b, t in v.drop_duplicates(["congress", "bill_number"])[["congress", "bill_number", "vote_desc"]].values}


def needs_name(r) -> bool:
    """Whether the member must name the bill for their remarks to count as being about it. Not when the section is
    about that bill alone or with one other; yes when it is a rule for debating several bills, or the bill only comes
    up in a section about something else."""
    if r.headline:
        return r.n_headline > 2
    return r.n_headline > 0 or r.n_bills > 1


def verify(rows: pd.DataFrame, cache: Path, workers: int = 20) -> pd.DataFrame:
    """Keep the rows where the member's own remarks in that section are substantive and about that bill."""
    if rows.empty:
        return rows
    cache.mkdir(parents=True, exist_ok=True)
    sections = rows[["date", "granule"]].drop_duplicates()
    with cf.ThreadPoolExecutor(workers) as ex:
        paths = list(ex.map(lambda dg: fetch(granule_url(*dg), cache / f"CREC-{dg[0]}-{dg[1]}.htm"),
                            sections.itertuples(index=False, name=None)))
    texts = {(d, g): text_of(p) for (d, g), p in zip(sections.itertuples(index=False, name=None), paths) if p}
    if len(texts) < len(sections):
        print(f"Could not download {len(sections) - len(texts)} of {len(sections)} sections; their rows are left out. "
              "Run again to retry them.")
    titles = short_titles()
    reasons, said = [], {}
    for r in rows.itertuples(index=False):
        text = texts.get((r.date, r.granule))
        if text is None:
            reasons.append("no_text")
            continue
        k = (r.date, r.granule, r.bioguide_id)
        if k not in said:
            mine = member_turns(text, r.parsed, r.extension)
            said[k] = (mine, "\n".join(substantive(x) for x in mine).strip())
        mine, words = said[k]
        if not mine:
            reasons.append("no_turn")  # listed as speaking, but no turn of theirs in the text (lists, notices)
        elif len(words.split()) < MIN_WORDS:
            reasons.append("missed_vote" if any(MISSED_VOTE.search(x) for x in mine) else "procedural_or_short")
        elif not names_bill(words, r.bill_number, titles.get((r.congress, r.bill_number))) and (
                needs_name(r) or any(names_bill(words, o, titles.get((r.congress, o))) for o in str(r.others).split())):
            # Unnamed, where the section isn't plainly about this bill; or they named another bill in the section
            # and never this one (a senator using debate time on one bill to talk about a different one).
            reasons.append("not_about_bill")
        else:
            reasons.append("kept")
    kept = [i for i, x in enumerate(reasons) if x == "kept"]
    for i, (sim, other) in zip(kept, topic_scores(rows.iloc[kept], {k: v[1] for k, v in said.items()})):
        if off_topic(sim, other):
            reasons[i] = "off_topic"
    REASONS.update(pd.Series(reasons).value_counts().to_dict())
    return rows[[x == "kept" for x in reasons]]


REASONS: dict = {}  # why each candidate was kept or left out, for --report
TOPIC_SCORES: list = []  # for --topic-scores: how close each kept link's remarks are to the bill's own description


# Remarks less similar than this to the bill (TF-IDF cosine, best of the whole description and each part of it) are
# about something else. Set from a hand-labeled sample of 100 links (writeups/checking-the-congressional-record.md).
TOPIC_MIN = 0.07
PART_MIN_TERMS = 8  # a part of the bill counts on its own only if it has this many distinct weighted words
STOP = {"speaker", "president", "chair", "chairman", "madam", "gentleman", "gentlewoman", "gentleman's", "colleague",
        "colleagues", "time", "yield", "minutes", "balance", "today", "rise", "support", "oppose", "opposition",
        "urge", "vote", "votes", "voted", "bill", "bills", "legislation", "act", "resolution", "amendment", "amendments",
        "house", "senate", "congress", "member", "members", "floor", "committee", "chairman", "ranking", "thank",
        "just", "want", "know", "think", "going", "said", "say", "people", "american", "americans", "country",
        "united", "states", "state", "federal", "government", "year", "years", "make", "need", "important", "way"}


def topic_scores(rows: pd.DataFrame, said: dict) -> list[tuple[float | None, float | None]]:
    """(similarity to this bill, best similarity to another bill in the same section) for each row, in order, by
    TF-IDF cosine between the member's remarks and each bill's profile (scripts/bill_topics.py). None where there's
    no profile."""
    out: list = [(None, None)] * len(rows)
    if rows.empty:
        return out
    import bill_topics
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
    recs = list(rows.itertuples(index=False))
    for congress in dict.fromkeys(r.congress for r in recs):
        prof = bill_topics.profiles(int(congress))
        if not prof:
            continue
        keys = list(prof)
        big = len(keys) > 100  # a real Congress; tiny sets are tests
        vec = TfidfVectorizer(stop_words=list(ENGLISH_STOP_WORDS | STOP), sublinear_tf=True, min_df=2 if big else 1,
                              max_df=0.3 if big else 1.0, token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]{2,}\b")
        bills = vec.fit_transform([prof[k] for k in keys])
        where = {k: i for i, k in enumerate(keys)}
        split = bill_topics.parts(int(congress))
        piece: dict = {}  # bill -> TF-IDF rows of its parts, built on first use

        def pieces(b):
            if b not in piece:
                p = vec.transform(split[b]) if split.get(b) else None
                if p is not None:  # a short part ("In the nature of a substitute.") would match on a single word
                    p = p[(p.getnnz(axis=1) >= PART_MIN_TERMS).nonzero()[0]]
                piece[b] = p if p is not None and p.shape[0] else None
            return piece[b]

        idx = [i for i, r in enumerate(recs) if r.congress == congress]
        speech_keys = list(dict.fromkeys((recs[i].date, recs[i].granule, recs[i].bioguide_id) for i in idx))
        speech = vec.transform([said.get(k, "") for k in speech_keys])
        sk = {k: j for j, k in enumerate(speech_keys)}
        for i in idx:
            r = recs[i]
            v = speech[sk[(r.date, r.granule, r.bioguide_id)]]

            def sim(b, v=v):
                """Best match between the remarks and the bill: the whole profile or any one part of it."""
                if b not in where:
                    return None
                whole = float(v.multiply(bills[where[b]]).sum())
                p = pieces(b)
                return max(whole, float((p @ v.T).max())) if p is not None else whole
            others = [x for x in (sim(o) for o in str(r.others).split()) if x is not None]
            out[i] = (sim(r.bill_number), max(others) if others else None)
            TOPIC_SCORES.append({"congress": r.congress, "bill_number": r.bill_number, "bioguide_id": r.bioguide_id,
                                 "date": r.date, "granule": r.granule, "sim": out[i][0], "other": out[i][1]})
    return out


def off_topic(sim: float | None, other: float | None = None) -> bool:
    """Remarks that barely share a word with what the bill is about. No verdict when the bill has no description."""
    return sim is not None and sim < TOPIC_MIN


def build(years: list[int], cache: Path, workers: int = 8, recent: int | None = None) -> tuple[pd.DataFrame, list[str]]:
    cache.mkdir(parents=True, exist_ok=True)
    ids = days(years, cache)
    if recent:
        ids = ids[-recent:]
    with cf.ThreadPoolExecutor(workers) as ex:
        paths = list(ex.map(lambda i: fetch(f"https://www.govinfo.gov/metadata/pkg/{i}/mods.xml", cache / f"{i}.xml"),
                            ids))
    rows = [r for p in paths if p for r in parse(p)]
    df = pd.DataFrame(rows, columns=COLUMNS + ["parsed", "extension", "n_bills", "headline", "n_headline", "others"])
    # Keep remarks about bills of the same Congress, one row per member, bill and section.
    df = df[df["congress"].isin({(y - 1789) // 2 + 1 for y in years})]
    df = df.drop_duplicates(["bioguide_id", "bill_number", "date", "granule"])
    df = verify(df, cache / "html")
    read = [i.removeprefix("CREC-") for i, p in zip(ids, paths) if p]
    return df[COLUMNS].sort_values(["congress", "bill_number", "date", "bioguide_id"]), read


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--years", nargs="+", type=int, default=[2025, 2026])
    ap.add_argument("--cache", type=Path, default=Path("/tmp/crec/mods"))
    ap.add_argument("--recent", type=int, help="only re-read the last N days of the Record (for the twice-weekly refresh)")
    ap.add_argument("--report", type=Path, help="append why candidates were kept or left out, as a JSON line")
    ap.add_argument("--topic-scores", type=Path, help="append each kept link's topic similarity scores (CSV)")
    a = ap.parse_args()
    df, read = build(a.years, a.cache, recent=a.recent)
    old = pd.read_csv(OUT)[COLUMNS] if OUT.exists() else pd.DataFrame(columns=COLUMNS)
    if a.recent:
        keep = old[~old["date"].isin(read)]
    else:
        keep = old[~old["congress"].isin(df["congress"].unique())]
    out = pd.concat([keep, df]).drop_duplicates(["bioguide_id", "bill_number", "date", "granule"])
    out.sort_values(["congress", "bill_number", "date", "bioguide_id"]).to_csv(
        OUT, index=False, compression={"method": "gzip", "mtime": 0})
    if a.topic_scores and TOPIC_SCORES:
        pd.DataFrame(TOPIC_SCORES).to_csv(a.topic_scores, mode="a", index=False, header=not a.topic_scores.exists())
    if a.report:
        with a.report.open("a") as fh:
            fh.write(json.dumps({"years": a.years, "candidates": int(sum(REASONS.values())),
                                 **{k: int(v) for k, v in REASONS.items()}}) + "\n")
    print(f"{len(df):,} member-bill remarks for Congress {sorted(df['congress'].unique())} -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
