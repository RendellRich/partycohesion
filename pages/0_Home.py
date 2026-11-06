"""
PartyCohesion
-------------
Neutral, data-first view of U.S. Congressional voting patterns and party cohesion.
Built with Streamlit. Data primarily from Voteview (UCLA).
"""

import streamlit as st
import pandas as pd
from pathlib import Path



DATA_PATH = Path(__file__).parent.parent / "data" / "members_processed.csv"

@st.cache_data
def load_members():
    df = pd.read_csv(DATA_PATH)
    return df

def main():
    st.title("PartyCohesion")
    st.markdown("U.S. congressional voting patterns and party cohesion. Primary data, minimal spin.")

    try:
        df = load_members()
        current = df[df["congress"] == 119]
        house = current[current["chamber"] == "House"]
        senate = current[current["chamber"] == "Senate"]
        house_n = len(house)
        senate_n = len(senate)
    except Exception:
        house_n = "—"
        senate_n = "—"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Congress", value="119th")
    with col2:
        st.metric(label="House Members (scored)", value=house_n)
    with col3:
        st.metric(label="Senate Members (scored)", value=senate_n)
    with col4:
        st.metric(label="Data Source", value="Voteview")

    st.markdown("---")

    st.subheader("What this site shows")
    st.markdown("""
**PartyCohesion** presents transparent metrics derived from official congressional roll-call data 
(via Voteview / UCLA), covering the House and Senate from the 110th through the 119th Congress. The focus is on **how often members vote with the majority of their own party** 
and where they sit on the primary liberal–conservative dimension of voting behavior.

- **Overview** — Chamber-level and party-level patterns  
- **Member Explorer** — Look up any member’s party-unity rate, ideology score, and how they changed across Congresses  
- **Key Votes** — Party splits on funding bills, Cabinet confirmations and the biggest party breaks, with every member who broke ranks  
- **Methodology** — Exact definitions and data sources  
- **About** — Project purpose and neutrality statement  

Use the sidebar to navigate.
    """)

    st.markdown("---")
    st.caption("Data: Lewis, Poole, Rosenthal, Boche, Rudkin & Sonnet — Voteview: Congressional Roll-Call Votes Database. Coverage: Congresses 110–119.")
    st.caption("This is an independent educational project. It does not endorse any party or candidate.")

main()