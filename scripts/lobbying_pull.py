"""Download one year of Lobbying Disclosure Act quarterly reports from lda.gov, one row per lobbying activity.

    python scripts/lobbying_pull.py --year 2024 --out data/raw/lda

Writes data/raw/lda/lda_<year>.jsonl.gz. Set LDA_API_KEY for the registered rate limit (120 requests a minute instead
of 15). The API returns at most 25 reports a page, so a year (about 4,000 pages) takes an hour or more. Only quarterly reports, terminations and their amendments are kept: registrations and "no activity" reports
name no bills.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://lda.gov/api/v1/filings/"
REPORT = re.compile(r"^(?:Q[1-4]|[1-4][TA@])$")  # quarterly report, termination, amendment; not the "Y" no-activity forms
# Requests a minute for this process. lda.gov allows 120 a minute per key (15 without one), shared by everything using
# the key, so two jobs running at once each set LDA_RATE=55.
RATE = {True: 110, False: 14}


def fetch(url: str, key: str | None, tries: int = 6) -> dict:
    headers = {"Accept": "application/json", "User-Agent": "PartyCohesion (github.com/RendellRich/partycohesion)"}
    if key:
        headers["Authorization"] = f"Token {key}"
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise SystemExit("lda.gov rejected the API key (401). Check the LDA_API_KEY secret.") from e
            if e.code not in (429, 500, 502, 503, 504) or attempt == tries - 1:
                raise
            wait = int(e.headers.get("Retry-After") or 0) or 30 * (attempt + 1)
        except (urllib.error.URLError, TimeoutError):
            if attempt == tries - 1:
                raise
            wait = 30 * (attempt + 1)
        print(f"  waiting {wait}s before retrying", flush=True)
        time.sleep(wait)
    raise RuntimeError("unreachable")


def slim(filing: dict) -> list[dict]:
    """The fields the bill matcher needs, one row per lobbying activity on a quarterly report."""
    if not REPORT.match(filing.get("filing_type") or ""):
        return []
    reg, cli = filing.get("registrant") or {}, filing.get("client") or {}
    base = {"filing_uuid": filing["filing_uuid"], "filing_type": filing["filing_type"],
            "filing_year": filing["filing_year"], "filing_period": filing["filing_period"],
            "dt_posted": filing.get("dt_posted"), "registrant_id": reg.get("id"), "registrant": reg.get("name"),
            "client_id": cli.get("id"), "client": cli.get("name"), "income": filing.get("income"),
            "expenses": filing.get("expenses"), "url": filing.get("filing_document_url")}
    return [{**base, "issue_code": a.get("general_issue_code"), "description": a.get("description") or ""}
            for a in filing.get("lobbying_activities") or []]


def pull(year: int, out: Path, key: str | None, max_pages: int = 0) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"lda_{year}.jsonl.gz"
    url, pages, rows = f"{API}?filing_year={year}&page_size=25&ordering=dt_posted", 0, 0
    gap = 60 / float(os.environ.get("LDA_RATE") or RATE[bool(key)])
    last = 0.0
    with gzip.open(path, "wt", encoding="utf-8") as f:
        while url:
            time.sleep(max(0.0, last + gap - time.monotonic()))
            last = time.monotonic()
            page = fetch(url, key)
            for filing in page.get("results", []):
                for row in slim(filing):
                    f.write(json.dumps(row) + "\n")
                    rows += 1
            pages += 1
            if pages % 200 == 0:
                print(f"  {year}: {pages} pages of {(page.get('count', 0) + 24) // 25}, {rows:,} activities", flush=True)
            url = None if max_pages and pages >= max_pages else page.get("next")
    print(f"{year}: {pages} pages, {rows:,} activities -> {path}", flush=True)
    return path


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--out", type=Path, default=Path("data/raw/lda"))
    p.add_argument("--max-pages", type=int, default=0, help="stop after this many pages (for a quick test)")
    a = p.parse_args()
    key = os.environ.get("LDA_API_KEY") or None
    if not key:
        print("No LDA_API_KEY set: using the anonymous limit of 15 requests a minute.", flush=True)
    pull(a.year, a.out, key, a.max_pages)


if __name__ == "__main__":
    main()
