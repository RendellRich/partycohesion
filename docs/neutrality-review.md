# Neutrality review

**Date:** November 6, 2026 · **Data through:** September 30, 2026 · **Scope:** every page of partycohesion.streamlit.app, the data behind Position Flips, and the hand-picked lists

The question for every page: could a reasonable reader from either party say it was built to make their side look worse? Each item below says what was checked, what was found, and what was done.

## Summary

- **Wording:** clean. No loaded words (for example flip-flop, hypocrite, extreme, caved) on any page. Labels describe votes, not people.
- **Visual choices:** clean. Party colors follow convention, and Position Flips patterns use one neutral hue so no label reads as good or bad.
- **Data:** two real imbalances in Position Flips that could mislead if the two parties were compared directly. Both are now disclosed on the site. One of them should be fixed in the method before any public claim about the parties.
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
| Explainer worked examples | Schumer was listed before McConnell, with no stated rule for the pick | Now listed alphabetically (McConnell, then Schumer). The rule is stated: the two parties' Senate leaders during the years both led (2017 to 2024). Their overall results are close (+34 and +37), so neither looks singled out |
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

**Still open (recommended next):** adjust the measure so a member's two piles are compared only within the same chamber-control situation, or show the shift separately when their party held the majority and when it didn't. This should happen before anything public compares the two parties.

## 5. Hand-picked content

| List | Found | Done |
|---|---|---|
| Debt limit votes (`data/flip_debt_limit_votes.csv`, 28 votes) | Listed by hand because increases ride on unrelated bills. Spans all four presidents | Already labeled and public |
| Major Legislation (`data/key_votes_custom.csv`, 13 votes) | All from 2025, the 119th Congress only. Chosen by hand with no written rule, so earlier Congresses show no such tab | Now labeled on Key Votes and Methodology as hand-picked and covering only the 119th Congress |

**Still open (recommended):** replace Major Legislation with a written rule applied to every Congress (for example, every bill signed into law that passed by roll call in both chambers and appears in a nonpartisan list of major laws), or drop the series.

## How to repeat this review

1. Search the page text for loaded words (the list in section 1).
2. Check every default selection, example and ordering, and confirm that a stated rule explains each one.
3. Recompute the two Position Flips tables above from `data/flip_votes.csv` and `data/flip_member_votes.csv`.
4. Read every hand-picked list in `data/`.
