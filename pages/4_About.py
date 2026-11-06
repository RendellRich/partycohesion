"""About PartyCohesion."""

import streamlit as st


st.title("About PartyCohesion")

st.markdown("""
**PartyCohesion** exists to put primary congressional voting data in front of the public with as little editorial framing as possible.

When someone is elected after campaigning on a set of values, the roll-call record is one of the clearest public measures of whether those values (or party loyalty) shaped their subsequent votes. This site surfaces that record in a neutral, inspectable form.
""")

st.header("Design Principles")
st.markdown("""
1. **Primary sources first.** Official roll-call data and research-grade scaling (Voteview, DW-NOMINATE) come before secondary interpretations.
2. **Minimal spin.** Charts and numbers come before commentary, and captions stay descriptive.
3. **Transparency.** Methodology, definitions, data sources and every vote behind a score are public.
4. **The same rules for everyone.** Every member of both parties is measured with the same votes and cutoffs. See "Keeping It Neutral" on the Methodology page.
5. **No scorecards that hide the data.** The site shows distributions and individual positions rather than opaque composite rankings.
""")

st.header("Current Scope")
st.markdown("""
- U.S. House and Senate, from the 110th Congress (2007) to the present, refreshed automatically twice a week
- **Position Flips:** whether a member's vote on the same kind of question (debt limit, government funding, disaster aid,
  war powers) changes when the White House changes parties, explained step by step on How We Measure Consistency
- Party unity rates computed from individual roll-call votes, plus DW-NOMINATE ideology scores and how they changed over time
- Each member's votes compared with the president's officially stated positions (2009 on)
- High-profile vote series (funding bills, Cabinet confirmations, biggest party breaks, major legislation) with every member who broke ranks
- Member profiles and side-by-side comparisons of any two members
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
