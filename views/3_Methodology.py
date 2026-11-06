"""Methodology and data sources."""

import streamlit as st


st.title("Methodology & Sources")
st.markdown("Transparent definitions so anyone can understand (and critique) the numbers.")
st.page_link("views/9_How_It_Works.py", label="New here? Start with How We Measure Consistency, a step-by-step example →")

st.header("Data Coverage")
st.markdown("""
- **Years:** the 110th Congress (2007) to the present. Votes before 2007 are not included, so a member who served
  earlier is scored only on votes from 2007 on, and their profile says the data starts in 2007.
- **Votes counted:** only Yea and Nay floor votes. Present, not voting, and paired or announced positions are left out.
- **Chambers:** House and Senate. Non-voting delegates appear in member lists but are left out of Ideology Drift.
""")

st.header("Primary Data Source")
st.markdown("""
All ideology scores and member biographical data shown on this site come from:

**Voteview: Congressional Roll-Call Votes Database**  
Lewis, Jeffrey B., Keith Poole, Howard Rosenthal, Adam Boche, Aaron Rudkin, and Luke Sonnet.  
https://voteview.com/

Voteview provides the research-standard DW-NOMINATE scores and the underlying roll-call matrix for the U.S. Congress from 1789 to the present. Data are updated as new votes occur.
""")

st.header("DW-NOMINATE Ideology Score (Dimension 1)")
st.markdown("""
DW-NOMINATE is a scaling procedure that places legislators in a low-dimensional space based solely on their recorded floor votes. 

- **Dimension 1** is the primary axis recovered from the data. For most of modern American history it corresponds closely to the familiar liberal–conservative (or left–right) economic and social spectrum.
- Negative scores are more liberal; positive scores are more conservative.
- The scale is relative and comparable across members within the same model estimation.

These scores are **not** opinions or survey responses. They are statistical summaries of actual voting behavior.
""")

st.header("Party Unity Rate")
st.markdown("""
The **party unity rate** is the classic measure of how often a member votes with their own party.

1. For every roll call in a Congress and chamber, count only actual Yea and Nay floor votes. Present, not voting, and "paired" or "announced" positions are excluded, which matches the official clerk totals.
2. Find the majority position of Democrats and of Republicans. Roll calls where a party splits exactly 50/50 are excluded.
3. A **party-unity vote** is a roll call where a majority of Democrats opposed a majority of Republicans.
4. A member's **party unity %** is the share of the party-unity votes they cast on which they sided with their own party's majority.

Scores are computed separately for each Congress and chamber, so a member's rate in one Congress never carries over to another.
Party majorities are set by Democrats and Republicans. Independents who caucus with a party (such as Sanders and King with the Democrats) are scored against that party's majority, using the caucus records in the public congress-legislators dataset. Independents who caucus with neither party have no unity rate.
""")

st.header("Party Cohesion Proxy")
st.markdown("""
A second, ideology-based measure shows who sits near the center of their party versus the wings:

1. Within each Congress + chamber + party, compute the median DW-NOMINATE Dimension 1 score.
2. Rank every member by absolute distance from that party median.
3. Convert the rank into a 0–100 score (100 = closest to the party median; lower scores = further toward the ideological wing).

A member can have a high party unity rate and still sit toward their party's wing. The two measures answer different questions.
""")

st.header("Key Vote Series")
st.markdown("""
The Key Votes page groups high-profile roll calls into series. Three series are chosen by a fixed rule:

- **Funding & Appropriations**: final passage votes (including votes to concur in the other chamber's changes) on appropriations bills and continuing resolutions. Procedural rule votes and authorization bills are excluded.
- **Cabinet Confirmations**: Senate confirmation votes for the heads of the 15 executive departments and the Attorney General. Nominees confirmed by voice vote have no roll call.
- **Biggest Party Breaks**: in each chamber, the 10 party-unity votes on final passage or nominations where the most Democrats and Republicans combined voted against their own party's majority.

A fourth series, **Major Legislation**, is chosen by hand from widely covered bills and listed in
`data/key_votes_custom.csv`, where anyone can see and question the picks. So far it covers only the 119th Congress.
It is labeled as hand-picked on the page.

For every vote, the page shows the Yea–Nay split for each party and lists each Democrat or Republican who voted against their party's majority. If a party splits exactly evenly, it has no majority position and none of its members are counted as breaking with it.
""")

st.header("All Votes and Member Voting Records")
st.markdown("""
The All Votes page lists every House and Senate roll call since 2007, refreshed twice a week. For each vote it shows
each party's Yea–Nay split and lists every Democrat and Republican who voted against their own party's majority (a
party that split exactly evenly has no majority). Searching by bill number, such as H.R. 1 or S. 5, finds every
roll call on that bill in both chambers; other searches match words in the bill's official title, and Senate records
often use the formal title rather than the short name.

Each member's profile has their full voting record. A vote is flagged **against their party** when they voted Yea or
Nay and their party's majority voted the other way. Independents are compared with the party they caucus with. This
counts every roll call where the party took a side, including lopsided and procedural votes, so it is a broader
count than the party unity rate, which uses only party-line votes.
""")

st.header("Comparing Two Members")
st.markdown("""
Compare Members uses every roll call where both members actually voted Yea or Nay while serving in the same chamber during the same Congress. "Voted the same way" is the share of those votes where their votes matched. The same figure is shown for party-unity votes only. Members who never served in the same chamber at the same time can be compared on party unity but not vote by vote.
""")

st.header("Position Flips")
st.markdown("""
Position Flips looks at five kinds of votes that come up under presidents of both parties. For each, one side gives *whichever president is in office* more room ("president-friendly"):

- **Debt limit:** Yea to raise or suspend the limit, or Nay on a resolution disapproving an increase. These votes are **listed by hand** in `data/flip_debt_limit_votes.csv`, because increases often rode on unrelated vehicle bills.
- **Stopgap funding:** Yea on a government-wide continuing resolution that passed the chamber. One-agency "mini" bills and rival versions that failed are excluded.
- **War powers limits:** Nay on a resolution directing the president to remove U.S. forces from hostilities.
- **Full-year funding:** Yea on the final vote for every law that gave full-year funding to two or more of the twelve
  regular appropriations bills at once (omnibus, minibus, consolidated or full-year continuing appropriations), fiscal
  year 2008 on. **Listed by hand** in `data/flip_funding_votes.csv`. Full-year continuing resolutions count here, not
  as stopgaps.
- **Disaster aid:** Yea on the final vote for every law containing a disaster relief supplemental of $10 billion or
  more, as listed by the Congressional Budget Office. **Listed by hand** in the same file.

The final vote is the last one in each chamber that approved the text that became law; when the House split a
package into two votes, both count. These two lists replaced keyword matching, which missed packages passed as
unrelated "vehicle" bills and caught bills that never became law.

A step-by-step example with a real member's votes is on the **How We Measure Consistency** page.

Each vote is matched to the president in office on its date, and to which party ran the member's chamber that
Congress (the party with more members, counting those who caucus with it; the evenly split 110th and 117th Senates
are set to the Democrats, who organized both). For every Democrat and Republican, the page compares how often they
cast the president-friendly vote when their own party held the White House versus when the other party did,
**like for like**:

1. Votes are grouped by **type of vote** and by **whether the member's party ran the chamber**.
2. Inside each group, the rate under the other party's president is subtracted from the rate under their own party's
   president. Groups with votes on only one side are set aside.
3. The **shift** is the weighted average of those differences, with weight = own × other ÷ (own + other) votes, so
   groups with more votes on both sides count more.

Members need at least 2 compared votes under each party's president to be labeled. The **simple difference** (every
vote, no grouping) is shown next to the shift. The grouping matters because the party running a chamber writes these
bills, and members of both parties back the president far more often when their own party also runs the chamber. The
bills in a category are not identical, so a changed vote can reflect a changed bill; every vote is listed on the page.
""")

st.header("The President's Stated Positions")
st.markdown("""
The White House's Office of Management and Budget issues **Statements of Administration Policy** giving the president's official position on bills before a floor vote. The site reads every statement from 2009 on (from the public archive maintained by the @unitedstates project) and records whether the president **supported** or **opposed** the bill, based on the statement's own wording ("The Administration strongly supports…", or a veto threat against the bill as written). Statements that take no clear position are not used.

Each statement is linked to final floor votes on the same bill, in the same chamber, within 30 days and before any newer statement on that bill. Position Flips uses these positions for every rule-selected vote where a statement exists (the hand-listed debt limit votes keep their listed direction).

**Why this isn't used to score every bill:** comparing how often a member agrees with presidents of different parties *across different bills* would mostly measure ideology, not consistency. A conservative who agrees with a Republican president's bills and disagrees with a Democratic president's bills hasn't changed position. Position Flips only compares the *same kind of question* asked under both parties' presidents.
""")

st.header("Ideology Drift")
st.markdown("""
Ideology Drift uses Voteview's Nokken-Poole scores, which estimate each member's position separately for each Congress. A member's movement is compared with their party's median movement over the same Congresses in the same chamber. Changes under 0.10 are treated as noise. Because the scores only see Yea and Nay, a member who votes No for the opposite reason from the other party can appear to move toward the center.
""")

st.header("Platform Votes")
st.markdown("""
Platform Votes compares members' votes with their **party's national platform**, the policy document each party
adopts at its convention every four years. Members don't write or sign it, so the page says a member "voted against
their party's platform", not that they broke a personal promise.

- **Which platform:** the one adopted in the presidential election year before the vote (2004 for 2007 to 2008, 2008
  for 2009 to 2012, 2012 for 2013 to 2016, 2016 for 2017 to 2020, 2020 for 2021 to 2024, 2024 for 2025 on). The
  Republican Party re-adopted its 2016 platform in 2020.
- **Which topics:** only actions both platforms address in opposite directions, such as a specific law or program,
  with at least one roll call on exactly that action. Topics only one platform mentions are left out.
- **Which votes count:** direct votes on the measure itself. Procedural votes and votes on broader, related measures
  are shown but not counted.
- **Independents** are compared with the platform of the party they caucus with.
- Every plank is a paraphrase with a link to the platform text. The full list is in `data/platform_topics.csv` and
  `data/platform_votes.csv`, and the rules are in `docs/platform-comparison-design.md`.
- Vote Smart's candidate questionnaire was considered and not used: most incumbents don't answer it, and it fills in
  answers for those who don't.
""")

st.header("Keeping It Neutral")
st.markdown("""
**Rules the site follows on every page**

- The same rules, cutoffs and votes apply to every member of both parties. Nothing is adjusted by party.
- Parties are listed alphabetically (Democrat, then Republican), and paired examples are listed alphabetically by last name.
- Party colors follow the usual convention (blue, red, gray). Position Flips patterns use shades of one neutral color,
  so no pattern reads as good or bad, and colors never carry meaning on their own.
- The worked examples on How We Measure Consistency are the two parties' Senate leaders during the years they led at
  the same time (McConnell and Schumer, 2017 to 2024), one from each party. Readers can switch to any member.
- Anything picked by hand (the debt limit, full-year funding and disaster aid lists, Major Legislation, and the
  Platform Votes topics) is
  labeled, and the full lists are public. The three Position Flips lists follow written rules that cover every
  president the same way.
- Pages describe what the votes show. They do not call any vote right or wrong.

**Known imbalances in the Position Flips data**

- Votes are not spread evenly across presidents. More fall under Obama and Trump, who served longer in the years
  covered, than under Bush or Biden, and war powers votes fall almost entirely under Trump. The current counts are
  listed on the Position Flips page.
- Members cast the president-friendly vote far more often when their own party runs the chamber, under presidents of
  both parties, and that effect is about as large as the president's. The shift compares like with like to account
  for this (see Position Flips above). The cost is that votes with no comparable match are set aside, so some members
  are scored on a small share of their votes; every score shows how many votes it rests on.
- Compared like with like, the two parties' scores are close. The remaining difference comes mostly from war powers
  votes, which fall almost entirely under one president, and in the Senate it runs the other way. An earlier version
  of the data, which was missing most Biden-era funding votes, showed a much larger gap, so treat any party-level
  summary as a description of the members, not a verdict on either party.

**Known imbalances in the Platform Votes data**

- The list has 33 topics: 1 from the Bush years (the data starts in 2007), 14 from the Obama years, 11 from the Trump
  years and 7 from the Biden years. Every topic that qualifies under the rules is included rather than dropping some
  to even out the count, and the page shows the split.
- On more topics the vote was on a measure the Democratic platform backs (18, against 13 for the Republican platform
  and 1 with both), partly because House Democrats brought many of their platform bills to the floor from 2007 to
  2010 and 2019 to 2022. The Platform Votes page shows the current split. The two parties' totals depend heavily on which
  topics qualify, so read them as a description of these votes, not a ranking.
""")

st.header("What This Site Does *Not* Do")
st.markdown("""
- It does not assign moral judgments (“good” or “bad” members).
- It does not claim to know a legislator’s motives or private beliefs.
- It does not use campaign statements, speeches, or media coverage as primary inputs.
- It does not rank members on a single “scorecard” that mixes unrelated issues.

The goal is descriptive: show the patterns that exist in the official voting record and let readers draw their own conclusions.
""")

st.header("Updates & Reproducibility")
st.markdown("""
- Member files and roll-call vote files are re-downloaded from Voteview twice a week by an automatic job (`scripts/refresh_data.py`), which recomputes every number shown here.
- Before new data is published, `scripts/validate_data.py` checks it (complete chambers, vote totals matching official counts, no sudden drops). If a check fails, nothing is published and a notice appears on the site until a refresh succeeds.
- Processed data used by the app live in the project repository.
- Every proposed change to the code runs an automated test suite first: the Position Flips math and cutoffs, the data
  files, and every page loading and responding to the main interactions. A change that fails the tests is not merged.
- Code and data processing steps are kept simple and inspectable so others can reproduce the numbers.
""")

st.markdown("---")
st.caption("PartyCohesion is an independent educational project. It has no affiliation with Voteview, UCLA, any political party, or any campaign.")
