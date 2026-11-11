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

First, sections that are only lists or notices are skipped by title: bill introductions, committee meeting notices, messages between the chambers, the weekly schedule, and so on. That leaves **591,053** candidate links. Each one is then checked against the text of the section:

1. **Find the member's turns.** The text marks each speaker ("Mr. FITZPATRICK. Mr. Speaker, ..."). If the member has no turn in the text, there is nothing to link to.
2. **Keep only their own words.** Remove procedural lines ("I yield back", "I ask unanimous consent", "I demand a recorded vote"), statements explaining a missed vote, lists of how they would have voted, and documents read into the Record. At least 60 words must remain.
3. **Make sure it's about this bill.** If the section is about this bill, that's enough. Otherwise the member has to name it, by number ("H.R. 2913") or short title ("Ukraine Support Act"). And if they name a different bill from the same section but never this one, they were talking about the other bill.
4. **Make sure the words match the bill's topic.** Senators can speak on anything during a bill's debate time, and a member can stand in the right section without naming any bill. So the remarks are compared with what the bill is about: its titles, the Library of Congress subject terms, the start of its Congressional Research Service summary, and its amendments' descriptions, from GovInfo's BILLSTATUS data. The comparison is a TF-IDF similarity score, taken as the best match against either the whole description or any one part of it: the titles, the subject terms, the summary, or a single amendment. Remarks scoring under 0.07 share almost none of the bill's vocabulary, and are dropped. Why the best part, and how I picked 0.07, are below.

Then a vote links to the remark closest to it, from 30 days before the vote to a week after.

## Results

| What happened to the candidate link | Links | Share |
|---|---:|---:|
| Kept: the member's own words about the bill | 134,108 | 22.7% |
| Spoke, but not about this bill | 306,953 | 51.9% |
| No turn of theirs in the text (lists, notices) | 59,825 | 10.1% |
| Only procedural lines, or too short | 45,601 | 7.7% |
| Words don't match the bill's topic (step 4) | 26,765 | 4.5% |
| Only explained a missed vote | 17,801 | 3.0% |
| **Total candidates** | **591,053** | |

About one link in five survives. The biggest group is the third rule: the member spoke in a section that mentions the bill, but not about it.

By Congress:

| Congress | Years | Candidates | Pass steps 1 to 3 | Kept |
|---|---|---:|---:|---:|
| 110th | 2007 to 2008 | 147,474 | 30,574 | 26,824 |
| 111th | 2009 to 2010 | 75,416 | 25,488 | 22,320 |
| 112th | 2011 to 2012 | 66,956 | 17,447 | 14,345 |
| 113th | 2013 to 2014 | 50,922 | 14,736 | 11,608 |
| 114th | 2015 to 2016 | 49,573 | 15,390 | 12,643 |
| 115th | 2017 to 2018 | 42,601 | 14,159 | 11,697 |
| 116th | 2019 to 2020 | 46,940 | 12,894 | 10,546 |
| 117th | 2021 to 2022 | 52,693 | 11,741 | 9,355 |
| 118th | 2023 to 2024 | 32,043 | 9,818 | 7,959 |
| 119th | 2025 to 2026, in progress | 26,435 | 8,626 | 6,811 |

## How good is it?

I read random samples by hand, and I kept changing the rules until the samples stopped turning up new kinds of mistakes. Then I took fresh samples I hadn't seen and scored those.

**Before the topic step.** Steps 1 to 3 kept about 162,000 links. Of 40 random ones, 30 were clearly the member talking about that bill, 5 were unclear, and 5 were not. The misses included a weekly schedule announcement, a tribute to a colleague given during a bill's debate time, and speeches about a different bill in the same debate. None of them named a different bill, so the rules couldn't see them.

**Picking the topic threshold.** I scored every one of those links for similarity to its bill, then hand-labeled 100 of them, oversampling the low scores where the decision is made:

| Similarity score | Share of links | About the bill | Unclear | Not about the bill |
|---|---:|---:|---:|---:|
| under 0.03 | 9% | 6 of 25 | 3 | 16 |
| 0.03 to 0.06 | 9% | 9 of 25 | 4 | 12 |
| 0.06 to 0.10 | 14% | 15 of 25 | 6 | 4 |
| 0.10 to 0.15 | 18% | 12 of 15 | 1 | 2 |
| 0.15 and up | 50% | 9 of 10 | 0 | 1 |

The labels are in `writeups/data/topic_labels.csv`. Below 0.06, most links were wrong; above it, most were right. So the first version of step 4 dropped links under 0.06. The cost was real: weighting the sample by how common each score band is, it also dropped about 7.6% of the links that were right, mostly short remarks that don't use the bill's vocabulary. For links shown next to a member's name, I'd rather miss some than show a wrong one.

**Big bills lost the most.** Checking the live site, one of the dropped links was Rep. Jason Crow's speech in the 2026 defense authorization debate, against an amendment to end the Afghanistan War Commission early. It was plainly about the bill. But a defense authorization covers hundreds of subjects, and a speech about one amendment shares few words with all of them together. Across the 53 bills with 200 or more candidate links, the topic step dropped 19.9% of links, against 18.3% overall.

So step 4 now scores each speech against the whole description and against each part of it on its own, and keeps the best match. A part has to have at least 8 distinct weighted words to count by itself. Without that rule, an amendment described only as "In the nature of a substitute" matched any speech that used the word "substitute". I re-scored the same labels (the `best_part` column; 97 of the 100 could be matched to the current metadata) and picked 0.07 for the new score. Weighted the same way:

| | Whole description, under 0.06 dropped | Best part, under 0.07 dropped |
|---|---:|---:|
| Links kept | 82% | 83% |
| Kept links clearly about the bill | 83.9% | 84.8% |
| Kept links not about the bill | 10.4% | 9.8% |
| Right links dropped | 7.6% | 5.5% |

The threshold was picked on these labels, so the table flatters it a little. The fresh samples below are the real test. On big bills, the drop went from 19.9% to 16.6%, and Crow's speech is linked again.

**After the first topic step.** On a fresh sample of 40 kept links:

- **35** were clearly the member talking about that bill.
- **2** were unclear.
- **3** were not: two speeches on a different bill in the same section, and one about a nomination.

That's 87.5% clearly right, up from 75%, and 7.5% clearly wrong, down from 12.5%. It's a sample of 40, so treat both as rough.

**After best-part matching.** Two more samples I hadn't seen, labeled in `writeups/data/audit_best_part.csv`:

- Of 40 random kept links, **34** were clearly right, **3** unclear and **3** wrong: about the same as before (35, 2 and 3). The wrong ones were a senator discussing a different bill passed in the same request, a speech on a related air marshal bill, and a speech on a different telework bill.
- Of 20 links that best-part matching brought back, **18** were right, **1** unclear and **1** wrong. The wrong one is a bill number reused across Congresses: a 2013 speech about H.R. 3590 from 2009, the Affordable Care Act, linked to the 2013 bill with that number.

So the change brings back right links at about the same precision as the rest.

**Links that were dropped (recall).** Before the topic step, of 30 random dropped links where the member did have a turn in the text, 2 should have been kept and 1 more possibly. The topic step adds the 5.5% loss above.

Some early versions taught me more than the final numbers:

- One rule I added to catch off-topic speeches started dropping good links, because the metadata often doesn't mark which bill a section is about. Reading the section's title for the bill fixed that.
- A one-character typo in the Record (one leading space instead of two) was hiding a senator's 2,000-word speech.
- The missed-vote rule let through long lists of "had I been present" statements until I counted roll call numbers.

## How the site uses it

- The **Members** page links each vote to "Their remarks" when there is a checked remark near the vote. The caption says it shows where they spoke, not what they said.
- **Member spotlights** on the PartyCohesion Facebook Page only say "Spoke about it in the Congressional Record" when a checked link exists. Every week's spotlights also go through a pull request that a person reviews before anything posts.
- Nothing is coded or summarized automatically. Stances on the Campaign Statements page are coded by hand, separately.

## What I'd do next

- **Better topic matching.** TF-IDF only sees shared words. A sentence-embedding model would also match a speech about "the farm bill" to the "Agriculture Improvement Act", which would win back some of the 5.5% of right links the topic step drops.
- **A bigger labeled set.** The 100 labels above were enough to pick a threshold. Another 200, labeled blind to the score, would give a measured precision and recall, and would show when a rule change makes things worse.
- **Use the amendment numbers.** Many floor turns are about an amendment ("I call up my amendment No. 5812"). Linking amendment numbers to the vote on that amendment would be more exact than linking to the bill.

## Reproduce it

```
python scripts/floor_remarks_index.py --years 2007 2008 --report reasons.jsonl
```

Run it for each pair of years: 2007 2008 through 2025 2026. It needs no API key, since GovInfo serves the metadata, text and BILLSTATUS data directly. The full run downloads about 7 GB of the Record, mostly metadata, and caches it in `--cache`, plus about 60 MB of BILLSTATUS per Congress in `/tmp/billstatus`. `--report` writes the counts in the tables above, and `--topic-scores` writes each link's similarity score. The rules are in `scripts/floor_remarks_index.py`, and `tests/test_floor_remarks.py` pins the Fitzpatrick examples.

Data: Congressional Record and BILLSTATUS via GovInfo (U.S. Government Publishing Office, public domain); Voteview roll calls.
