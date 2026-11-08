"""Cosponsored, then voted no: parsing a bill status file and the committed data."""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import cosponsor_votes as cv  # noqa: E402

BILL = """<billStatus><bill><introducedDate>2023-01-09</introducedDate>
  <sponsors><item><bioguideId>A000001</bioguideId></item></sponsors>
  <cosponsors>
    <item><bioguideId>B000002</bioguideId><sponsorshipDate>2023-02-01</sponsorshipDate></item>
    <item><bioguideId>C000003</bioguideId><sponsorshipDate>2023-02-01</sponsorshipDate>
          <sponsorshipWithdrawnDate>2023-03-01</sponsorshipWithdrawnDate></item>
  </cosponsors>
  <actions>
    <item><actionDate>2023-04-01</actionDate><text>Reported (Amended) by the Committee on Ways and Means.</text></item>
    <item><actionDate>2023-05-01</actionDate><text>Passed/agreed to in House.</text></item>
  </actions>
  <amendments>
    <amendment><number>5</number><type>HAMDT</type>
      <latestAction><actionDate>2023-04-20</actionDate><text>On agreeing to the X amendment (A001) Agreed to by voice vote.</text></latestAction></amendment>
    <amendment><number>6</number><type>HAMDT</type>
      <latestAction><actionDate>2023-04-20</actionDate><text>On agreeing to the Y amendment (A002) Failed by recorded vote.</text></latestAction></amendment>
  </amendments>
</bill></billStatus>"""


def test_parse_bill_status():
    root = ET.fromstring(BILL)
    assert cv.signers(root) == {"A000001": ("Sponsor", "2023-01-09"), "B000002": ("Cosponsor", "2023-02-01")}
    assert cv.amendments_agreed(root) == ["2023-04-20"]  # the failed amendment isn't counted
    assert cv.change_dates(root) == ["2023-04-01"]


def test_committed_data_adds_up():
    votes = pd.read_csv(ROOT / "data" / "cosponsor_votes.csv")
    nays = pd.read_csv(ROOT / "data" / "cosponsor_nays.csv")
    assert votes["signers_nay"].sum() == len(nays) > 0
    # Social Security Fairness Act, House, Nov. 12, 2024: 10 cosponsors voted no, on unchanged text
    ssfa = votes[(votes["congress"] == 118) & (votes["bill"] == "HR82") & (votes["chamber"] == "House")].iloc[0]
    assert ssfa["signers_nay"] == 10 and not ssfa["changed_before_vote"]
