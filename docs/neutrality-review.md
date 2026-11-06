# Neutrality review

**Date:** November 6, 2026 · **Data through:** September 30, 2026 · **Scope:** every page of partycohesion.streamlit.app, the data behind Position Flips, and the hand-picked lists

The question for every page: could a reasonable reader from either party say it was built to make their side look worse? Each item below says what was checked, what was found, and what was done.

## Summary

- **Wording:** clean. No loaded words (for example flip-flop, hypocrite, extreme, caved) on any page. Labels describe votes, not people.
- **Visual choices:** clean. Party colors follow convention, and Position Flips patterns use one neutral hue so no label reads as good or bad.
- **Data:** two real imbalances in Position Flips that could mislead if the two parties were compared directly. Both are now disclosed on the site. Chamber control is built into the score (section 6), and the missing Biden-era funding votes are filled in by written rules (section 7). With both fixed, the two parties' scores are close.
- **Hand-picked content:** the Major Legislation list covers only 2025 and was chosen by hand. It is now labeled that way. It should be replaced with a rule.

## 1. Wording

| Checked | Found | Done |
|---|---|---|
| Every page searched for loaded words (flip-flop, waver, hypocrite, loyal, extreme, radical, moderate, caved, betray, good, bad, worst, best, blame) | None in page text. "Principle" appears only in the caveat that a changed vote may reflect a changed bill, not a changed principle | Nothing needed |
| Pattern labels | "Consistent", "Partly changed", "Changed with the White House", "Opposite pattern" describe the votes, not the member | Nothing needed |
| "President-friendly vote" | Defined on every page that uses it as the side that gives whichever president is in office more room, and the explainer says it is not the "right" vote | Nothing needed |
| Em dashes in site prose | Five on the About page | Replaced |
| Overview heading | Read "119th Congress — House" and would misformat for some Congress numbers | Now "119th Congress: House" |

## 2. Defaults, order and examples

| Checked | Found | Done |
|---|---|---|
| Party order | Democrat before Republican everywhere, which is alphabetical | Rule now stated on Methodology |
| Explainer worked examples | Schumer was listed before McConnell, with no stated rule for the pick | Now listed alphabetically (McConnell, then Schumer). The rule is stated: the two parties' Senate leaders during the years both led (2017 to 2024). Neither is singled out: both are labeled Consistent (+22 and +3 compared like for like, as of section 7) |
| Default member pickers | Members, Compare and Position Flips start empty, so the site never chooses whom to show first | Nothing needed |
| Home page findings | Computed from all current members by fixed rules, with no party comparison | Nothing needed |

## 3. Visual choices

| Checked | Found | Done |
|---|---|---|
| Party colors | Blue, red and gray, the usual convention, all meeting WCAG contrast on the dark background | Nothing needed |
| Pattern colors | Shades of one violet, so "Changed" is not red and "Consistent" is not green | Nothing needed |
| Two-member comparisons | Use gold and light blue, deliberately not party colors | Nothing needed |

## 4. Position Flips data

### Votes are not spread evenly across presidents

| Category | Bush | Obama | Trump | Biden |
|---|---|---|---|---|
| Debt limit | 1 | 15 | 6 | 6 |
| Stopgap funding | 4 | 19 | 19 | 10 |
| Full-year funding | 0 | 5 | 9 | 0 |
| Disaster aid | 0 | 4 | 3 | 0 |
| War powers limits | 0 | 6 | 20 | 2 |
| **Total** | **5** | **49** | **57** | **18** |

Biden-era full-year funding and disaster aid are missing mostly because those bills passed as unrelated "vehicle" bills that the rules cannot detect without a White House statement naming them. Members who served in different years are therefore scored on different mixes of votes.

**Done:** the Position Flips "Limits" section now shows these counts, calculated live from the data, and Methodology explains the gap.

### The party running the chamber matters about as much as the president

Share of president-friendly votes, all categories, Democrats and Republicans only:

| Party | President | Chamber majority | President-friendly | Votes |
|---|---|---|---|---|
| Democrat | Other party's | Other party's | 25% | 6,061 |
| Democrat | Other party's | Own party's | 65% | 4,018 |
| Democrat | Own party's | Other party's | 71% | 5,652 |
| Democrat | Own party's | Own party's | 95% | 3,587 |
| Republican | Other party's | Other party's | 36% | 2,911 |
| Republican | Other party's | Own party's | 56% | 6,709 |
| Republican | Own party's | Other party's | 65% | 3,288 |
| Republican | Own party's | Own party's | 90% | 6,543 |

Holding chamber control fixed, both parties give their own party's president more room. The gap is 30 to 46 points for Democrats and 29 to 34 points for Republicans. So the effect the site measures is real in both parties. But chamber control moves votes by a similar amount, and each party held the majorities in different years. Among current members, 6% of Democrats and 34% of Republicans are labeled Consistent. That difference can't be read as one party being more principled until chamber control and the vote mix are accounted for.

**Done:** the Position Flips chart now has a caption saying to read it as a summary of members, not a verdict on either party. The Limits section, the explainer and Methodology now explain the chamber effect.

**Follow-up done:** the score now compares like with like. See section 6.

## 5. Hand-picked content

| List | Found | Done |
|---|---|---|
| Debt limit votes (`data/flip_debt_limit_votes.csv`, 28 votes) | Listed by hand because increases ride on unrelated bills. Spans all four presidents | Already labeled and public |
| Major Legislation (`data/key_votes_custom.csv`, 13 votes) | All from 2025, the 119th Congress only. Chosen by hand with no written rule, so earlier Congresses show no such tab | Now labeled on Key Votes and Methodology as hand-picked and covering only the 119th Congress |

**Still open (recommended):** replace Major Legislation with a written rule applied to every Congress (for example, every bill signed into law that passed by roll call in both chambers and appears in a nonpartisan list of major laws), or drop the series.

## 6. Follow-up: comparing like with like

**What changed.** The shift now compares a member's votes only within groups of the same **type of vote** cast when their party was in the same **position in the chamber** (running it, or not). It then takes a weighted average of the differences, with weight = own × other ÷ (own + other) votes. The simple difference is still shown next to it. Chamber control comes from member counts, with the evenly split 110th and 117th Senates set to the Democrats, who organized both. The data check fails if a future chamber ties without an entry.

**What it costs.** Votes with nothing comparable are set aside. Current members with a label went from 460 to 418, and every score now shows how many votes it rests on.

**What it showed (current members, data through September 30, 2026, before the vote list was completed; see section 7 for the current results):**

| | Simple difference | Like for like |
|---|---|---|
| All members labeled Consistent | 20% | 32% |
| Democrats labeled Consistent | 6% | 13% |
| Republicans labeled Consistent | 34% | 50% |
| Median shift, Democrats | 48 | 47 |
| Median shift, Republicans | 32 | 23 |

Checks on the like-for-like party gap:

- **By chamber:** median shift in the House is 50 for Democrats and 24.5 for Republicans. In the Senate it is 11 for Democrats and 20 for Republicans, so the gap there is smaller and runs the other way.
- **Leaving out one type of vote at a time:** the gap stays between 10 and 28 points whichever type is removed. The narrowest is 41 vs 31, without war powers votes.
- **Members with longer records:** among members with 10 or more compared votes on each side, the medians are 35 and 23.
- **Resampling members** (2,000 bootstrap draws): the 95% interval for the gap in median shift is 16 to 28 points.

**Reading it fairly.** Members of both parties give their own party's president more room on the same kinds of votes. Among current members, House Democrats do so more than House Republicans, and that holds up under these checks. It doesn't hold in the Senate, and it's smaller for members with longer records. So the site describes members individually and does not state a party-level conclusion.

## 7. Follow-up: completing the vote list

**What changed.** Full-year funding and disaster aid were selected by keyword, which missed most packages passed as unrelated "vehicle" bills (every Biden-era package among them) and caught some bills that never became law. Both are now hand-listed in `data/flip_funding_votes.csv` by written rules that treat every president the same way:

- **Full-year funding:** every enacted law that gave full-year funding to two or more of the twelve regular appropriations bills at once, fiscal year 2008 on, using the final vote in each chamber. Full-year continuing resolutions count here, not as stopgaps.
- **Disaster aid:** every enacted law containing a disaster relief supplemental of $10 billion or more, as listed by CBO, using the same vote rule.

All 73 listed votes were checked against the roll-call record for the right bill, a passing result and the final vote. The data check now fails if any listed vote goes missing.

**Votes by president, all five categories:**

| | Bush | Obama | Trump | Biden | Total |
|---|---|---|---|---|---|
| Before | 5 | 49 | 57 | 18 | 129 |
| After | 11 | 55 | 76 | 33 | 175 |

Full-year funding went from 0 to 9 Biden-era votes, and disaster aid from 0 to 6.

**What it showed (current members, compared like with like):**

| | Before | After |
|---|---|---|
| Members with a label | 418 | 441 |
| Median votes behind each score | 30 | 51 |
| Labeled Consistent, all | 32% | 34% |
| Labeled Consistent, Democrats | 13% | 24% |
| Labeled Consistent, Republicans | 50% | 44% |
| Median shift, Democrats | 47 | 35 |
| Median shift, Republicans | 23 | 27 |

- The 95% interval for the gap in median shift is now 3 to 13.5 points (it was 16 to 28).
- Leaving out war powers votes, the medians are 31 and 30. Most of the remaining gap comes from war powers votes, 20 of which fall under Trump and 2 under Biden.
- By chamber: the House median is 40 for Democrats and 29 for Republicans; the Senate median is 9 and 19.5.

**Reading it fairly.** Section 6's larger party gap came mostly from missing Biden-era votes, not from the members. With the vote list completed, members of both parties still give their own party's president more room on the same kinds of votes, by similar amounts. The site makes no party-level claim, and this result shows why that rule matters.

## How to repeat this review

1. Search the page text for loaded words (the list in section 1).
2. Check every default selection, example and ordering, and confirm that a stated rule explains each one.
3. Recompute the Position Flips tables above from `data/flip_votes.csv` and `data/flip_member_votes.csv`, including the like-for-like checks in section 6.
4. Read every hand-picked list in `data/`.
