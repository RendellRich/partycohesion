"""Lobbying Disclosure Act reports that name a bill, matched by scripts/lobbying_index.py.

What these reports can't say, and the site must not imply:
- which members were lobbied: a report names only the chamber or agency contacted
- whether the client was for or against the bill: reports don't say
- how much was spent on any one bill: one amount covers everything on the report
- that lobbying changed a vote: timing next to a vote is not a cause
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

import lobbying_store
from lobbying_store import COLUMNS

DATA_DIR = Path(__file__).parent / "data"

CANT_SAY = ("Lobbying reports name the bills a client lobbied on, but not which members were contacted (only the "
            "House, the Senate or an agency), not whether the client was for or against the bill, and not how much was "
            "spent on it (one amount covers everything on a report). A report filed before a vote doesn't show that it "
            "changed the vote.")


def data_path() -> Path:
    """The folder written by scripts/lobbying_index.py (see lobbying_store.py)."""
    return Path(os.environ.get("LOBBYING_DATA") or DATA_DIR / "lobbying")


def _mtime(folder: Path) -> float:
    return max((f.stat().st_mtime for f in folder.glob("*.parquet")), default=0.0)


@st.cache_data(show_spinner=False)
def _congresses(path: str, mtime: float) -> list[int]:
    return lobbying_store.congresses(Path(path))


@st.cache_data(show_spinner=False, max_entries=3)
def _read(path: str, mtime: float, congress: int) -> pd.DataFrame:
    df = lobbying_store.read(Path(path), congress)
    df["issue"] = df["issue_code"].map(issue_names()).fillna(df["issue_code"])
    df["period"] = df["filing_year"] * 10 + df["quarter"]
    return df


def congresses() -> list[int]:
    """Congresses whose bills the reports name, oldest first; empty before the first download is merged."""
    path = data_path()
    return _congresses(str(path), _mtime(path)) if lobbying_store.exists(path) else []


def load(congress: int) -> pd.DataFrame:
    """Every report-bill link for one Congress (one Congress at a time keeps the app's memory small)."""
    path = data_path()
    if not lobbying_store.exists(path):
        return pd.DataFrame(columns=[*COLUMNS, "issue", "period"])
    return _read(str(path), _mtime(path), int(congress))


@st.cache_data
def issue_names() -> dict:
    path = DATA_DIR / "lobbying_issue_codes.csv"
    return dict(pd.read_csv(path).itertuples(index=False)) if path.exists() else {}


def quarter_label(year: int, quarter: int) -> str:
    return f"Q{int(quarter)} {int(year)}"


def bill_counts(links: pd.DataFrame) -> pd.DataFrame:
    """Per bill: reports naming it, clients, first and last quarter, and its most common issue areas."""
    if links.empty:
        return pd.DataFrame(columns=["congress", "bill_number", "reports", "clients", "first", "last", "issues"])
    g = links.groupby(["congress", "bill_number"])
    out = g.agg(reports=("filing_uuid", "nunique"), clients=("client_id", "nunique"),
                first=("period", "min"), last=("period", "max")).reset_index()
    top = (links.drop_duplicates(["congress", "bill_number", "filing_uuid", "issue"])
           .groupby(["congress", "bill_number"])["issue"]
           .agg(lambda s: ", ".join(s.value_counts().head(3).index)).rename("issues"))
    return out.merge(top, on=["congress", "bill_number"], how="left").sort_values("reports", ascending=False)


AMENDMENT = r"amendment no\.|^providing for (?:the )?consideration|^on (?:motion|cloture)"


@st.cache_data(show_spinner=False)
def _official(path: str, mtime: float) -> pd.Series:
    return pd.read_csv(path).dropna(subset=["title"]).set_index(["congress", "bill_number"])["title"]


def bill_titles(votes: pd.DataFrame, official: Path | None = DATA_DIR / "lobbying_bill_titles.csv.gz",
                checked: Path | None = DATA_DIR / "bill_titles.csv") -> pd.Series:
    """(congress, bill) -> a readable name: the display title from GovInfo (written by scripts/lobbying_index.py), else
    the checked title in data/bill_titles.csv, else the most common roll call description that isn't an amendment, a
    rule or a motion. A bill with none of these gets no title rather than an amendment's description."""
    v = votes.dropna(subset=["bill_number"])[["congress", "bill_number", "label"]]
    good = v[~v["label"].str.contains(AMENDMENT, case=False, regex=True, na=False)]
    best = good.groupby(["congress", "bill_number"])["label"].agg(lambda s: s.mode().iat[0])
    if checked is not None and checked.exists():
        known = pd.read_csv(checked).dropna(subset=["title"]).set_index(["congress", "bill_number"])["title"]
        best = known.combine_first(best)
    if official is not None and official.exists():
        best = _official(str(official), official.stat().st_mtime).combine_first(best)
    return best.rename("title")


def period_label(period: int) -> str:
    return quarter_label(period // 10, period % 10)


def summary_line(links: pd.DataFrame, congress: int, bill: str) -> str | None:
    """'214 lobbying reports from 63 clients named this bill, Q1 2023 to Q2 2024', or None."""
    one = links[(links["congress"] == congress) & (links["bill_number"] == bill)]
    if one.empty:
        return None
    n, c = one["filing_uuid"].nunique(), one["client_id"].nunique()
    first, last = period_label(int(one["period"].min())), period_label(int(one["period"].max()))
    span = first if first == last else f"{first} to {last}"
    return (f"{n:,} lobbying report{'s' if n != 1 else ''} from {c:,} client{'s' if c != 1 else ''} "
            f"named this bill, {span}.")
