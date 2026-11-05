"""
PartyCohesion
-------------
Neutral, data-first view of U.S. Congressional voting patterns and party cohesion.
Built with Streamlit. Data primarily from Voteview (UCLA).
"""

import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="PartyCohesion",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for a clean, neutral look
st.markdown("""
<style>
    .main-header {
        font-size: 2.4rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #4a4a4a;
        margin-bottom: 1.5rem;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #666;
    }
    .stMetric {
        background-color: #f8f9fa;
        padding: 10px 15px;
        border-radius: 8px;
    }
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

DATA_PATH = Path(__file__).parent / "data" / "members_processed.csv"

@st.cache_data
def load_members():
    df = pd.read_csv(DATA_PATH)
    return df

def main():
    st.markdown('<p class="main-header">PartyCohesion</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-header">U.S. Congressional voting patterns and party cohesion — primary data, minimal spin.</p>',
        unsafe_allow_html=True
    )

    df = load_members()

    # Quick stats for current (119th) Congress
    current = df[df["congress"] == 119]
    house = current[current["chamber"] == "House"]
    senate = current[current["chamber"] == "Senate"]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Congress", "119th")
    with col2:
        st.metric("House Members (scored)", len(house))
    with col3:
        st.metric("Senate Members (scored)", len(senate))
    with col4:
        st.metric("Data Source", "Voteview")

    st.markdown("---")

    st.subheader("What this site shows")
    st.markdown("""
    **PartyCohesion** presents transparent metrics derived from official congressional roll-call data 
    (via Voteview / UCLA). The focus is on **how often members vote with the majority of their own party** 
    and where they sit on the primary liberal–conservative dimension of voting behavior.

    - **Overview** — Chamber-level and party-level patterns  
    - **Member Explorer** — Look up any member’s ideology score and cohesion proxy  
    - **Methodology** — Exact definitions and data sources  
    - **About** — Project purpose and neutrality statement  

    Use the sidebar to navigate.
    """)

    st.markdown("---")
    st.caption("Data: Lewis, Poole, Rosenthal, Boche, Rudkin & Sonnet — Voteview: Congressional Roll-Call Votes Database. Last processed for display: recent Congresses 117–119.")
    st.caption("This is an independent educational project. It does not endorse any party or candidate.")

if __name__ == "__main__":
    main()
