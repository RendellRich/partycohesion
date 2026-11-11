"""What each bill is about, for checking that a member's floor remarks match the bill they're linked to.

Reads GovInfo's BILLSTATUS bulk data (public domain, no key): for every bill and resolution, its titles, the Library
of Congress policy area and subject terms, the latest CRS summary, and its amendments' descriptions. Each bill gets one
"profile" text built from those, which scripts/floor_remarks_index.py compares with the member's remarks.

  from bill_topics import profiles
  p = profiles(119)            # {"HR2913": "Ukraine Support Act ...", ...}

Downloads (about 60 MB a Congress) are cached in /tmp/billstatus.
"""

from __future__ import annotations

import functools
import html
import re
import urllib.request
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

CACHE = Path("/tmp/billstatus")
TYPES = ("hr", "s", "hres", "sres", "hjres", "sjres", "hconres", "sconres")
URL = "https://www.govinfo.gov/bulkdata/BILLSTATUS/{c}/{t}/BILLSTATUS-{c}-{t}.zip"
SUMMARY_WORDS = 250  # the start of the summary says what the bill does; the rest is section-by-section detail


def download(congress: int, cache: Path = CACHE) -> list[Path]:
    cache.mkdir(parents=True, exist_ok=True)
    out = []
    for t in TYPES:
        path = cache / f"BILLSTATUS-{congress}-{t}.zip"
        if not (path.exists() and path.stat().st_size > 0):
            try:
                with urllib.request.urlopen(URL.format(c=congress, t=t), timeout=300) as r:
                    path.write_bytes(r.read())
            except Exception:
                continue
        out.append(path)
    return out


def strip(text: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def profile(bill: ET.Element) -> str:
    titles = [strip(t.findtext("title")) for t in bill.findall("titles/item")]
    subjects = [strip(s.findtext("name")) for s in bill.findall("subjects/legislativeSubjects/item")]
    area = strip(bill.findtext("policyArea/name"))
    sums = bill.findall("summaries/summary") or bill.findall("summaries/item")
    summary = " ".join(strip(sums[-1].findtext("text")).split()[:SUMMARY_WORDS]) if sums else ""
    amends = [strip(a.findtext("description") or a.findtext("purpose")) for a in
              (bill.findall("amendments/amendment") or bill.findall("amendments/item"))]
    parts = list(dict.fromkeys(t for t in titles if t)) + [area] + subjects[:40] + [summary] + [a for a in amends if a][:60]
    return " ".join(p for p in parts if p)


@functools.lru_cache(maxsize=12)
def profiles(congress: int, cache: Path = CACHE) -> dict[str, str]:
    """{"HR2913": profile text} for every bill and resolution of a Congress."""
    out = {}
    for path in download(congress, cache):
        try:
            z = zipfile.ZipFile(path)
        except zipfile.BadZipFile:
            continue
        for name in z.namelist():
            try:
                bill = ET.fromstring(z.read(name)).find("bill")
            except ET.ParseError:
                continue
            if bill is None:
                continue
            key = f"{(bill.findtext('type') or bill.findtext('billType') or '').upper()}{bill.findtext('number')}"
            out[key] = profile(bill)
    # A rule ("Providing for consideration of the bill (H.R. 3074) ...") is about the bills it sets up for debate.
    for key, text in list(out.items()):
        if key.startswith("HRES") and re.match(r"providing for (?:the )?consideration", text, re.I):
            named = {re.sub(r"[^A-Z0-9]", "", b.upper()) for b in re.findall(r"\(((?:H|S)\.[^)]{1,20}?\d+)\)", text[:3000])}
            out[key] = text + " " + " ".join(out.get(b, "")[:3000] for b in sorted(named))
    return out
