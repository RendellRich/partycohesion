"""Match bills named in lobbying reports to the bills PartyCohesion covers.

    python scripts/lobbying_index.py data/raw/lda/lda_*.jsonl.gz

Reads the files from scripts/lobbying_pull.py and writes:
- data/lobbying_bill_mentions.csv.gz: one row per report and bill it names (congress, bill_number, client, registrant,
  year, quarter, issue code, link to the report on lda.gov)
- data/lobbying_coverage.csv: per year, how many reports there were and how many name at least one bill

What the reports can't say, and the site must not imply: which members were lobbied (reports name only the chamber),
whether a client was for or against a bill, or how much was spent on any one bill (one amount covers the whole report).

Rules, in order:
1. Amendments replace the report they amend: one report per registrant, client, year and quarter, the latest posted.
2. Bill numbers are found with the same patterns as the Congressional Record remarks check (H.R. 2913, S. 12,
   H.Res. 5, HR2913, ...). A bare "S 12" without a period is too loose and is skipped.
3. A number belongs to the Congress in session when the report's quarter ends, unless the text says otherwise:
   "(117th Congress)" right after it; a Public Law number next to it ("H.R. 5376, P.L. 117-169" is the 117th's bill);
   or a year before that Congress began right after it, which marks an older law, so the mention is dropped
   ("H.R. 5376, Inflation Reduction Act of 2022" in a 2024 report is not a 118th bill).
4. The bill has to exist in that Congress (GovInfo BILLSTATUS) and have been introduced by the end of the quarter,
   with a week's slack, as in the remarks check.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

OUT = ROOT / "data" / "lobbying_bill_mentions.csv.gz"
COVERAGE = ROOT / "data" / "lobbying_coverage.csv"
QUARTER_END = {"first_quarter": "03-31", "second_quarter": "06-30", "third_quarter": "09-30", "fourth_quarter": "12-31"}
QUARTER = {"first_quarter": 1, "second_quarter": 2, "third_quarter": 3, "fourth_quarter": 4}
SLACK_DAYS = 7

KINDS = {"HCONRES": r"H\.?\s?Con\.?\s?Res\.?", "SCONRES": r"S\.?\s?Con\.?\s?Res\.?",
         "HJRES": r"H\.?\s?J\.?\s?Res\.?", "SJRES": r"S\.?\s?J\.?\s?Res\.?",
         "HRES": r"H\.?\s?Res\.?", "SRES": r"S\.?\s?Res\.?", "HR": r"H\.?\s?R\.?", "S": r"S\."}
BILL = re.compile(r"(?<![A-Za-z.])(" + "|".join(f"(?P<{k}>{v})" for k, v in KINDS.items()) + r")\s?(?P<num>\d{1,5})\b",
                  re.I)
NAMED_CONGRESS = re.compile(r"^\W{0,3}(?:\(|,\s*)?(\d{3})(?:th|st|nd|rd)\s+Congress", re.I)
PUBLIC_LAW = re.compile(r"(?:P\.\s?L\.|Public\s+Law)\s*(\d{3})-\d+", re.I)
LAW_BEFORE = re.compile(r"(?:P\.\s?L\.|Public\s+Law)\s*(\d{3})-\d+\W{0,4}$", re.I)
YEAR = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")


def congress_of(year: int) -> int:
    return (year - 1789) // 2 + 1


def first_year(congress: int) -> int:
    return 1789 + 2 * (congress - 1)


def mentions(text: str, congress: int) -> list[tuple[int, str]]:
    """(congress, bill) for each bill number in a report's text, after rule 3."""
    out = []
    found = list(BILL.finditer(text or ""))
    for i, m in enumerate(found):
        kind = next(k for k in KINDS if m.group(k))
        bill = f"{kind}{int(m.group('num'))}"
        tail = text[m.end(): found[i + 1].start() if i + 1 < len(found) else m.end() + 120][:120]
        named = NAMED_CONGRESS.match(tail)
        if named:
            out.append((int(named.group(1)), bill))
            continue
        law = PUBLIC_LAW.search(tail[:100]) or LAW_BEFORE.search(text[max(0, m.start() - 30): m.start()])
        if law:  # "H.R. 5376, P.L. 117-169": the bill became that law, in the Congress the law number names
            out.append((int(law.group(1)), bill))
            continue
        years = [int(y) for y in YEAR.findall(tail[:90])]
        if years and max(years) < first_year(congress):
            continue
        out.append((congress, bill))
    return list(dict.fromkeys(out))


def load(paths: list[Path]) -> pd.DataFrame:
    rows = []
    for p in paths:
        with gzip.open(p, "rt", encoding="utf-8") as f:
            rows += [json.loads(line) for line in f]
    return pd.DataFrame(rows)


def latest_reports(acts: pd.DataFrame) -> pd.DataFrame:
    """Rule 1: keep only the latest posted version of each registrant-client-quarter report."""
    if acts.empty:
        return acts
    key = ["registrant_id", "client_id", "filing_year", "filing_period"]
    latest = (acts.drop_duplicates("filing_uuid").sort_values("dt_posted")
              .drop_duplicates(key, keep="last")["filing_uuid"])
    return acts[acts["filing_uuid"].isin(set(latest))]


def build(acts: pd.DataFrame, introduced=None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    import bill_topics
    introduced = introduced or bill_topics.introduced
    acts = latest_reports(acts)
    reasons = collections.Counter()
    when: dict[int, dict] = {}
    rows = []
    for r in acts.itertuples(index=False):
        congress = congress_of(int(r.filing_year))
        end = pd.Timestamp(f"{r.filing_year}-{QUARTER_END.get(r.filing_period, '12-31')}")
        for c, bill in mentions(r.description, congress):
            reasons["named"] += 1
            if c not in when:
                when[c] = introduced(c)
            intro = when[c].get(bill)
            if intro is None:
                reasons["no_such_bill"] += 1
                continue
            if (pd.Timestamp(intro) - end).days > SLACK_DAYS:
                reasons["not_yet_introduced"] += 1
                continue
            reasons["kept"] += 1
            rows.append({"congress": c, "bill_number": bill, "filing_uuid": r.filing_uuid,
                         "filing_year": int(r.filing_year), "quarter": QUARTER.get(r.filing_period),
                         "client_id": r.client_id, "client": r.client, "registrant_id": r.registrant_id,
                         "registrant": r.registrant, "issue_code": r.issue_code, "url": r.url})
    out = pd.DataFrame(rows, columns=["congress", "bill_number", "filing_uuid", "filing_year", "quarter", "client_id",
                                      "client", "registrant_id", "registrant", "issue_code", "url"])
    out = out.drop_duplicates(["congress", "bill_number", "filing_uuid", "issue_code"])
    named = set(out["filing_uuid"])
    reports = acts.drop_duplicates("filing_uuid")
    coverage = (reports.assign(names_bill=reports["filing_uuid"].isin(named))
                .groupby("filing_year").agg(reports=("filing_uuid", "size"), reports_naming_a_bill=("names_bill", "sum"))
                .reset_index())
    return out.sort_values(["congress", "bill_number", "filing_year", "quarter", "client"]), coverage, dict(reasons)


def main() -> None:
    p = argparse.ArgumentParser(description="Match bills named in lobbying reports to PartyCohesion's bills.")
    p.add_argument("paths", nargs="+", type=Path)
    a = p.parse_args()
    out, coverage, reasons = build(load(a.paths))
    if OUT.exists():  # keep years that weren't pulled this time
        old = pd.read_csv(OUT)
        out = pd.concat([old[~old["filing_year"].isin(coverage["filing_year"])], out], ignore_index=True)
    if COVERAGE.exists():
        oldc = pd.read_csv(COVERAGE)
        coverage = pd.concat([oldc[~oldc["filing_year"].isin(coverage["filing_year"])], coverage]).sort_values("filing_year")
    out.to_csv(OUT, index=False, compression="gzip")
    coverage.to_csv(COVERAGE, index=False)
    print(json.dumps(reasons), f"{len(out):,} report-bill links -> {OUT}", sep="\n")


if __name__ == "__main__":
    main()
