"""
PartyCohesion
-------------
Neutral, data-first view of U.S. Congressional voting patterns and party cohesion.
Built with Streamlit. Data primarily from Voteview (UCLA).

This file is the entry point. It sets the page config once and defines the sidebar navigation.
"""

import streamlit as st
from chart_utils import EXPORT_SIZES, DEFAULT_EXPORT, clear_cache_if_data_changed
from site_status import show_refresh_notice

st.set_page_config(
    page_title="PartyCohesion",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("<style>footer {visibility: hidden;}</style>", unsafe_allow_html=True)

# Grouped as in the Figma design: findings first, then exploration tools, then how it works
pages = {
    "": [st.Page("pages/0_Home.py", title="Home", icon="🏠", default=True)],
    "Findings": [
        st.Page("pages/7_Position_Flips.py", title="Position Flips", icon="🔄"),
        st.Page("pages/5_Key_Votes.py", title="Key Votes", icon="🗳️"),
        st.Page("pages/8_Ideology_Drift.py", title="Ideology Drift", icon="📈"),
    ],
    "Explore": [
        st.Page("pages/10_All_Votes.py", title="All Votes", icon="🔎"),
        st.Page("pages/2_Member_Explorer.py", title="Members", icon="👤"),
        st.Page("pages/6_Compare.py", title="Compare Members", icon="⚖️"),
        st.Page("pages/1_Overview.py", title="Overview", icon="📊"),
    ],
    "About": [
        st.Page("pages/9_How_It_Works.py", title="How We Measure Consistency", icon="🧮"),
        st.Page("pages/3_Methodology.py", title="Methodology", icon="📐"),
        st.Page("pages/4_About.py", title="About", icon="ℹ️"),
    ],
}

nav = st.navigation(pages)

with st.sidebar:
    st.radio("Chart download size", list(EXPORT_SIZES), key="export_size",
             index=list(EXPORT_SIZES).index(DEFAULT_EXPORT))
    st.caption("Use the camera icon on any chart to download a PNG at this size.")

clear_cache_if_data_changed()  # new data from the twice-weekly refresh shows up without a restart
show_refresh_notice()
nav.run()
