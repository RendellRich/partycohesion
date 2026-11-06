"""
PartyCohesion
-------------
Neutral, data-first view of U.S. Congressional voting patterns and party cohesion.
Built with Streamlit. Data primarily from Voteview (UCLA).

This file is the entry point. It sets the page config once and defines the sidebar navigation.
"""

import streamlit as st

st.set_page_config(
    page_title="PartyCohesion",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("<style>footer {visibility: hidden;}</style>", unsafe_allow_html=True)

pages = [
    st.Page("pages/0_Home.py", title="Home", icon="🏠", default=True),
    st.Page("pages/1_Overview.py", title="Overview", icon="📊"),
    st.Page("pages/2_Member_Explorer.py", title="Member Explorer", icon="👤"),
    st.Page("pages/5_Key_Votes.py", title="Key Votes", icon="🗳️"),
    st.Page("pages/3_Methodology.py", title="Methodology", icon="📐"),
    st.Page("pages/4_About.py", title="About", icon="ℹ️"),
]

st.navigation(pages).run()
