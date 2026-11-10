# Checking the Congressional Record before linking to it

*Rendell Rich, November 2026. Part of [PartyCohesion](https://partycohesion.streamlit.app).*

PartyCohesion shows how every member of Congress voted since 2007. I wanted each vote to link to the member's own words about that bill, so readers could see their reasons instead of my guess at them. The Congressional Record has the words. The hard part turned out to be knowing which words go with which vote.

## The shortcut that doesn't work

GovInfo publishes structured metadata for every day of the Congressional Record. Each section of a day's Record lists the members who spoke in it, by their official Bioguide ID, and the bills it mentions. Join "who spoke" to "which bills" and you have a link from every member to every bill they talked about. From 2007 to 2026 that join produces **618,897** member-bill links.

Most of them are wrong. The metadata describes sections, not speeches. A member counts as "speaking" in a section if they said anything at all in it, and a section can mention many bills. Some examples from the real data:

- **A missed vote.** On December 17, 2025, Rep. Brian Fitzpatrick is listed as speaking in the debate on a rule covering four bills. All he said was "had I been present, I would have voted YEA on Roll Call No. 343." The shortcut turned that into "spoke about" four bills, including two he voted against his party on.
- **A list.** One section on January 5, 2007, the list of bills introduced that day, produced **41,888** links on its own. Every sponsor counts as a speaker for every bill in the list.
- **Floor time used for something else.** Senators often take the floor during one bill's debate to talk about something else. One senator spoke about a different bill entirely; another gave a tribute to a retiring colleague.
- **Rules.** The House debates a "rule" that sets the terms for several bills at once. A member who spoke about one of them gets linked to all of them.

These links would have gone onto public posts that name members of Congress. A wrong "here is what they said about it" is worse than no link.

## What the check does

First, sections that are only lists or notices are skipped by title: bill introductions, committee meeting notices, messages between the chambers, and so on. That leaves **592,933** candidate links. Each one is then checked against the text of the section:

1. **Find the member's turns.** The text marks each speaker ("Mr. FITZPATRICK. Mr. Speaker, ..."). If the member has no turn in the text, there is nothing to link to.
2. **Keep only their own words.** Remove procedural lines ("I yield back", "I ask unanimous consent", "I demand a recorded vote"), statements explaining a missed vote, lists of how they would have voted, and documents read into the Record. At least 60 words must remain.
3. **Make sure it's about this bill.** If the section is about this bill, that's enough. Otherwise the member has to name it, by number ("H.R. 2913") or short title ("Ukraine Support Act"). And if they name a different bill from the same section but never this one, they were talking about the other bill.

Then a vote links to the remark closest to it, from 30 days before the vote to a week after.

## Results

| What happened to the candidate link | Links | Share |
|---|---:|---:|
| Kept: the member's own words about the bill | 162,076 | 27.3% |
| Spoke, but not about this bill | 307,511 | 51.9% |
| No turn of theirs in the text (lists, notices) | 59,828 | 10.1% |
| Only procedural lines, or too short | 45,717 | 7.7% |
| Only explained a missed vote | 17,801 | 3.0% |
| **Total candidates** | **592,933** | |

About one link in four survives. The biggest group is the third rule: the member spoke in a section that mentions the bill, but not about it.

By Congress:

| Congress | Years | Candidates | Kept |
|---|---|---:|---:|
| 110th | 2007 to 2008 | 147,873 | 30,856 |
| 111th | 2009 to 2010 | 75,761 | 25,734 |
| 112th | 2011 to 2012 | 67,269 | 17,673 |
| 113th | 2013 to 2014 | 51,150 | 14,873 |
| 114th | 2015 to 2016 | 49,680 | 15,452 |
| 115th | 2017 to 2018 | 42,741 | 14,236 |
| 116th | 2019 to 2020 | 47,107 | 12,975 |
| 117th | 2021 to 2022 | 52,865 | 11,830 |
| 118th | 2023 to 2024 | 32,051 | 9,821 |
| 119th | 2025 to 2026, in progress | 26,436 | 8,626 |

## How good is it?

I read random samples by hand, and I kept changing the rules until the samples stopped turning up new kinds of mistakes. Then I took fresh samples I hadn't seen and scored those.

**Links that pass (precision).** Of 40 random kept links:

- **30** were clearly the member talking about that bill.
- **5** were unclear.
- **5** were not about the bill: a weekly schedule announcement, a ruling on a budget point of order, a tribute to a colleague given during a bill's debate, and two speeches about a different bill in the same debate.

That's 75% clearly right and 12.5% clearly wrong, from a sample of 40, so treat both numbers as rough.

**Links that were dropped (recall).** Of 30 random dropped links where the member did have a turn in the text:

- **2** should have been kept: a committee chair speaking for a contempt resolution, and a member offering an amendment during an appropriations debate. Neither named the bill, and the section didn't mark which bill it was about.
- **1** more was possibly about the bill.

The check finds turns reliably. Reading every turn by hand isn't possible at this scale, but in samples the speaker matching found the member's turn for about 98% of real speakers. The early versions taught me more than the final numbers:

- One rule I added to catch off-topic speeches started dropping good links, because the metadata often doesn't mark which bill a section is about. Reading the section's title for the bill fixed that.
- A one-character typo in the Record (one leading space instead of two) was hiding a senator's 2,000-word speech.
- The missed-vote rule let through long lists of "had I been present" statements until I counted roll call numbers.

## How the site uses it

- The **Members** page links each vote to "Their remarks" when there is a checked remark near the vote. The caption says it shows where they spoke, not what they said.
- **Member spotlights** on the PartyCohesion Facebook Page only say "Spoke about it in the Congressional Record" when a checked link exists. Every week's spotlights also go through a pull request that a person reviews before anything posts.
- Nothing is coded or summarized automatically. Stances on the Campaign Statements page are coded by hand, separately.

## What I'd do next

- **Topic matching.** The remaining errors are mostly speeches on a different subject during a bill's debate. Comparing the speech to the bill's summary (Congress.gov has one for most bills) with a text-similarity score would catch most of them.
- **A labeled test set.** 200 hand-labeled links, split between kept and dropped, would turn the audit numbers above into a measured precision and recall, and would show when a rule change makes things worse.
- **Use the amendment numbers.** Many floor turns are about an amendment ("I call up my amendment No. 5812"). Linking amendment numbers to the vote on that amendment would be more exact than linking to the bill.

## Reproduce it

```
python scripts/floor_remarks_index.py --years 2007 2008 --report reasons.jsonl
```

Run it for each pair of years: 2007 2008 through 2025 2026. It needs no API key, since GovInfo serves the metadata and text directly. The full run downloads about 7 GB, mostly metadata, and caches it in `--cache`. `--report` writes the counts in the tables above. The rules are in `scripts/floor_remarks_index.py`, and `tests/test_floor_remarks.py` pins the Fitzpatrick examples.

Data: Congressional Record via GovInfo (U.S. Government Publishing Office, public domain); Voteview roll calls.
