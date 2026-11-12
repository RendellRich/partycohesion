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


def test_titles_for_named_bills_only():
    links = pd.DataFrame({"congress": [118, 118, 117], "bill_number": ["HR8070", "HR8070", "HR1"]})
    names = {118: {"HR8070": "NDAA 2025", "HR2": "Secure the Border Act"}, 117: {}}
    out = L.bill_titles(links, titles=lambda c: names[c])
    assert out.to_dict("records") == [{"congress": 118, "bill_number": "HR8070", "title": "NDAA 2025"}]


def test_page_titles_prefer_official_then_votes(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from lobbying import bill_titles
    official = tmp_path / "t.csv.gz"
    pd.DataFrame({"congress": [118], "bill_number": ["HR8997"], "title": ["Energy and Water Act, 2025"]}).to_csv(
        official, index=False, compression="gzip")
    votes = pd.DataFrame({"congress": [118, 118, 118], "bill_number": ["HR8997", "HR7024", "HR4820"],
                          "label": ["Ogles of Tennessee Part A Amendment No. 36 to H.R. 8997", "Tax Relief Act",
                                    "Escobar of Texas Part B Amendment No. 5 to H.R. 4820"]})
    t = bill_titles(votes, official=official, checked=None)
    assert t[(118, "HR8997")] == "Energy and Water Act, 2025"
    assert t[(118, "HR7024")] == "Tax Relief Act"
    assert (118, "HR4820") not in t.index  # only an amendment vote: no title rather than the amendment's text


def test_store_round_trip_and_one_congress(tmp_path):
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    import lobbying_store as S
    links = pd.DataFrame({
        "congress": [118, 118, 118, 117], "bill_number": ["HR8070", "HR8070", "S12", "HR1"],
        "filing_uuid": ["a-1", "a-1", "a-1", "b-2"], "filing_year": [2024, 2024, 2024, 2022], "quarter": [2, 2, 2, 4],
        "client_id": pd.array([7, 7, 7, 9], dtype="Int64"), "client": ["Acme", "Acme", "Acme", "Beta"],
        "registrant_id": pd.array([3, 3, 3, 4], dtype="Int64"), "registrant": ["Firm", "Firm", "Firm", "Other"],
        "issue_code": ["DEF", "BUD", "DEF", "TAX"],
        "url": ["https://lda.gov/filings/public/filing/a-1/print/"] * 3 + ["https://lda.gov/filings/public/filing/b-2/print/"],
    })
    S.save(links, tmp_path)
    assert S.congresses(tmp_path) == [117, 118]
    back = S.read(tmp_path).sort_values(["congress", "bill_number", "issue_code"]).reset_index(drop=True)
    want = links.sort_values(["congress", "bill_number", "issue_code"]).reset_index(drop=True)
    for col in S.COLUMNS:
        assert back[col].astype(str).tolist() == want[col].astype(str).tolist(), col
    one = S.read(tmp_path, 118)
    assert set(one["congress"]) == {118} and len(one) == 3
    assert S.read(tmp_path / "missing").empty
