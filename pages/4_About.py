"""About PartyCohesion."""

import streamlit as st


st.title("About PartyCohesion")

st.markdown("""
**PartyCohesion** exists to put primary congressional voting data in front of the public with as little editorial framing as possible.

When someone is elected after campaigning on a set of values, the roll-call record is one of the clearest public measures of whether those values (or party loyalty) shaped their subsequent votes. This site surfaces that record in a neutral, inspectable form.
""")

st.header("Design Principles")
st.markdown("""
1. **Primary sources first** — Prefer official roll-call data and research-grade scaling (Voteview / DW-NOMINATE) over secondary interpretations.
2. **Minimal spin** — Charts and numbers come before commentary. Captions stay descriptive.
3. **Transparency** — Methodology, definitions, and data provenance are public.
4. **No scorecards that hide the data** — We show distributions and individual positions rather than opaque composite rankings.
5. **Expandable** — The same approach can later incorporate campaign-promise tracking, state legislatures, or other domains where structured public data exists.
""")

st.header("Current Scope")
st.markdown("""
- U.S. House and Senate  
- The 110th Congress (2007) to the present  
- Party unity rates computed from individual roll-call votes, plus DW-NOMINATE ideology scores and a cohesion proxy  
- Interactive exploration of members and chamber-level patterns  
- High-profile vote series (funding bills, Cabinet confirmations, biggest party breaks) with every member who broke ranks
""")

st.header("Independence")
st.markdown("""
PartyCohesion is a solo educational project. It is not funded by, affiliated with, or endorsed by any political party, candidate, PAC, or advocacy organization. The only agenda is clearer access to the voting record.
""")

st.header("Contact & Feedback")
st.markdown("""
Questions, corrections, or suggestions about the data or methodology are welcome.  
Because the underlying numbers come from Voteview, the most authoritative place for technical questions about DW-NOMINATE remains the Voteview project itself.
""")

st.markdown("---")
st.caption("Built with Streamlit · Data from Voteview · Independent project")
