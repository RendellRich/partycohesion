"""Links from a member's vote to their own remarks on that bill in the Congressional Record, from
data/floor_remarks_index.csv.gz (built by scripts/floor_remarks_index.py, which checks each one against the text).
Used by the Members page and the member spotlight cards. The link shows where a member spoke about the bill; it says
nothing about what they said."""

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
BEFORE_DAYS, AFTER_DAYS = 30, 7  # remarks this close to the vote count as being about it
COLUMNS = ["bioguide_id", "congress", "bill_number", "date", "chamber", "url"]


def granule_url(date: str, granule: str) -> str:
    return f"https://www.govinfo.gov/content/pkg/CREC-{date}/html/CREC-{date}-{granule}.htm"


def load_index() -> pd.DataFrame:
    path = DATA_DIR / "floor_remarks_index.csv.gz"
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_csv(path)
    df["url"] = [granule_url(d, g) for d, g in zip(df["date"], df["granule"])]
    return df[COLUMNS]


def remark_near(spoke: pd.DataFrame, bill, date) -> str | None:
    """URL of the member's remarks on this bill closest to the vote date: up to 30 days before it or 7 days after."""
    if not isinstance(bill, str) or spoke.empty:
        return None
    r = spoke[spoke["bill_number"] == bill]
    if r.empty:
        return None
    gap = (pd.to_datetime(r["date"]) - pd.Timestamp(date)).dt.days
    r = r[(gap >= -BEFORE_DAYS) & (gap <= AFTER_DAYS)]
    if r.empty:
        return None
    return r.loc[(pd.to_datetime(r["date"]) - pd.Timestamp(date)).dt.days.abs().idxmin(), "url"]


def attach(record: pd.DataFrame, bioguide: str, index: pd.DataFrame) -> pd.Series:
    """For each roll call in a member's record (columns congress, bill_number, date), the link to their remarks."""
    spoke = index[index["bioguide_id"] == bioguide]
    if spoke.empty or record.empty:
        return pd.Series([None] * len(record), index=record.index, dtype=object)
    by_congress = {c: g for c, g in spoke.groupby("congress")}
    return pd.Series([remark_near(by_congress.get(c, spoke.iloc[0:0]), b, d)
                      for c, b, d in zip(record["congress"], record["bill_number"], record["date"])],
                     index=record.index, dtype=object)
