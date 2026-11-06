# Comparing votes with what members ran on: design and pilot

**Status:** proposal for review. Nothing here is on the site yet.
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
- **Democratic platform (2024):** calls a 10% across-the-board tariff on imports from every country reckless and estimates it would cost families about $1,500 a year. It supports targeted tariffs, for example on China. A vote to end across-the-board tariffs is consistent with it.

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

## 5. Decisions needed before building

- **A. Which platform applies.** Use the platform from the election before each vote (proposed), or always each party's latest platform (simpler, but it judges 2021 votes against 2024 promises)?
- **B. Procedural votes.** Leave them out of the headline (proposed), or count them when they're the only vote on the topic, as with the minimum wage, with a label?
- **C. Starting topic list.** About 10 to 15 pairs, picked by a written rule (proposed: planks that both platforms address in opposite directions and that got at least one direct roll call in the matching Congresses), or a list you choose?
- **D. Vote Smart.** Skip it (proposed), or add Political Courage Test answers for the minority of members who gave them, labeled as their own answers?

## Sources

- Platforms: [2024 Republican platform trade section](https://ielp.worldtradelaw.net/2024/07/the-trade-section-of-the-gop-2024-platform/); [2024 Democratic platform tariff language, as excerpted](https://www.protectingtaxpayers.org/election/grading-the-2024-dnc-platform); [2016 Republican platform minimum wage language, as reported](https://www.kcur.org/2018-10-16/supporters-hope-minimum-wage-votes-will-push-democratic-turnout); [2020 Democratic platform $15 minimum wage](https://www.foxbusiness.com/politics/democrats-2020-agenda-biden-harris-working-people-ed-rensi). Before building, each link would cite the official platform PDF and page.
- Votes: Voteview roll-call records (this site's data), and for H.J.Res. 72, [KPMG summary of the House vote](https://kpmg.com/us/en/taxnewsflash/news/2026/02/tnf-house-passes-joint-resolution-to-terminate-tariffs-on-canada.html).
- Vote Smart: [2020 Political Courage Test results](https://www.blog.votesmart.org/post/76-of-congressional-candidates-flunk-courage-test); [1992 to 2012 response study](https://votesmart.org/blog-archive/2012/oct/29/candidates-flunk-20-year-study-of-political); [2024 response rate, as reported](https://www.coloradopolitics.com/2026/09/10/should-we-always-blame-voters-for-low-civic-participation-in-elections-guest-column/); [how Vote Smart fills in non-responders](https://justfacts.votesmart.org/candidate/political-courage-test/16553/darrell-issa); [API](https://votesmart.org/share/api).
