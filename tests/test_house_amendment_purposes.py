"""Matching House amendment roll calls to Congress.gov amendment records, with the API replaced by canned answers."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import house_amendment_purposes as hap  # noqa: E402
import house_vote_labels as hvl  # noqa: E402

JACKSON = ("An amendment numbered 5 printed in Part A of House Report 118-125 to prohibit the Secretary of Defense "
           "from paying for or reimbursing expenses relating to abortion services.")
OLD = "An amendment to prohibit funds for the program."

# Canned Congress.gov answers, shaped like the API's JSON
ANSWERS = {
    "/house-vote/118/1/300": {"houseRollCallVote": {"amendmentNumber": "222", "amendmentType": "HAMDT"}},
    "/amendment/118/hamdt/222": {"amendment": {"purpose": JACKSON}},
    "/bill/112/hr/2112/amendments": {"amendments": [{"number": "500", "type": "HAMDT"},
                                                    {"number": "501", "type": "HAMDT"}], "pagination": {}},
    "/amendment/112/hamdt/500/actions": {"actions": [{"recordedVotes": [
        {"chamber": "House", "rollNumber": 380, "sessionNumber": 1}]}], "pagination": {}},
    "/amendment/112/hamdt/501/actions": {"actions": [{"text": "On agreeing to the amendment Agreed to by voice vote."}]},
    "/amendment/112/hamdt/500": {"amendment": {"purpose": OLD}},
}


class FakeClient(hap.Client):
    def __init__(self, *a, **k):
        super().__init__("key", budget=100, pause=0)

    def get(self, path_or_url, **params):
        self.used += 1
        return ANSWERS.get(path_or_url)


def test_clean_purpose_and_bill_path():
    assert hap.clean_purpose(JACKSON).startswith("Prohibit the Secretary of Defense from paying")
    assert hap.clean_purpose(OLD) == "Prohibit funds for the program"
    assert hap.clean_purpose(float("nan")) == ""
    assert len(hap.clean_purpose("x " * 400)) <= hap.MAX_PURPOSE
    assert hap.bill_path("H R 2670") == ("hr", "2670") and hap.bill_path("H J RES 7") == ("hjres", "7")
    assert hap.bill_path("QUORUM") is None


def test_run_matches_both_eras_and_feeds_descriptions(tmp_path, monkeypatch):
    labels = pd.DataFrame([
        {"congress": 118, "rollnumber": 299, "year": 2023, "clerk_rollnumber": 300, "legis_num": "H R 2670",
         "amendment_author": "Jackson of Texas Amendment No. 5", "clerk_vote_desc": None},
        {"congress": 112, "rollnumber": 370, "year": 2011, "clerk_rollnumber": 380, "legis_num": "H R 2112",
         "amendment_author": "Flake of Arizona Amendment", "clerk_vote_desc": None},
    ])
    labels_file, amend_file = tmp_path / "labels.csv", tmp_path / "amendments.csv"
    labels.to_csv(labels_file, index=False)
    for mod in (hap, hvl):
        monkeypatch.setattr(mod, "LABELS_FILE", labels_file)
        monkeypatch.setattr(mod, "AMENDMENTS_FILE", amend_file)
    monkeypatch.setattr(hap, "Client", FakeClient)

    assert hap.run(budget=100, key="key") == 2
    a = pd.read_csv(amend_file, dtype={"hamdt": str})
    assert set(a["hamdt"]) == {"222", "500", "501"}  # 501 cached as checked, with no roll call
    assert hap.run(budget=100, key="key") == 0  # nothing looked up twice

    votes = pd.DataFrame({"congress": [118, 112], "chamber": ["House", "House"], "rollnumber": [299, 370],
                          "vote_desc": ["Jackson of Texas Amendment No. 5 to H.R. 2670", None]})
    out = hvl.apply_labels(votes)
    assert out.loc[0, "vote_desc"] == ("Jackson of Texas Amendment No. 5 to H.R. 2670: Prohibit the Secretary of "
                                       "Defense from paying for or reimbursing expenses relating to abortion services")
    assert out.loc[1, "vote_desc"] == "Flake of Arizona Amendment to H.R. 2112: Prohibit funds for the program"


def test_no_key_does_nothing(monkeypatch, capsys):
    monkeypatch.delenv("CONGRESS_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["house_amendment_purposes.py"])
    hap.main()
    assert "No CONGRESS_API_KEY" in capsys.readouterr().out
