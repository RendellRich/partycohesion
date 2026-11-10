"""Links from votes to members' own floor remarks."""
import pandas as pd

import floor_remarks as fr

IDX = fr.load_index()


def test_index_shape_and_sources():
    assert list(IDX.columns) == fr.COLUMNS
    assert set(IDX["congress"]) >= {118, 119}
    assert IDX["url"].str.startswith("https://www.govinfo.gov/content/pkg/CREC-").all()
    assert set(IDX["chamber"]) <= {"House", "Senate"}


def test_window_picks_closest_remark_and_ignores_far_ones():
    spoke = pd.DataFrame({"bill_number": ["S2", "S2", "S2"], "date": ["2026-05-01", "2026-06-04", "2026-06-20"],
                          "url": ["far", "close", "after"]})
    assert fr.remark_near(spoke, "S2", "2026-06-05") == "close"
    assert fr.remark_near(spoke, "S2", "2026-08-01") is None  # nothing within 30 days before or 7 after
    assert fr.remark_near(spoke, None, "2026-06-05") is None


def test_known_example_cassidy_s2():
    rec = pd.DataFrame({"congress": [119], "bill_number": ["S2"], "date": ["2026-06-05"]})
    url = fr.attach(rec, "C001075", IDX).iloc[0]
    assert url and "CREC-2026-06-04" in url
