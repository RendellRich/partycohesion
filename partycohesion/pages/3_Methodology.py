"""Methodology and data sources."""

import streamlit as st

st.set_page_config(page_title="Methodology | PartyCohesion", page_icon="📐", layout="wide")

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

st.header("Party Cohesion Proxy (Current Version)")
st.markdown("""
True **party unity scores** measure the percentage of times a member votes with the majority of their own party on party-unity votes (votes where a majority of Democrats opposed a majority of Republicans).

For this release we display a transparent **proxy**:

1. Within each Congress + chamber + party, compute the median DW-NOMINATE Dimension 1 score.
2. Rank every member by absolute distance from that party median.
3. Convert the rank into a 0–100 score (100 = closest to the party median; lower scores = further toward the ideological wing).

This shows who sits near the center of their party’s voting coalition versus the wings. It is **not** identical to classic party-unity percentages (% of votes with the party majority on party-unity votes).

**Next data upgrade**: Incorporate full roll-call vote files from Voteview to compute official party-unity percentages (the classic “votes with party majority” metric). That work is straightforward once the vote matrices are processed and will replace or supplement the current proxy.
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
- Member ideology files are re-downloaded periodically from Voteview.
- Processed data used by the app live in the project repository.
- Code and data processing steps are kept simple and inspectable so others can reproduce the numbers.
""")

st.markdown("---")
st.caption("PartyCohesion is an independent educational project. It has no affiliation with Voteview, UCLA, any political party, or any campaign.")
