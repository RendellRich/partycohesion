#!/usr/bin/env python3
"""
Build data/president_positions.csv: the president's stated position on bills, read from the
White House Statements of Administration Policy (SAPs).

Usage:
    python scripts/build_president_positions.py                 # all administrations from Obama on
    python scripts/build_president_positions.py --current-only  # only re-read the current administration

Source: https://github.com/unitedstates/statements-of-administration-policy (public domain).
Each statement is a PDF; its position is read from the standard wording ("The Administration
strongly supports...", "...would recommend that the President veto..."). Statements without a
clear support/oppose sentence are kept with position "Unclear" and are not used.

Needs git and pdftotext (poppler-utils). Run from the project root.
"""

from pathlib import Path
import argparse
import re
import shutil
import subprocess
import sys

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
REPO_DIR = RAW / "statements-of-administration-policy"
OUT = ROOT / "data" / "president_positions.csv"
REPO_URL = "https://github.com/unitedstates/statements-of-administration-policy"

# PDFs exist from the Obama administration on
ADMINISTRATIONS = [
    ("44-Obama", "Obama", "Democrat"),
    ("45-Trump", "Trump", "Republican"),
    ("46-Biden", "Biden", "Democrat"),
    ("47-Trump", "Trump", "Republican"),
]

SUP = r"Administration (?:strongly |fully |continues to |also )?(?:supports?|endorses)\b"
OPP = (r"Administration (?:strongly |continues to |also )?opposes?\b|Administration cannot support|"
       r"Administration does not support|Administration is (?:strongly )?opposed to")
VETO = r"recommend (?:that )?(?:the President|he|she) (?:would )?veto|(?:the President|he|she) would veto|recommend a veto|would be vetoed"
# "If the final bill includes X, ... veto" is a warning about changes, not a threat against the bill as written
CONDITIONAL = (r"\bif (?:the )?final (?:bill|version|legislation|conference)|"
               r"\bif .{0,120}(?:contains|includes|were amended|is amended|were to include|retains|were modified)\b")


def position(text: str) -> str:
    s, o = re.search(SUP, text), re.search(OPP, text)
    first = None
    if s and (not o or s.start() < o.start()):
        first = "Support"
    elif o:
        first = "Oppose"
    for m in re.finditer(VETO, text, re.I):
        start = text.rfind(".", 0, m.start()) + 1
        if not re.search(CONDITIONAL, text[start:m.end() + 40], re.I):
            return "Oppose"
    return first or "Unclear"


def chamber(text: str):
    m = re.search(r"\((House|Senate)[^)]{0,30}\)", text[:600])
    return m.group(1) if m else None


def fetch(admins):
    if not shutil.which("pdftotext"):
        sys.exit("pdftotext not found: install poppler-utils")
    if not (REPO_DIR / ".git").exists():
        RAW.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--sparse", REPO_URL, str(REPO_DIR)], check=True)
    else:
        subprocess.run(["git", "-C", str(REPO_DIR), "pull", "-q", "--depth", "1"], check=True)
    paths = ["/archive/*.yaml"] + [f"/archive/statements/{a}/" for a, _, _ in admins]
    subprocess.run(["git", "-C", str(REPO_DIR), "sparse-checkout", "set", "--no-cone", *paths], check=True)


def read_pdf(path: Path) -> str:
    out = subprocess.run(["pdftotext", "-layout", "-q", str(path), "-"], capture_output=True, text=True)
    return re.sub(r"\s+", " ", out.stdout)


def build(admins) -> pd.DataFrame:
    rows = []
    for admin, president, party in admins:
        for s in yaml.safe_load((REPO_DIR / "archive" / f"{admin}.yaml").read_text(encoding="utf-8")):
            if not s.get("file") or s.get("rescinded"):
                continue
            pdf = REPO_DIR / "archive" / s["file"]
            text = read_pdf(pdf) if pdf.exists() else ""
            rows.append({
                "administration": admin, "president": president, "president_party": party,
                "congress": s["congress"], "date": str(s["date_issued"]),
                "bills": ";".join(b.upper() for b in s["bills"]), "chamber": chamber(text),
                "title": s.get("document_title", ""), "position": position(text) if text else "Unclear",
                "statement_url": s.get("fetched_from_url", ""),
            })
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-only", action="store_true", help="only re-read the current administration")
    args = parser.parse_args()
    admins = ADMINISTRATIONS[-1:] if args.current_only else ADMINISTRATIONS
    fetch(admins)
    new = build(admins)
    if args.current_only and OUT.exists():
        old = pd.read_csv(OUT)
        new = pd.concat([old[~old["administration"].isin([a for a, _, _ in admins])], new], ignore_index=True)
    new = new.sort_values(["date", "bills"]).reset_index(drop=True)
    new.to_csv(OUT, index=False)
    print(f"Wrote {OUT.name}: {len(new)} statements")
    print(new.groupby(["administration", "position"]).size().unstack(fill_value=0))


if __name__ == "__main__":
    main()
