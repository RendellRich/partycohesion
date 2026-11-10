"""Fill social/posts.yml with member spotlights and finding cards for the next two weeks.

The rules, so no post is picked by hand:
  - Spotlights go out every one or two days, each at a different time of day (Eastern), in the fixed order from
    member_spotlights.spotlight_order(). A member is featured once per Congress.
  - One finding card goes out each week, the one posted least recently, on a day without a spotlight.
  - Days that already have a post in the queue are left alone, so entries added by hand keep their place.
The day gaps and times come from a seeded random draw, so the same queue always produces the same plan.

  python scripts/schedule_posts.py                      plan through 14 days from today, render the spotlights
  python scripts/schedule_posts.py --until 2026-11-24   plan through a given day
  python scripts/schedule_posts.py --dry-run            print the plan without writing anything

Each run only adds entries after the last one already queued, so running it weekly tops the queue up to two weeks
ahead. The weekly "Queue member spotlights" workflow does that and opens a pull request to review.
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import post_social as ps  # noqa: E402

# Finding cards in the order they rotate; partycohesion is the introduction, so it comes up least often.
FINDINGS = ["same-bill-different-vote", "floor-remarks", "senate-unity", "respect-for-marriage-act", "partycohesion"]
# Times of day (Eastern) a post can go out: mornings, lunch, after work and evenings.
SLOTS = ["07:40", "08:50", "11:45", "12:30", "16:50", "18:10", "19:35", "20:25"]
FINDING_SLOTS = ["09:15", "12:05", "18:40"]
SPOTLIGHT_EXPIRES_DAYS = 1  # a spotlight that couldn't go out within a day waits for the next plan instead
HORIZON_DAYS = 14


def spotlight_id(congress: int, bioguide: str) -> str:
    return f"spotlight-{congress}-{bioguide}"


def day_of(entry: dict) -> date:
    return entry["post_on"] if isinstance(entry["post_on"], date) else date.fromisoformat(str(entry["post_on"]))


def last_used(card: str, entries: list[dict]) -> date:
    """Most recent day a finding card is queued or went out (date.min if never). Posted entries stay in the queue."""
    return max((day_of(e) for e in entries if e["card"] == card), default=date.min)


def is_finding(entry: dict) -> bool:
    return not entry["card"].startswith("member/")


def plan(entries: list[dict], posted_ids: set[str], order: list[str], congress: int, today: date, until: date,
         seed: int = 119) -> list[dict]:
    """New queue entries from the day after the last queued spotlight (or tomorrow) through `until`."""
    start = max([today + timedelta(days=1)] + [day_of(e) + timedelta(days=1) for e in entries if not is_finding(e)])
    if start > until:
        return []
    taken = {day_of(e) for e in entries}
    featured = {e["card"].split("/", 1)[1] for e in entries if e["card"].startswith("member/")}
    featured |= {i.rsplit("-", 1)[1] for i in posted_ids if i.startswith(f"spotlight-{congress}-")}
    queue = [b for b in order if b not in featured]
    rng = random.Random(f"{seed}-{start.isoformat()}")
    new: list[dict] = []

    # One finding card per week, at least five days after the one before, unless that week already has one.
    week = start
    while week <= until:
        end = min(week + timedelta(days=6), until)
        findings = entries + new
        has = any(week <= day_of(e) <= end and is_finding(e) for e in findings)
        before = max((day_of(e) for e in findings if is_finding(e) and day_of(e) < week), default=date.min)
        free = [week + timedelta(days=i) for i in range((end - week).days + 1)]
        free = [x for x in free if x not in taken and (x - before).days >= 5]
        if not has and free and (end - week).days >= 3:  # don't squeeze one into a short tail
            card = min(FINDINGS, key=lambda c: (last_used(c, findings), FINDINGS.index(c)))
            day = rng.choice(free)
            new.append({"id": f"{card}-{day.isoformat()}", "card": card, "post_on": day,
                        "time": rng.choice(FINDING_SLOTS)})
            taken.add(day)
        week = end + timedelta(days=1)

    # Spotlights every one or two days.
    day, prev = start, None
    while day <= until and queue:
        if day not in taken:
            slot = rng.choice([s for s in SLOTS if s != prev])
            b = queue.pop(0)
            new.append({"id": spotlight_id(congress, b), "card": f"member/{b}", "post_on": day, "time": slot,
                        "expires_after_days": SPOTLIGHT_EXPIRES_DAYS})
            prev = slot
            taken.add(day)
            day += timedelta(days=rng.choice([1, 2]))
        else:
            day += timedelta(days=1)
    return sorted(new, key=lambda e: (e["post_on"], e["time"]))


def as_yaml(entries: list[dict]) -> str:
    out = []
    for e in entries:
        out.append(f"\n- id: {e['id']}\n  card: {e['card']}\n  post_on: {e['post_on'].isoformat()}\n"
                   f"  time: \"{e['time']}\"")
        if "expires_after_days" in e:
            out[-1] += f"\n  expires_after_days: {e['expires_after_days']}"
        out[-1] += "\n"
    return "".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--until", type=date.fromisoformat)
    ap.add_argument("--today", type=date.fromisoformat, default=date.today())
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    until = a.until or a.today + timedelta(days=HORIZON_DAYS)

    import member_spotlights as ms  # needs the data files; loaded only when planning for real
    d = ms.load()
    entries = ps.load_queue(ps.QUEUE)
    posted_ids = {i for i, _ in ps.load_posted(ps.POSTED)}
    new = plan(entries, posted_ids, ms.spotlight_order(d), d["latest"], a.today, until)
    if not new:
        print(f"The queue already runs through {until}. Nothing to add.")
        return 0
    for e in new:
        print(f"{e['post_on']:%a %b %d} {e['time']} ET  {e['card']}")
    if a.dry_run:
        return 0
    members = [e["card"].split("/", 1)[1] for e in new if e["card"].startswith("member/")]
    if members:
        for path in ms.render(d, members):
            print(path.relative_to(ROOT))
    with ps.QUEUE.open("a") as fh:
        fh.write(as_yaml(new))
    print(f"Added {len(new)} posts to {ps.QUEUE.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
