"""The posting plan: spotlights every one or two days at varied times, one finding card a week, fixed by rule."""
import importlib.util
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("schedule_posts", ROOT / "scripts" / "schedule_posts.py")
sp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sp)

ORDER = [f"M{i:03d}" for i in range(60)]
TODAY = date(2026, 11, 10)


def plan(entries=(), posted=(), until=TODAY + timedelta(days=14)):
    return sp.plan(list(entries), set(posted), ORDER, 119, TODAY, until)


def test_spotlights_every_one_or_two_days_at_varied_times():
    new = plan()
    spots = [e for e in new if e["card"].startswith("member/")]
    days = [e["post_on"] for e in spots]
    gaps = [(b - a).days for a, b in zip(days, days[1:])]
    assert spots and all(1 <= g <= 3 for g in gaps)  # 3 only when a finding card took the day between
    times = [e["time"] for e in spots]
    assert all(a != b for a, b in zip(times, times[1:]))
    assert [e["card"] for e in spots] == [f"member/{b}" for b in ORDER[:len(spots)]]  # rotation order
    assert all(e["expires_after_days"] == 1 for e in spots)


def test_one_finding_a_week_on_its_own_day():
    new = plan()
    findings = [e for e in new if not e["card"].startswith("member/")]
    assert len(findings) == 2
    assert (findings[1]["post_on"] - findings[0]["post_on"]).days >= 5
    assert len({e["post_on"] for e in new}) == len(new)  # never two posts on one day


def test_respects_queued_days_and_featured_members_and_is_repeatable():
    queued = [{"id": "senate-unity-2026-11", "card": "senate-unity", "post_on": date(2026, 11, 17)},
              {"id": "spotlight-119-M000", "card": "member/M000", "post_on": date(2026, 11, 5)}]
    new = plan(queued, posted={"spotlight-119-M001"})
    assert date(2026, 11, 17) not in {e["post_on"] for e in new}
    cards = [e["card"] for e in new]
    assert "member/M000" not in cards and "member/M001" not in cards
    assert sum(not c.startswith("member/") for c in cards) == 1  # the week with senate-unity gets no second card
    assert new == plan(queued, posted={"spotlight-119-M001"})


def test_tops_up_after_the_last_spotlight():
    first = plan(until=TODAY + timedelta(days=14))
    again = plan(first, until=TODAY + timedelta(days=14))
    assert len(again) <= 1  # at most the last day, when the first plan's next gap ran past it
    assert plan(first + again, until=TODAY + timedelta(days=14)) == []
    later = plan(first, until=TODAY + timedelta(days=21))
    last = max(e["post_on"] for e in first if e["card"].startswith("member/"))
    assert later and min(e["post_on"] for e in later) > last


def test_yaml_quotes_times():
    out = sp.as_yaml([{"id": "x", "card": "member/M000", "post_on": date(2026, 11, 11), "time": "07:40",
                       "expires_after_days": 1}])
    assert 'time: "07:40"' in out and "expires_after_days: 1" in out
