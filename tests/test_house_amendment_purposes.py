"""Matching House amendment roll calls to their amendment records, with the network replaced by canned answers."""
import sys
import xml.etree.ElementTree as ET
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

# A GovInfo bill status file, cut down to what the script reads
BILL_STATUS_112_HR_2112 = f"""<billStatus><bill><amendments>
  <amendment><number>500</number><type>HAMDT</type><purpose>{OLD}</purpose>
    <actions><actions><item><recordedVotes><recordedVote>
      <rollNumber>380</rollNumber><chamber>House</chamber><sessionNumber>1</sessionNumber>
    </recordedVote></recordedVotes></item></actions></actions></amendment>
  <amendment><number>501</number><type>HAMDT</type><description>(See item 759 for explanation.).</description>
    <actions><actions><item><text>Agreed to by voice vote.</text></item></actions></actions></amendment>
  <amendment><number>12</number><type>SAMDT</type><purpose>A Senate amendment</purpose></amendment>
</amendments></bill></billStatus>"""

# Canned Congress.gov answers, shaped like the API's JSON
ANSWERS = {
    "/house-vote/118/1/300": {"houseRollCallVote": {"amendmentNumber": "222", "amendmentType": "HAMDT"}},
    "/amendment/118/hamdt/222": {"amendment": {"purpose": JACKSON}},
}
FILES = {hap.BILL_STATUS.format(congress=112, kind="hr", number="2112"): BILL_STATUS_112_HR_2112}


class FakeClient(hap.Client):
    def __init__(self, *a, **k):
        super().__init__("key", budget=100, pause=0)
        self.asked = []

    def get(self, path_or_url, **params):
        self._check()
        self.used += 1
        self.asked.append(path_or_url)
        return ANSWERS.get(path_or_url)

    def get_xml(self, url):
        self._check()
        self.used += 1
        self.asked.append(url)
        return ET.fromstring(FILES[url]) if url in FILES else None


def _setup_files(tmp_path, monkeypatch):
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
    return amend_file


def test_clean_purpose_and_bill_path():
    assert hap.clean_purpose(JACKSON).startswith("Prohibit the Secretary of Defense from paying")
    assert hap.clean_purpose(OLD) == "Prohibit funds for the program"
    assert hap.clean_purpose(float("nan")) == ""
    assert len(hap.clean_purpose("x " * 400)) <= hap.MAX_PURPOSE
    assert hap.bill_path("H R 2670") == ("hr", "2670") and hap.bill_path("H J RES 7") == ("hjres", "7")
    assert hap.bill_path("QUORUM") is None


def test_bill_status_amendments():
    items = hap.bill_status_amendments(ET.fromstring(BILL_STATUS_112_HR_2112))
    assert items == [{"number": "500", "purpose": "Prohibit funds for the program", "votes": [(1, 380)]},
                     {"number": "501", "purpose": "", "votes": []}]  # "(See item ...)" isn't a purpose


def test_run_matches_both_eras_and_feeds_descriptions(tmp_path, monkeypatch):
    amend_file = _setup_files(tmp_path, monkeypatch)
    client = FakeClient()
    assert hap.run(budget=100, key="key", client=client) == 2
    assert client.asked[0].endswith("BILLSTATUS-112hr2112.xml")  # one file for the older bill
    a = pd.read_csv(amend_file, dtype={"hamdt": str})
    assert set(a["hamdt"]) == {"222", "500"}
    assert hap.run(budget=100, key="key", client=FakeClient()) == 0  # nothing looked up twice

    votes = pd.DataFrame({"congress": [118, 112], "chamber": ["House", "House"], "rollnumber": [299, 370],
                          "vote_desc": ["Jackson of Texas Amendment No. 5 to H.R. 2670", None]})
    out = hvl.apply_labels(votes)
    assert out.loc[0, "vote_desc"] == ("Jackson of Texas Amendment No. 5 to H.R. 2670: Prohibit the Secretary of "
                                       "Defense from paying for or reimbursing expenses relating to abortion services")
    assert out.loc[1, "vote_desc"] == "Flake of Arizona Amendment to H.R. 2112: Prohibit funds for the program"


def test_without_a_key_only_older_amendments_are_looked_up(tmp_path, monkeypatch):
    amend_file = _setup_files(tmp_path, monkeypatch)
    client = FakeClient()
    assert hap.run(budget=100, key="", client=client) == 1
    assert not any(str(p).startswith("/") for p in client.asked)  # no Congress.gov API calls
    assert set(pd.read_csv(amend_file, dtype={"hamdt": str})["hamdt"]) == {"500"}


def test_no_key_message(monkeypatch, capsys, tmp_path):
    _setup_files(tmp_path, monkeypatch)
    monkeypatch.delenv("CONGRESS_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["house_amendment_purposes.py"])
    monkeypatch.setattr(hap, "Client", FakeClient)
    hap.main()
    assert "No CONGRESS_API_KEY" in capsys.readouterr().out


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
            raise KeyboardInterrupt  # the job is killed after the older bills, during the 2023 lookups

    with pytest.raises(KeyboardInterrupt):
        hap.run(budget=100, key="key", client=KilledClient())
    a = pd.read_csv(amend_file, dtype={"hamdt": str})
    assert list(a["hamdt"]) == ["500"]  # the older match found before the cut-off was kept


def test_older_files_without_recorded_votes_use_the_action_text():
    old_schema = """<billStatus><bill><amendments><amendment>
      <number>445</number><congress>115</congress><type>HAMDT</type><purpose>To add funds.</purpose>
      <latestAction><actionDate>2017-09-14</actionDate>
        <text>On agreeing to the Jackson Lee amendment (A173) Agreed to by recorded vote: 265 - 143 (Roll no. 526).</text>
      </latestAction></amendment></amendments></bill></billStatus>"""
    assert hap.bill_status_amendments(ET.fromstring(old_schema)) == [
        {"number": "445", "purpose": "To add funds", "votes": [(1, 526)]}]
