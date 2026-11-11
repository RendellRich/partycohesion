import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import lobbying_index as L  # noqa: E402
import lobbying_pull as P  # noqa: E402


@pytest.mark.parametrize("text, expected", [
    ("H.R.3949, End Cells in Cells Act", [(118, "HR3949")]),
    ("S. 1409 - Kids Online Safety Act S. 2511, the ADAPT Act", [(118, "S1409"), (118, "S2511")]),
    ("H.J.Res. 7 and H. Con. Res. 12", [(118, "HJRES7"), (118, "HCONRES12")]),
    # A law named by the year it passed, before this Congress began: an older law, not a current bill.
    ("H.R. 5376, Inflation Reduction Act of 2022", []),
    # A Public Law number says which Congress passed the bill.
    ("H.R. 5376, Inflation Reduction Act of 2022 (P.L. 117-169)", [(117, "HR5376")]),
    ("Public Law 117-58 H.R.3684 IIJA", [(117, "HR3684")]),
    ("H.R. 2, P.L. 118-5", [(118, "HR2")]),
    ("H.R. 1 (117th Congress)", [(117, "HR1")]),
    ("H.R. 4366, Consolidated Appropriations Act, 2024", [(118, "HR4366")]),
    # "U.S. 12" and a bare "S 2210" are not bills.
    ("U.S. 12 trade partners; HR 6453/S 2210", [(118, "HR6453")]),
])
def test_mentions(text, expected):
    assert L.mentions(text, 118) == expected


def test_congress_of_year():
    assert [L.congress_of(y) for y in (2007, 2008, 2023, 2024, 2025)] == [110, 110, 118, 118, 119]


def _act(uuid, ftype, posted, desc, period="first_quarter", client=1):
    return {"filing_uuid": uuid, "filing_type": ftype, "filing_year": 2024, "filing_period": period,
            "dt_posted": posted, "registrant_id": 9, "registrant": "Firm", "client_id": client, "client": "Client",
            "income": None, "expenses": None, "url": f"https://lda.gov/filings/public/filing/{uuid}/print/",
            "issue_code": "TAX", "description": desc}


def test_amendment_replaces_the_report_it_amends():
    acts = pd.DataFrame([_act("a", "Q1", "2024-04-19", "H.R. 1"), _act("b", "1A", "2024-05-02", "H.R. 2"),
                         _act("c", "Q1", "2024-04-19", "H.R. 3", client=2)])
    assert set(L.latest_reports(acts)["filing_uuid"]) == {"b", "c"}


def test_build_checks_the_bill_exists_and_was_introduced():
    intro = {118: {"HR1": "2023-01-09", "HR8800": "2024-06-20"}}
    acts = pd.DataFrame([_act("a", "Q1", "2024-04-19", "H.R. 1; H.R. 8800; H.R. 99999")])
    out, coverage, reasons = L.build(acts, introduced=lambda c: intro.get(c, {}))
    assert out["bill_number"].tolist() == ["HR1"]
    assert reasons == {"named": 3, "kept": 1, "not_yet_introduced": 1, "no_such_bill": 1}
    assert coverage.to_dict("records") == [{"filing_year": 2024, "reports": 1, "reports_naming_a_bill": 1}]


def test_slim_keeps_quarterly_reports_only():
    filing = {"filing_uuid": "u", "filing_type": "Q2", "filing_year": 2024, "filing_period": "second_quarter",
              "dt_posted": "2024-07-19", "registrant": {"id": 1, "name": "R"}, "client": {"id": 2, "name": "C"},
              "income": "10000.00", "expenses": None, "filing_document_url": "x",
              "lobbying_activities": [{"general_issue_code": "HCR", "description": "S. 12"},
                                      {"general_issue_code": "TAX", "description": None}]}
    rows = P.slim(filing)
    assert [(r["issue_code"], r["description"]) for r in rows] == [("HCR", "S. 12"), ("TAX", "")]
    assert P.slim({**filing, "filing_type": "RR"}) == []
    assert P.slim({**filing, "filing_type": "Q2Y"}) == []  # "no activity" report
