"""Check every floor quote in data/floor_statements.csv word for word against its Congressional Record page.

Fetches each source_url from GovInfo (public, no key) and confirms the quote appears in the page's text, ignoring
spacing, case and the Record's straight-quote marks. Prints any quote it can't find and exits 1 if there are any.

  python scripts/check_floor_quotes.py
"""

from __future__ import annotations

import html
import re
import sys
import urllib.request
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data" / "floor_statements.csv"


def normalize(text: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    for a, b in (("``", '"'), ("''", '"'), ("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"')):
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text).strip().lower()


def missing(rows: pd.DataFrame, fetch=None) -> list[tuple[str, str, str]]:
    """(bioguide_id, topic, quote) for each quote not found on its source page."""
    fetch = fetch or (lambda url: urllib.request.urlopen(url, timeout=60).read().decode("utf-8", "replace"))
    pages: dict[str, str] = {}
    out = []
    for r in rows[rows["quote"] != ""].itertuples(index=False):
        if r.source_url not in pages:
            pages[r.source_url] = normalize(fetch(r.source_url))
        if normalize(r.quote) not in pages[r.source_url]:
            out.append((r.bioguide_id, r.topic, r.quote))
    return out


def main() -> None:
    rows = pd.read_csv(DATA, dtype=str, keep_default_na=False)
    bad = missing(rows)
    for who, topic, quote in bad:
        print(f"NOT FOUND  {who}  {topic}: {quote[:120]}")
    print(f"{(rows['quote'] != '').sum()} quotes checked, {len(bad)} not found on their source page")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
