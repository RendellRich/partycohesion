"""House amendment votes get a description from the House Clerk's record when Voteview has none."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import house_vote_labels as h  # noqa: E402


def test_bill_label_and_session_year():
    assert h.bill_label("H R 2670") == "H.R. 2670"
    assert h.bill_label("H J RES  7") == "H.J.Res. 7"
    assert h.bill_label("S 5") == "S. 5"
    assert h.bill_label("QUORUM") == "" and h.bill_label(float("nan")) == ""
    assert h.session_year(112, 2) == 2012  # Jan 1, 2013 votes are filed under the 2012 session
    assert h.session_year(118, 1) == 2023


def test_describe():
    assert h.describe({"legis_num": "H R 2670", "amendment_author": "Jackson of Texas Amendment No. 5",
                       "clerk_vote_desc": float("nan")}) == "Jackson of Texas Amendment No. 5 to H.R. 2670"
    assert h.describe({"legis_num": "H RES 5", "amendment_author": "", "clerk_vote_desc": "Rules of the House"}) \
        == "Rules of the House"
    assert h.describe({"legis_num": "JOURNAL", "amendment_author": float("nan"), "clerk_vote_desc": float("nan")}) == ""


def test_apply_labels_fills_only_blank_house_rows():
    votes = pd.DataFrame({"congress": [118, 118, 118], "chamber": ["House", "House", "Senate"],
                          "rollnumber": [299, 1, 299], "vote_desc": [None, "Kept as is", None]})
    out = h.apply_labels(votes)
    # The committed data may add the amendment's purpose after a colon (see house_amendment_purposes.py)
    assert out.loc[0, "vote_desc"].startswith("Jackson of Texas Amendment No. 5 to H.R. 2670")
    assert out.loc[1, "vote_desc"] == "Kept as is"
    assert pd.isna(out.loc[2, "vote_desc"])  # Senate rows untouched
    assert list(out.columns) == list(votes.columns)


def test_committed_data_names_house_amendments():
    v = pd.read_csv(ROOT / "data" / "all_votes.csv")
    amend = v[(v["chamber"] == "House") & (v["vote_question"] == "On Agreeing to the Amendment")]
    assert amend["vote_desc"].isna().mean() < 0.02
    jackson = v[(v["congress"] == 118) & (v["chamber"] == "House") & (v["rollnumber"] == 299)]
    assert jackson["vote_desc"].iloc[0].startswith("Jackson of Texas")
