# Comparing votes with what members ran on: design and pilot

**Status:** built. Decisions A to D were settled on November 6, 2026 (section 5), and 39 topics from 2007 to 2026 are on the Platform Votes page (section 6).
**Date:** November 6, 2026. Data through September 30, 2026.

The goal: show where members voted against what they ran on, without the site taking a side. This document covers which sources can support that, a set of written rules, a two-topic pilot run under those rules, what the pilot taught, and the decisions needed before anything is built.

## 1. Which sources can say what a member ran on

| Source | What it is | Coverage | Neutral? | Verdict |
|---|---|---|---|---|
| **National party platforms** | Each party's official policy document, adopted at its convention every four years | Every member of both parties, by party | Yes, if the same rules apply to both platforms | **Use as the main source** |
| **Vote Smart's Political Courage Test** | The same issue questionnaire sent to every candidate | About 20% of candidates answered in 2024 and 24% in 2020, down from 72% in 1996. Incumbents answer far less often than challengers (26% vs 52% from 1992 to 2012). | The questions are identical for both parties, and both parties answer at similar rates | **Not usable as the main source.** For members who don't answer, Vote Smart fills in "likely responses" from its own research, which is Vote Smart's judgment, not the member's own words. Free API, but a key is needed and its copyright and attribution terms would need checking before republishing. At most, an optional extra for the few members who answered, clearly labeled. |
| **Signed pledges** (tax pledges, term limits and similar) | Specific, signed commitments | Only members who signed | No. Most pledges are signed mostly by one party, so a page built on them would lean one way. | **Do not use** |
| **Campaign websites and speeches** | Members' own words | Uneven, often deleted after the election | Hard to apply evenly | **Do not use** as a systematic source |

**Recommendation:** compare votes with the member's **party platform**, and say so plainly. The site would show where a member voted against what their party ran on, not against promises they personally made.

## 2. Proposed rules

These would be published on the site and applied the same way to both parties.

1. **Which platform applies.** Use the platform adopted in the presidential election year before the vote: 2016 platforms for the 115th and 116th Congresses, 2020 for the 117th and 118th, and 2024 for the 119th and 120th. In 2020 the Republican convention re-adopted its 2016 platform, so that text applies to 2021 to 2024. *(Decision A below covers the alternative.)*
2. **Which planks count.** Only planks that name a specific, testable action, such as a law, a program, a rate or a power. General aims like "grow the economy" are left out.
3. **Which votes count.** Only roll calls on the measure itself: passage, a joint resolution, or an amendment that adds or removes the policy. Procedural votes (cloture, motions to waive a budget rule, rules, motions to table) are shown separately and don't count in the headline. *(Decision B below.)*
4. **How strong each link is.** **Direct** means the vote is on exactly what the plank names. **Related** means same topic, different measure. Only direct links count toward a member's total. Related ones are shown as context.
5. **Topics in pairs, chosen before looking at results.** Each topic that tests one party's platform is paired with one that tests the other party's, ideally across Congresses with presidents of both parties (section 4 explains why). The list of topics, planks and votes is written down and published first. Only then are the member results computed.
6. **Everything is public.** Every plank-to-vote link lives in a data file with a link to the platform text and its page, a short paraphrase, the link strength, and who approved it. Readers can question any link.
7. **Neutral wording.** The site says "voted against their party's platform," never "broke a promise" or anything similar. It notes that members often give reasons the roll call can't show.

## 3. Pilot

Both topics were run under the rules above, using every relevant recorded vote in this data.

### Topic A: tariffs (119th Congress, tests the 2024 Republican platform)

- **Republican platform (2024):** supports "baseline Tariffs on Foreign-made goods" and the Trump Reciprocal Trade Act. A vote to keep across-the-board tariffs in place is consistent with it.
- **Democratic platform (2024):** criticizes sweeping import tariffs as making life more expensive for families. A vote to end across-the-board tariffs is consistent with it. *(An earlier draft of this document described this plank from a secondary source; it was rechecked against the platform text for the build.)*

| Vote | Link | Result | Against their own party's platform |
|---|---|---|---|
| S.J.Res. 49, end the global tariff emergency (Senate, Apr 30, 2025) | **Direct** | Failed 49–49 | Collins (R-ME), Murkowski (R-AK), Paul (R-KY) |
| S.J.Res. 88, end the global tariff emergency (Senate, Oct 30, 2025) | **Direct** | Passed 51–47 | Collins, McConnell (R-KY), Murkowski, Paul |
| S.J.Res. 37, end the Canada tariff emergency (Senate, Apr 2, 2025) | Related | Passed 51–48 | Collins, McConnell, Murkowski, Paul |
| S.J.Res. 81, end the Brazil tariff emergency (Senate, Oct 28, 2025) | Related | Passed 52–48 | Collins, McConnell, Murkowski, Paul, Tillis (R-NC) |
| S.J.Res. 77, end the Canada tariff emergency (Senate, Oct 29, 2025) | Related | Passed 50–46 | Collins, McConnell, Murkowski, Paul |
| H.J.Res. 72, end the Canada tariff emergency (House, Feb 11, 2026) | Related | Passed 219–211 | Bacon (R-NE), Fitzpatrick (R-PA), Hurd (R-CO), Kiley (R-CA), Massie (R-KY), Newhouse (R-WA); Golden (D-ME) |

The Canada and Brazil votes are "related" rather than "direct" because those tariffs were justified by fentanyl and by Brazil's prosecution of its former president, not as baseline tariffs.

### Topic B: $15 federal minimum wage (117th Congress, tests the 2020 Democratic platform)

- **Democratic platform (2020):** a $15 federal minimum wage is a signature commitment. A vote for it is consistent.
- **Republican platform (2016, re-adopted in 2020):** says the minimum wage "should be handled at the state and local level." A vote against a federal increase is consistent.

| Vote | Link | Result | Against their own party's platform |
|---|---|---|---|
| Motion to waive the Budget Act for the $15 minimum wage amendment to the American Rescue Plan (Senate, Mar 5, 2021) | **Direct topic, procedural form** | Rejected 42–58 | Carper (D-DE), Coons (D-DE), Hassan (D-NH), Manchin (D-WV), Shaheen (D-NH), Sinema (D-AZ), Tester (D-MT), King (I-ME, caucuses with Democrats) |

This is the only Senate roll call in the 117th Congress data whose description mentions the minimum wage, and it was procedural.

## 4. What the pilot taught

1. **One topic always looks one-sided.** In 2025 the tariff votes tested the president's own party's platform: Republicans had to choose between their platform and other concerns, while Democrats could vote their platform at no cost. In 2021 the minimum wage reversed that. Fairness has to come from **which topics are chosen**, which is why rule 5 pairs them and fixes the list before any results are seen.
2. **The same vote can mean two things.** Some Republicans who voted to end the tariff emergencies, Paul among them, framed it as Congress's power over tariffs rather than tariffs alone. Some Democrats who voted against the minimum wage motion cited the Senate's budget rules, timing or effects on small businesses rather than opposing a higher wage. The roll call can't tell these apart. This is the biggest risk of misleading readers, and it's why rule 3 keeps procedural votes out of the headline and rule 7 limits the wording.
3. **Direct tests are rare.** Six tariff votes produced two direct links. The minimum wage produced one, and it was procedural. A credible feature needs roughly 10 to 15 paired topics, which means 20 to 30 topics in all. Each needs the plank found, the votes found, and the link written and reviewed by hand. That's careful research work, not a quick build.
4. **The results are still informative.** Both topics show the same small groups of members repeatedly voting against their party's platform: Collins, Murkowski, Paul and McConnell on tariffs, and a bloc of Democratic senators on the minimum wage. That's exactly what a reader would want to see, as long as the reasons caveat sits right beside it.

## 5. Decisions (settled November 6, 2026)

Ren asked for whichever options gave the most and best data, and the recommended option was used on each: **A** the platform from the election before each vote; **B** procedural votes shown but not counted; **C** topics picked by the written rule (both platforms opposite, at least one direct roll call); **D** Vote Smart not used. The original questions are kept below for the record.

- **A. Which platform applies.** Use the platform from the election before each vote (proposed), or always each party's latest platform (simpler, but it judges 2021 votes against 2024 promises)?
- **B. Procedural votes.** Leave them out of the headline (proposed), or count them when they're the only vote on the topic, as with the minimum wage, with a label?
- **C. Starting topic list.** About 10 to 15 pairs, picked by a written rule (proposed: planks that both platforms address in opposite directions and that got at least one direct roll call in the matching Congresses), or a list you choose?
- **D. Vote Smart.** Skip it (proposed), or add Political Courage Test answers for the minority of members who gave them, labeled as their own answers?

## 6. Topic list (built)

Thirty-four topics: 1 from the Bush years, 14 from the Obama years, 11 from the Trump years and 8 from the Biden years. The data starts in 2007, so the Bush years cover only the 110th Congress, which is judged against the 2004 platforms. Rule 5 was applied as "include every topic that qualifies and publish the split" rather than dropping qualifying topics to make the counts even. Every plank is in `data/platform_topics.csv` and every roll call in `data/platform_votes.csv`; `scripts/validate_data.py` checks that each roll call exists, that each party's platform year follows rule 1, and that most of each party voted the way its listed platform vote says (a guard against a flipped Yea/Nay).

| Congress | Topic | Counted votes | Shown only |
|---|---|---|---|
| 110th | Federal funding for embryonic stem cell research | House 19 and 437, Senate 127 | |
| 111th | Repealing Don't Ask Don't Tell | House 1621, Senate 678 | Senate 676 (cloture) |
| 111th | Path to citizenship for Dreamers | House 1608 | Senate 675 (cloture) |
| 111th | Ending the 2001 and 2003 tax cuts for top earners | House 1587 | |
| 111th | The Mexico City policy on overseas abortion funding | Senate 19 | Senate 81 (related: a condition on UN Population Fund money) |
| 112th | Ending the 2001 and 2003 tax cuts for top earners | House 1488, Senate 418 and 419 | House 1487 (motion to recommit) |
| 113th | Deferred action for Dreamers (DACA) | House 1117 | |
| 113th | A permanent ban on federal funding for abortion | House 669 | |
| 113th | Repealing the Affordable Care Act | House 153 | |
| 113th | Banning assault weapons | Senate 101 and 103 | |
| 113th | Immigration reform with a path to citizenship | Senate 168 | |
| 113th | A nationwide ban on abortion after 20 weeks | House 250 | |
| 114th | Repealing the Affordable Care Act | House 57, 566, 707 and 753, Senate 329 | |
| 114th | A nationwide ban on abortion after 20 weeks | House 222 | Senate 268 (cloture) |
| 114th | Deferred action for Dreamers (DACA) | House 29 | House 28 (related: aimed at the 2014 programs) |
| 114th | A permanent ban on federal funding for abortion | House 44 | |
| 114th | Cutting federal funding for Planned Parenthood | House 503 | Senate 262 (cloture) |
| 115th | Repealing the Affordable Care Act | House 255, Senate 169 and 179 | Senate 168 (budget waiver) |
| 115th | A permanent ban on federal funding for abortion | House 64 | |
| 115th | Cutting federal funding for Planned Parenthood | House 98, Senate 101 | Senate 100 (motion to proceed) |
| 115th | A nationwide ban on abortion after 20 weeks | House 548 | Senate 350 (cloture) |
| 115th | Net neutrality rules for internet providers | Senate 422 | |
| 115th | Path to citizenship for Dreamers | | Senate 358 (cloture) |
| 115th | The 2017 tax law | House 636 and 698, Senate 303 and 323 | |
| 116th | $15 federal minimum wage | House 495 | |
| 116th | Path to citizenship for Dreamers | House 239 | |
| 116th | Statehood for Washington D.C. | House 821 | |
| 116th | A permanent ban on federal funding for abortion | | Senate 7 (cloture) |
| 117th | The PRO Act and right-to-work laws | House 69 | |
| 117th | A federal law protecting abortion access | House 294 and 807 | Senate 593 and 698 (cloture) |
| 117th | $15 federal minimum wage | | Senate 74 (budget waiver) |
| 117th | Path to citizenship for Dreamers | House 90 | |
| 117th | Banning assault weapons | House 857 | |
| 117th | Statehood for Washington D.C. | House 131 | |
| 117th | Barring family planning grants to clinics that refer for abortion (Title X) | | Senate 668 (motion to proceed) |
| 118th | A wall on the southern border | | House 208 (related: a broad border bill) |
| 118th | A permanent ban on federal funding for abortion | | House 299 (related: the Jackson amendment ending Pentagon payment of abortion travel costs) |
| 119th | Across-the-board tariffs | Senate 225 and 600 | Senate 160, 594, 598; House 425 (related) |
| 119th | Making the 2017 tax cuts permanent | House 144 and 189, Senate 372 | |

**Checked and left out** because only one platform takes a position: the 2009 Stupak amendment on abortion funding in the health care bill (the 2008 Republican platform addresses only international abortion funding), the 2007 minimum wage increase and the 2007 House vote on the Employee Free Choice Act (the 2004 Republican platform doesn't address them; the 2008 platforms do, but the bill got no floor vote in 2009 or 2010), the 2009 cap-and-trade bill (the 2008 Republican platform doesn't oppose it), the 2014 minimum wage, the 2013 Employment Non-Discrimination Act and the 2015 Keystone XL pipeline (only one 2012 platform addresses each), the 2013 background check amendment (the 2012 Republican platform doesn't mention background checks), the Respect for Marriage Act (2022; the 2020 Democratic platform doesn't mention marriage), expanded gun background checks (2019 and 2021; the Republican platform doesn't mention them), the Equality Act (the Republican platform doesn't name it), the 2019 votes to end the border wall emergency (the 2016 Democratic platform criticizes the wall only as Trump's idea, without its own position), the 2007 Senate votes on overseas abortion funding (the 2004 Democratic platform doesn't address it), the 2009 Senate vote to require 700 miles of border fencing (the 2008 Democratic platform doesn't take a position on a fence), the 2026 Senate votes on photo ID and proof of citizenship to vote (the 2024 Democratic platform doesn't address either), and the 2026 Senate votes on DACA renewals (the 2024 Republican platform doesn't mention DACA).

**How the wording was checked.** Most planks were read in the platform text on The American Presidency Project. Four were confirmed another way, and the data file says so for each: the 2004 Republican stem cell plank and the 2016 Republican call to repeal the Affordable Care Act (both quoted in news reports), and the 2020 Democratic planks on citizenship and the border wall (the Democratic Party's own copy of the platform). The 2020 Democratic section on D.C. statehood was confirmed from the platform's table of contents.

**Results** (counted votes, 2007 to 2026): 92 of 609 Democrats and 134 of 684 Republicans voted against their party's platform at least once. The single largest group is the 91 Republican votes for expanding stem cell research funding in 2007. On 16 topics the vote was on a measure the Democratic platform backs, on 16 a measure the Republican platform backs, and on 1 both, so the party totals are a description of these votes, not a ranking.

## Sources

- Platform texts: The American Presidency Project, [2004 Democratic](https://www.presidency.ucsb.edu/documents/2004-democratic-party-platform), [2004 Republican](https://www.presidency.ucsb.edu/documents/2004-republican-party-platform), [2008 Democratic](https://www.presidency.ucsb.edu/documents/2008-democratic-party-platform), [2008 Republican](https://www.presidency.ucsb.edu/documents/2008-republican-party-platform), [2012 Democratic](https://www.presidency.ucsb.edu/documents/2012-democratic-party-platform), [2012 Republican](https://www.presidency.ucsb.edu/documents/2012-republican-party-platform), [2016 Democratic](https://www.presidency.ucsb.edu/documents/2016-democratic-party-platform), [2016 Republican](https://www.presidency.ucsb.edu/documents/2016-republican-party-platform), [2020 Democratic](https://www.presidency.ucsb.edu/documents/2020-democratic-party-platform), [2024 Democratic](https://www.presidency.ucsb.edu/documents/2024-democratic-party-platform), [2024 Republican](https://www.presidency.ucsb.edu/documents/2024-republican-party-platform). Democratic Party's copy of the 2020 platform: [immigration section](https://democrats.org/?p=1010862). News quotes: 2016 Republican repeal plank, [Medical Economics](https://www.medicaleconomics.com/view/2016-gop-platform-calls-obamacare-repeal-reform-medicare); 2004 Republican stem cell plank, [Baptist Press](https://www.baptistpress.com/?p=104443).
- Platforms as first researched for the pilot: [2024 Republican platform trade section](https://ielp.worldtradelaw.net/2024/07/the-trade-section-of-the-gop-2024-platform/); [2024 Democratic platform tariff language, as excerpted](https://www.protectingtaxpayers.org/election/grading-the-2024-dnc-platform); [2016 Republican platform minimum wage language, as reported](https://www.kcur.org/2018-10-16/supporters-hope-minimum-wage-votes-will-push-democratic-turnout); [2020 Democratic platform $15 minimum wage](https://www.foxbusiness.com/politics/democrats-2020-agenda-biden-harris-working-people-ed-rensi). Before building, each link would cite the official platform PDF and page.
- Votes: Voteview roll-call records (this site's data), and for H.J.Res. 72, [KPMG summary of the House vote](https://kpmg.com/us/en/taxnewsflash/news/2026/02/tnf-house-passes-joint-resolution-to-terminate-tariffs-on-canada.html).
- Vote Smart: [2020 Political Courage Test results](https://www.blog.votesmart.org/post/76-of-congressional-candidates-flunk-courage-test); [1992 to 2012 response study](https://votesmart.org/blog-archive/2012/oct/29/candidates-flunk-20-year-study-of-political); [2024 response rate, as reported](https://www.coloradopolitics.com/2026/09/10/should-we-always-blame-voters-for-low-civic-participation-in-elections-guest-column/); [how Vote Smart fills in non-responders](https://justfacts.votesmart.org/candidate/political-courage-test/16553/darrell-issa); [API](https://votesmart.org/share/api).
