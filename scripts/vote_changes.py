"""Same bill, different vote: members who voted for a bill at one stage and against it at another (or the reverse).

A bill can get more than one up-or-down vote in the same chamber: passage, then a vote on the final version after
the other chamber changed it (a conference report or agreeing to the other chamber's amendment), then sometimes a
veto override. On each of these, Yea means supporting the bill. This script finds every member who voted Yea on
one of those votes and Nay on another for the same bill in the same chamber and Congress.

Procedural votes (cloture, motions to recommit, rules, amendments, tabling) are left out on purpose: voting against
a motion to recommit and for passage is the same position, not a change.

The bill's text can change a lot between votes, and a bill number is sometimes used as the vehicle for an entirely
different bill. A changed vote is a fact about the record, not a judgment about why.

Writes:
  data/vote_changes.csv       one row per member who changed, with their first and final votes
  data/vote_change_bills.csv  one row per bill with two or more support votes, and how many members changed

Run on its own (python scripts/vote_changes.py) or as part of scripts/refresh_data.py. Needs data/raw/ from a
refresh.
"""

from pathlib import Path
import re
import time
import urllib.request
import xml.etree.ElementTree as ET

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
MEMBERS_FILE = DATA_DIR / "members_processed.csv"
CHANGES_FILE = DATA_DIR / "vote_changes.csv"
BILLS_FILE = DATA_DIR / "vote_change_bills.csv"
TITLES_FILE = DATA_DIR / "bill_titles.csv"  # cache of each bill's current title from GovInfo
BILLSTATUS_URL = "https://www.govinfo.gov/bulkdata/BILLSTATUS/{congress}/{kind}/BILLSTATUS-{congress}{kind}{number}.xml"
STOP_WORDS = set("a an and act acts the of for to in on by with from or as at be is it its this that other purposes "
                 "fiscal year ending september 30 making appropriations bill joint resolution providing provide "
                 "united states related agencies programs department departments".split())
CHAMBERS = {"House": "H", "Senate": "S"}

# Questions where Yea means supporting the bill or resolution itself.
SUPPORT_RE = re.compile(
    r"^on passage"
    r"|^passage, objections of the president"
    r"|suspend the rules and pass(?!\s+certain)"
    r"|suspend the rules and agree"
    r"|^on (?:the )?joint resolution$"
    r"|^on (?:agreeing to )?the (?:concurrent )?resolution(?:, as amended)?$"
    r"|conference report"
    r"|concur in the (?:senate|house) amendments?"
    r"|overriding the veto",
    re.IGNORECASE,
)
# Never counted, even if a pattern above matches part of the wording.
EXCLUDE_RE = re.compile(r"table|instruct|disagree|recommit|commit|reconsider|cloture|closing", re.IGNORECASE)

YEA, NAY = 1, 6  # Voteview cast codes for floor votes (paired and announced positions are not counted)


def stage(question: str) -> str:
    """Short, plain name for the kind of vote."""
    q = question.lower()
    if "veto" in q or "objections of the president" in q:
        return "Veto override"
    if "conference report" in q:
        return "Final version (conference report)"
    if "concur" in q:
        return "Final version (other chamber's changes)"
    return "Passage"


def support_votes(rollcalls: pd.DataFrame) -> pd.DataFrame:
    q = rollcalls["vote_question"].fillna("")
    keep = q.str.contains(SUPPORT_RE) & ~q.str.contains(EXCLUDE_RE) & rollcalls["bill_number"].notna()
    out = rollcalls[keep].copy()
    out["stage"] = out["vote_question"].map(stage)
    # Only bills with two or more support votes in this chamber and Congress can show a change
    n = out.groupby("bill_number")["rollnumber"].transform("size")
    return out[n >= 2]


def changes_for(congress: int, chamber: str, members: pd.DataFrame):
    prefix = CHAMBERS[chamber]
    rc_path, v_path = RAW_DIR / f"{prefix}{congress}_rollcalls.csv", RAW_DIR / f"{prefix}{congress}_votes.csv"
    if not rc_path.exists() or not v_path.exists():
        return None, None
    rollcalls = support_votes(pd.read_csv(rc_path))
    if rollcalls.empty:
        return None, None
    votes = pd.read_csv(v_path, usecols=["rollnumber", "icpsr", "cast_code"])
    votes = votes[votes["rollnumber"].isin(rollcalls["rollnumber"]) & votes["cast_code"].isin([YEA, NAY])]
    cols = ["rollnumber", "date", "bill_number", "vote_question", "vote_desc", "vote_result", "yea_count", "nay_count", "stage"]
    v = votes.merge(rollcalls[cols], on="rollnumber").sort_values(["icpsr", "bill_number", "rollnumber"])
    v["vote"] = v["cast_code"].map({YEA: "Yea", NAY: "Nay"})
    who = members[(members["congress"] == congress) & (members["chamber"] == chamber)][
        ["icpsr", "bioguide_id", "name", "party", "caucus", "state_abbrev"]].drop_duplicates("icpsr")
    v = v.merge(who[["icpsr", "caucus"]], on="icpsr", how="left")
    # How most of each member's party (by caucus) voted on each roll call; ties count as no majority
    tally = v.groupby(["rollnumber", "caucus"])["vote"].agg(yea=lambda s: (s == "Yea").sum(), nay=lambda s: (s == "Nay").sum())
    tally["party_majority"] = "Tie"
    tally.loc[tally["yea"] > tally["nay"], "party_majority"] = "Yea"
    tally.loc[tally["nay"] > tally["yea"], "party_majority"] = "Nay"
    v = v.merge(tally[["party_majority"]].reset_index(), on=["rollnumber", "caucus"], how="left")

    # Members who voted on at least two of the bill's support votes
    g = v.groupby(["bill_number", "icpsr"])
    both = g["vote"].agg(["size", "nunique", "first", "last"]).reset_index()
    both = both[both["size"] >= 2]
    changed = both[both["nunique"] > 1]

    # Bill summary: every bill with two or more support votes that at least some members voted on twice
    first_rc = rollcalls.sort_values("rollnumber").groupby("bill_number").head(1).set_index("bill_number")
    last_rc = rollcalls.sort_values("rollnumber").groupby("bill_number").tail(1).set_index("bill_number")
    first = g.head(1).set_index(["bill_number", "icpsr"])
    last = g.tail(1).set_index(["bill_number", "icpsr"])
    # A change "apart from the party": most of the member's party voted the same way on both of the member's
    # votes, so the member changed while the party did not.
    ch = changed.set_index(["bill_number", "icpsr"])[[]]
    ch["party_first"] = first["party_majority"].reindex(ch.index)
    ch["party_final"] = last["party_majority"].reindex(ch.index)
    ch["apart"] = (ch["party_first"] == ch["party_final"]) & ch["party_first"].isin(["Yea", "Nay"])
    bills = both.groupby("bill_number").agg(voted_twice=("icpsr", "size")).join(
        ch.groupby("bill_number").agg(changed=("apart", "size"), changed_apart=("apart", "sum"))).fillna(0)
    bills["changed"] = bills["changed"].astype(int)
    bills["changed_apart"] = bills["changed_apart"].astype(int)
    bills["support_votes"] = rollcalls.groupby("bill_number").size()
    bills["first_roll"], bills["first_date"] = first_rc["rollnumber"], first_rc["date"]
    bills["first_question"], bills["first_desc"] = first_rc["vote_question"], first_rc["vote_desc"]
    bills["final_roll"], bills["final_date"] = last_rc["rollnumber"], last_rc["date"]
    bills["final_question"], bills["final_desc"] = last_rc["vote_question"], last_rc["vote_desc"]
    bills = bills.reset_index()
    bills.insert(0, "chamber", chamber)
    bills.insert(0, "congress", congress)

    if changed.empty:
        return None, bills

    # Each changed member's first and final vote, with the roll calls behind them
    rows = ch.copy()
    for tag, src in (("first", first), ("final", last)):
        for c in ["rollnumber", "date", "vote_question", "stage", "vote", "vote_desc", "vote_result"]:
            rows[f"{tag}_{c}"] = src[c].reindex(rows.index)
    rows = rows.reset_index()
    rows["direction"] = rows["first_vote"] + " to " + rows["final_vote"]
    rows.loc[rows["first_vote"] == rows["final_vote"], "direction"] = "Changed, then changed back"
    rows = rows.merge(who, on="icpsr", how="left")
    rows.insert(0, "chamber", chamber)
    rows.insert(0, "congress", congress)
    return rows, bills


def split_bill(bill_number: str):
    m = re.fullmatch(r"([A-Z]+)(\d+)", str(bill_number))
    return (m.group(1).lower(), m.group(2)) if m else (None, None)


def fetch_titles(bills: pd.DataFrame, max_fetch: int = 400) -> pd.DataFrame:
    """Current title of each bill (the title Congress.gov shows, which becomes the enacted short title), cached in
    data/bill_titles.csv. Only bills not already cached are fetched. A failed fetch leaves the title blank."""
    cache = pd.read_csv(TITLES_FILE) if TITLES_FILE.exists() else pd.DataFrame(columns=["congress", "bill_number", "title"])
    have = set(zip(cache["congress"].astype(int), cache["bill_number"]))
    need = [(int(c), b) for c, b in zip(bills["congress"], bills["bill_number"]) if (int(c), b) not in have]
    new = []
    for congress, bill in sorted(set(need))[:max_fetch]:
        kind, number = split_bill(bill)
        if not kind:
            continue
        url = BILLSTATUS_URL.format(congress=congress, kind=kind, number=number)
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                root = ET.fromstring(r.read())
            title = (root.findtext("bill/title") or "").strip()
        except Exception as e:  # GovInfo being down shouldn't stop the refresh
            print(f"  No title for {congress} {bill}: {e}")
            continue
        new.append({"congress": congress, "bill_number": bill, "title": title})
        time.sleep(0.2)
    if new:
        cache = pd.concat([cache, pd.DataFrame(new)], ignore_index=True)
        cache.sort_values(["congress", "bill_number"]).to_csv(TITLES_FILE, index=False)
        print(f"Fetched {len(new)} bill titles from GovInfo")
    return cache


def words(text) -> set:
    if not isinstance(text, str):
        return set()
    return {w for w in re.findall(r"[a-z]+", text.lower()) if w not in STOP_WORDS and len(w) > 2}


def title_changed(first_desc, title) -> bool:
    """True when the bill's current title shares almost no words with how the first vote described it: a sign the
    bill number was used for a different bill. Blank titles count as unchanged."""
    a, b = words(first_desc), words(title)
    if not a or not b:
        return False
    return len(a & b) / min(len(a), len(b)) < 0.25


def build_vote_changes(members: pd.DataFrame | None = None) -> pd.DataFrame:
    if members is None:
        members = pd.read_csv(MEMBERS_FILE)
    all_rows, all_bills = [], []
    for congress in sorted(members["congress"].unique()):
        for chamber in CHAMBERS:
            rows, bills = changes_for(int(congress), chamber, members)
            if rows is not None:
                all_rows.append(rows)
            if bills is not None:
                all_bills.append(bills)
    changes = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    bills = pd.concat(all_bills, ignore_index=True) if all_bills else pd.DataFrame()
    if not changes.empty:
        changes["icpsr"] = changes["icpsr"].astype(int)
        changes = changes.sort_values(["congress", "chamber", "final_rollnumber", "name"])
    if not bills.empty:
        titles = fetch_titles(bills)
        bills = bills.merge(titles, on=["congress", "bill_number"], how="left")
        bills["title_changed"] = [title_changed(d, t) for d, t in zip(bills["first_desc"], bills["title"])]
        bills = bills.sort_values(["congress", "chamber", "first_roll"])
        if not changes.empty:
            changes = changes.merge(bills[["congress", "chamber", "bill_number", "title", "title_changed"]],
                                    on=["congress", "chamber", "bill_number"], how="left")
    changes.to_csv(CHANGES_FILE, index=False)
    bills.to_csv(BILLS_FILE, index=False)
    n_bills = int((bills["changed"] > 0).sum()) if not bills.empty else 0
    print(f"Wrote {CHANGES_FILE.name} ({len(changes):,} changed votes on {n_bills} bills) and {BILLS_FILE.name} "
          f"({len(bills)} bills with two or more support votes)")
    return changes


if __name__ == "__main__":
    build_vote_changes()
