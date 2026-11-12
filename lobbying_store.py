"""How the lobbying report-bill links are stored: two Parquet files in data/lobbying/.

- reports.parquet: one row per report (filing_uuid, year, quarter, client, registrant), numbered by `report`
- mentions.parquet: one row per report, bill and issue code (congress, bill_number, report, issue_code), sorted by
  congress so a page can read one Congress without loading the rest

A flat CSV repeated the client, registrant, report ID and link on every bill a report named: 2.5 million rows, 92 MB
compressed and about 680 MB in memory, too close to GitHub's 100 MB file limit and too big for the app.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

COLUMNS = ["congress", "bill_number", "filing_uuid", "filing_year", "quarter", "client_id", "client", "registrant_id",
           "registrant", "issue_code", "url"]
REPORT_COLS = ["filing_uuid", "filing_year", "quarter", "client_id", "client", "registrant_id", "registrant"]
URL = "https://lda.gov/filings/public/filing/{}/print/"


def save(links: pd.DataFrame, folder: Path) -> None:
    """Write report-bill links (COLUMNS; url is dropped and rebuilt from filing_uuid on read)."""
    folder.mkdir(parents=True, exist_ok=True)
    reports = (links[REPORT_COLS].drop_duplicates("filing_uuid")
               .sort_values(["filing_year", "quarter", "filing_uuid"]).reset_index(drop=True))
    reports.insert(0, "report", pd.RangeIndex(len(reports), dtype="int32"))
    ids = pd.Series(reports["report"].to_numpy(), index=reports["filing_uuid"])
    mentions = pd.DataFrame({
        "congress": links["congress"].astype("int16").to_numpy(),
        "bill_number": links["bill_number"].to_numpy(),
        "report": ids.reindex(links["filing_uuid"]).to_numpy().astype("int32"),
        "issue_code": links["issue_code"].to_numpy(),
    }).drop_duplicates().sort_values(["congress", "bill_number", "report", "issue_code"])
    for col, kind in (("filing_year", "int16"), ("quarter", "int8")):
        reports[col] = reports[col].astype(kind)
    for col in ("client_id", "registrant_id"):
        reports[col] = reports[col].astype("Int32")
    pq.write_table(pa.Table.from_pandas(reports, preserve_index=False), folder / "reports.parquet",
                   compression="zstd", use_dictionary=["client", "registrant"])
    pq.write_table(pa.Table.from_pandas(mentions, preserve_index=False), folder / "mentions.parquet",
                   compression="zstd", row_group_size=100_000, use_dictionary=["bill_number", "issue_code"])


def exists(folder: Path) -> bool:
    return (folder / "mentions.parquet").exists() and (folder / "reports.parquet").exists()


def congresses(folder: Path) -> list[int]:
    if not exists(folder):
        return []
    col = pq.read_table(folder / "mentions.parquet", columns=["congress"]).column("congress")
    return sorted(int(c) for c in pc.unique(col).to_pylist())


def read(folder: Path, congress: int | None = None) -> pd.DataFrame:
    """Report-bill links as one flat frame (COLUMNS), for one Congress or all of them."""
    if not exists(folder):
        return pd.DataFrame(columns=COLUMNS)
    filters = [("congress", "==", int(congress))] if congress is not None else None
    m = pq.read_table(folder / "mentions.parquet", filters=filters).to_pandas()
    r = pq.read_table(folder / "reports.parquet").to_pandas()
    r = r[r["report"].isin(m["report"].unique())]
    out = m.merge(r, on="report", how="left").drop(columns="report")
    for col in ("bill_number", "issue_code", "client", "registrant", "filing_uuid"):
        out[col] = out[col].astype(str)
    out["congress"] = out["congress"].astype(int)
    out["filing_year"] = out["filing_year"].astype(int)
    out["quarter"] = out["quarter"].astype(int)
    out["client_id"] = out["client_id"].astype("Int64")
    out["registrant_id"] = out["registrant_id"].astype("Int64")
    out["url"] = out["filing_uuid"].map(URL.format)
    return out[COLUMNS]
