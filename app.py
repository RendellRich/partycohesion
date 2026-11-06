"""
PartyCohesion
-------------
Neutral, data-first view of U.S. Congressional voting patterns and party cohesion.
Built with Streamlit. Data primarily from Voteview (UCLA).

This file is the entry point. It sets the page config once and defines the sidebar navigation.
"""

import streamlit as st

from module_refresh import drop_changed_local_modules

# A deploy that changed a helper module takes effect without a reboot. Cached data is cleared too, because the
# data-change check in chart_utils starts over when chart_utils is reloaded.
if drop_changed_local_modules():
    st.cache_data.clear()

from chart_utils import EXPORT_SIZES, DEFAULT_EXPORT, clear_cache_if_data_changed
from site_status import show_refresh_notice

st.set_page_config(
    page_title="PartyCohesion",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("<style>footer {visibility: hidden;}</style>", unsafe_allow_html=True)

# Page scripts live in views/, not pages/: Streamlit treats a pages/ folder as its older automatic navigation, and a
# visitor who opened a page link first after a restart got that plain page list and skipped this file entirely.
# Grouped as in the Figma design: findings first, then exploration tools, then how it works
pages = {
    "": [st.Page("views/0_Home.py", title="Home", icon="🏠", default=True)],
    "Findings": [
        st.Page("views/7_Position_Flips.py", title="Position Flips", icon="🔄"),
        st.Page("views/11_Platform_Votes.py", title="Platform Votes", icon="📜"),
        st.Page("views/5_Key_Votes.py", title="Key Votes", icon="🗳️"),
        st.Page("views/8_Ideology_Drift.py", title="Ideology Drift", icon="📈"),
    ],
    "Explore": [
        st.Page("views/10_All_Votes.py", title="All Votes", icon="🔎"),
        st.Page("views/2_Member_Explorer.py", title="Members", icon="👤"),
        st.Page("views/6_Compare.py", title="Compare Members", icon="⚖️"),
        st.Page("views/1_Overview.py", title="Overview", icon="📊"),
    ],
    "About": [
        st.Page("views/9_How_It_Works.py", title="How We Measure Consistency", icon="🧮"),
        st.Page("views/3_Methodology.py", title="Methodology", icon="📐"),
        st.Page("views/4_About.py", title="About", icon="ℹ️"),
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
