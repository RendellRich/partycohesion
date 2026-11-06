"""Methodology and data sources."""

import streamlit as st


st.title("Methodology & Sources")
st.markdown("Transparent definitions so anyone can understand (and critique) the numbers.")

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
Only Democrats and Republicans are scored. Independents (including those who caucus with a party) are shown without a unity rate.
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
The Key Votes page groups high-profile roll calls into series. Each series is chosen by a fixed rule, not by hand:

- **Funding & Appropriations**: final passage votes (including votes to concur in the other chamber's changes) on appropriations bills and continuing resolutions. Procedural rule votes and authorization bills are excluded.
- **Cabinet Confirmations**: Senate confirmation votes for the heads of the 15 executive departments and the Attorney General. Nominees confirmed by voice vote have no roll call.
- **Biggest Party Breaks**: in each chamber, the 10 party-unity votes on final passage or nominations where the most Democrats and Republicans combined voted against their own party's majority.

Additional series can be added by listing roll calls in `data/key_votes_custom.csv`. Any such series is labeled as hand-picked.

For every vote, the page shows the Yea–Nay split for each party and lists each Democrat or Republican who voted against their party's majority. If a party splits exactly evenly, it has no majority position and none of its members are counted as breaking with it.
""")

st.header("Comparing Two Members")
st.markdown("""
Compare Members uses every roll call where both members actually voted Yea or Nay while serving in the same chamber during the same Congress. "Voted the same way" is the share of those votes where their votes matched. The same figure is shown for party-unity votes only. Members who never served in the same chamber at the same time can be compared on party unity but not vote by vote.
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
- Code and data processing steps are kept simple and inspectable so others can reproduce the numbers.
""")

st.markdown("---")
st.caption("PartyCohesion is an independent educational project. It has no affiliation with Voteview, UCLA, any political party, or any campaign.")
