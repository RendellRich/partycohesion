"""Matching House amendment roll calls to Congress.gov amendment records, with the API replaced by canned answers."""
import sys
from pathlib import Path

import pandas as pd
import pytest

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
    # 500's roll call isn't in its latest action, so its full history was read; once the bill's only roll call
    # was matched, 501 wasn't needed
    assert set(a["hamdt"]) == {"222", "500"}
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


def _setup_files(tmp_path, monkeypatch):
    labels = pd.DataFrame([
        {"congress": 118, "rollnumber": 299, "year": 2023, "clerk_rollnumber": 300, "legis_num": "H R 2670",
         "amendment_author": "Jackson of Texas Amendment No. 5", "clerk_vote_desc": None},
        {"congress": 112, "rollnumber": 370, "year": 2011, "clerk_rollnumber": 380, "legis_num": "H R 2112",
         "amendment_author": "Flake of Arizona Amendment", "clerk_vote_desc": None},
    ])
    labels_file, amend_file = tmp_path / "labels.csv", tmp_path / "amendments.csv"
    labels.to_csv(labels_file, index=False)
    monkeypatch.setattr(hap, "LABELS_FILE", labels_file)
    monkeypatch.setattr(hap, "AMENDMENTS_FILE", amend_file)
    return amend_file


def test_time_limit_stops_the_run_and_keeps_progress(tmp_path, monkeypatch):
    amend_file = _setup_files(tmp_path, monkeypatch)
    client = hap.Client("key", budget=100, pause=0, minutes=1)
    client.deadline = 0  # already past the time limit
    assert hap.run(budget=100, key="key", client=client) == 0
    assert amend_file.exists()  # still writes what it has


def test_progress_is_saved_before_a_run_is_cut_off(tmp_path, monkeypatch):
    amend_file = _setup_files(tmp_path, monkeypatch)
    monkeypatch.setattr(hap, "SAVE_EVERY", 1)

    class KilledClient(FakeClient):
        def get(self, path_or_url, **params):
            if path_or_url.startswith("/bill/"):  # the job is killed partway through the older records
                raise KeyboardInterrupt
            return super().get(path_or_url, **params)

    with pytest.raises(KeyboardInterrupt):
        hap.run(budget=100, key="key", client=KilledClient())
    a = pd.read_csv(amend_file, dtype={"hamdt": str})
    assert list(a["hamdt"]) == ["222"]  # the 2023 match found before the cut-off was kept


def test_latest_action_matches_without_reading_actions(tmp_path, monkeypatch):
    amend_file = _setup_files(tmp_path, monkeypatch)
    listed = {"amendments": [
        {"number": "500", "type": "HAMDT", "purpose": OLD,
         "latestAction": {"actionDate": "2011-07-12", "text": "On agreeing to the Flake amendment (A010) Failed by "
                                                              "recorded vote: 152 - 274 (Roll no. 380)."}},
        {"number": "501", "type": "HAMDT", "purpose": "Something else",
         "latestAction": {"actionDate": "2011-07-12", "text": "Amendment agreed to by voice vote."}},
    ], "pagination": {}}
    asked = []

    class ListClient(FakeClient):
        def get(self, path_or_url, **params):
            asked.append(path_or_url)
            if path_or_url == "/bill/112/hr/2112/amendments":
                self.used += 1
                return listed
            return super().get(path_or_url, **params)

    assert hap.run(budget=100, key="key", client=ListClient()) == 2
    assert not any(p.startswith("/amendment/112") for p in asked)  # purpose and roll call came from the list
    a = pd.read_csv(amend_file, dtype={"hamdt": str})
    row = a[a["hamdt"] == "500"].iloc[0]
    assert (row["session"], row["clerk_rollnumber"], row["purpose"]) == (1, 380, "Prohibit funds for the program")
    assert "501" not in set(a["hamdt"])  # not needed once the bill's roll call was matched, so not cached


def test_latest_roll_call():
    item = {"latestAction": {"actionDate": "2010-03-04", "text": "... Failed by recorded vote: 1 - 2 (Roll no. 99)."}}
    assert hap.latest_roll_call(111, item) == (2, 99)
    assert hap.latest_roll_call(111, {"latestAction": {"actionDate": "2010-03-04", "text": "By voice vote."}}) is None
