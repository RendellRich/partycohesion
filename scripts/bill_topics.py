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


def _fields(bill: ET.Element) -> tuple[list[str], str, list[str], str, list[str]]:
    titles = list(dict.fromkeys(t for t in (strip(t.findtext("title")) for t in bill.findall("titles/item")) if t))
    subjects = [strip(s.findtext("name")) for s in bill.findall("subjects/legislativeSubjects/item")]
    area = strip(bill.findtext("policyArea/name"))
    sums = bill.findall("summaries/summary") or bill.findall("summaries/item")
    summary = " ".join(strip(sums[-1].findtext("text")).split()[:SUMMARY_WORDS]) if sums else ""
    amends = [strip(a.findtext("description") or a.findtext("purpose")) for a in
              (bill.findall("amendments/amendment") or bill.findall("amendments/item"))]
    return titles, area, subjects, summary, list(dict.fromkeys(a for a in amends if a))


def profile(bill: ET.Element) -> str:
    titles, area, subjects, summary, amends = _fields(bill)
    parts = titles + [area] + subjects[:40] + [summary] + amends[:60]
    return " ".join(p for p in parts if p)


def profile_parts(bill: ET.Element) -> list[str]:
    """The profile split into the pieces a speech can be about: the titles with the policy area, the subject terms,
    the summary, and each amendment on its own. A big bill such as a defense authorization covers hundreds of topics,
    and a speech on one amendment shares few words with all of them together, but many with that amendment."""
    titles, area, subjects, summary, amends = _fields(bill)
    parts = [" ".join(titles + [area]), " ".join(subjects), summary] + amends
    return [p for p in parts if p.strip()]


def _bills(congress: int, cache: Path):
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
            if bill is not None:
                yield f"{(bill.findtext('type') or bill.findtext('billType') or '').upper()}{bill.findtext('number')}", bill


def _rule_targets(text: str) -> set[str]:
    """Bills a rule ("Providing for consideration of the bill (H.R. 3074) ...") sets up for debate."""
    if not re.match(r"providing for (?:the )?consideration", text, re.I):
        return set()
    return {re.sub(r"[^A-Z0-9]", "", b.upper()) for b in re.findall(r"\(((?:H|S)\.[^)]{1,20}?\d+)\)", text[:3000])}


@functools.lru_cache(maxsize=12)
def _read(congress: int, cache: Path = CACHE) -> dict[str, tuple[str, list[str], str | None]]:
    """{"HR2913": (profile text, parts, introduced date)} for every bill and resolution, from one pass over the zips."""
    return {key: (profile(bill), profile_parts(bill), bill.findtext("introducedDate") or None)
            for key, bill in _bills(congress, cache)}


def parts(congress: int, cache: Path = CACHE) -> dict[str, list[str]]:
    """{"HR2913": [titles, subjects, summary, amendment, ...]} for every bill and resolution of a Congress. A rule also
    gets the parts of the bills it sets up."""
    out = {key: v[1] for key, v in _read(congress, cache).items()}
    for key, ps in list(out.items()):
        if key.startswith("HRES") and ps:
            for b in sorted(_rule_targets(ps[0])):
                out[key] = out[key] + out.get(b, [])
    return out


def introduced(congress: int, cache: Path = CACHE) -> dict[str, str]:
    """{"HR2913": "2025-04-14"}: when each bill or resolution of a Congress was introduced."""
    return {key: v[2] for key, v in _read(congress, cache).items() if v[2]}


def profiles(congress: int, cache: Path = CACHE) -> dict[str, str]:
    """{"HR2913": profile text} for every bill and resolution of a Congress."""
    out = {key: v[0] for key, v in _read(congress, cache).items()}
    # A rule ("Providing for consideration of the bill (H.R. 3074) ...") is about the bills it sets up for debate.
    for key, text in list(out.items()):
        if key.startswith("HRES"):
            named = _rule_targets(text)
            if named:
                out[key] = text + " " + " ".join(out.get(b, "")[:3000] for b in sorted(named))
    return out
