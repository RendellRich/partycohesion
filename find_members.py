"""Find your members by ZIP code or state, from data/current_seats.csv and data/zip_districts.csv (built by
scripts/member_lookup.py). Used on the Home page."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).parent / "data"
VALID_UNTIL = date(2027, 1, 3)  # the ZIP file uses 119th Congress district lines (see scripts/member_lookup.py)
OFFICIAL_LOOKUP = "https://www.house.gov/representatives/find-your-representative"


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    seats = pd.read_csv(DATA_DIR / "current_seats.csv")
    zips = pd.read_csv(DATA_DIR / "zip_districts.csv", dtype={"zip": str})
    return seats, zips


@st.cache_data
def load_cached() -> tuple[pd.DataFrame, pd.DataFrame]:
    return load()


def clean_zip(text: str) -> str | None:
    """'34219', '34219-1234' or ' 34219 ' -> '34219'; anything else -> None."""
    m = re.fullmatch(r"\s*(\d{5})(?:-\d{4})?\s*", str(text or ""))
    return m.group(1) if m else None


def lookup_zip(zip_code: str, seats: pd.DataFrame, zips: pd.DataFrame, today: date | None = None) -> dict:
    """The state, House districts (with the share of the ZIP's land in each) and members for a ZIP code.
    After VALID_UNTIL the district lines may be out of date, so only the state is used."""
    rows = zips[zips["zip"] == zip_code]
    if rows.empty:
        return {"found": False}
    state = rows["state_abbrev"].iloc[0]
    current_lines = (today or date.today()) < VALID_UNTIL
    out = {"found": True, "state": state, "lines_current": current_lines,
           "senators": seats[(seats["state_abbrev"] == state) & (seats["chamber"] == "Senate")]}
    house = seats[(seats["state_abbrev"] == state) & (seats["chamber"] == "House")]
    if current_lines:
        districts = rows[["district", "share"]].to_dict("records")
        out["districts"] = [{**d, "member": house[house["district"] == d["district"]]} for d in districts]
    else:
        out["districts"] = [{"district": d, "share": None, "member": house[house["district"] == d]}
                            for d in sorted(house["district"].unique())]
    return out


def state_members(state: str, seats: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    s = seats[seats["state_abbrev"] == state]
    return s[s["chamber"] == "Senate"], s[s["chamber"] == "House"].sort_values("district")


def district_label(state: str, district: int) -> str:
    return f"{state} at-large" if int(district) == 0 else f"{state}-{int(district)}"
