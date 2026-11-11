import sys
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import bill_topics  # noqa: E402

BILL = """<bill><type>HR</type><number>8800</number>
<titles><item><title>National Defense Authorization Act for Fiscal Year 2027</title></item>
<item><title>National Defense Authorization Act for Fiscal Year 2027</title></item></titles>
<policyArea><name>Armed Forces and National Security</name></policyArea>
<subjects><legislativeSubjects><item><name>Military pay</name></item><item><name>Shipbuilding</name></item>
</legislativeSubjects></subjects>
<summaries><summary><text>&lt;p&gt;This bill authorizes defense programs.&lt;/p&gt;</text></summary></summaries>
<amendments><amendment><description>Amendment to end the Afghanistan War Commission early.</description></amendment>
<amendment><description>Amendment on shipyard workforce.</description></amendment></amendments></bill>"""


def test_parts_keep_each_amendment_separate():
    bill = ET.fromstring(BILL)
    parts = bill_topics.profile_parts(bill)
    assert parts[0] == "National Defense Authorization Act for Fiscal Year 2027 Armed Forces and National Security"
    assert parts[1] == "Military pay Shipbuilding"
    assert parts[2] == "This bill authorizes defense programs."
    assert parts[3:] == ["Amendment to end the Afghanistan War Commission early.", "Amendment on shipyard workforce."]
    # The joined profile used to weight words is unchanged in content.
    assert all(p in bill_topics.profile(bill) for p in parts)


def test_rule_targets():
    assert bill_topics._rule_targets("Providing for consideration of the bill (H.R. 3074) to do X, and the bill "
                                     "(S. 12) to do Y") == {"HR3074", "S12"}
    assert bill_topics._rule_targets("A bill to name a post office (H.R. 5)") == set()
