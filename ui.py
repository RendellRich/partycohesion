"""Shared page building blocks that mirror the PartyCohesion Figma design system: cards, metric cards,
party tags, pattern badges and name/place formatting. Every helper escapes its text."""

import re
from html import escape

import pandas as pd
import streamlit as st

from chart_utils import PATTERN_COLORS
from theme import text_on, to_mode, tokens

PARTY_VARS = {"Democrat": "var(--pc-dem)", "Republican": "var(--pc-rep)", "Independent": "var(--pc-ind)"}
VOTE_VARS = {"Yea": "var(--pc-yea)", "Nay": "var(--pc-nay)"}

STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia", "PR": "Puerto Rico", "GU": "Guam",
    "VI": "U.S. Virgin Islands", "AS": "American Samoa", "MP": "Northern Mariana Islands", "USA": "United States",
}

# Type: Public Sans (the U.S. Web Design System's typeface, made for government data) for everything, and
# Source Serif 4 for the big questions and page titles, so headings read like the public record they come from.
FONTS = ("https://fonts.googleapis.com/css2?family=Public+Sans:ital,wght@0,400;0,600;0,700;1,400"
         "&family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&display=swap")
SERIF = "'Source Serif 4', Georgia, serif"
SANS = "'Public Sans', 'Segoe UI', system-ui, sans-serif"

# After editing CSS, run python scripts/build_css.py: it copies these styles to static/pc.css, which loads in the
# page head so the site is styled from the first paint (tests/test_css_file.py checks the copy is current).
CSS = f"""
<style>
@import url('{FONTS}');
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button,
.stApp [data-testid="stMarkdownContainer"] {{ font-family: {SANS}; }}
.stApp h1 {{ font-family: {SERIF}; font-weight: 700; letter-spacing: -0.01em; }}
.stApp h2, .stApp h3 {{ font-family: {SANS}; font-weight: 700; }}
.stApp [data-testid="stMetricValue"], .pc-stat, .pc-metric-value {{ font-variant-numeric: tabular-nums; }}
.stApp a:focus-visible, .stApp button:focus-visible {{ outline: 2px solid var(--pc-accent); outline-offset: 2px; }}
/* Streamlit's "Skip to main content" link (the first Tab stop): 44px tall and in the site's colors. It moves focus to
   the main area, which then shows a ring so keyboard users can see where they landed. */
.stApp [data-testid="stSkipToContent"]:focus {{ min-height: 44px; display: inline-flex; align-items: center;
    padding: 0 16px; background: var(--pc-surface); color: var(--pc-accent); border: 1px solid var(--pc-border);
    border-radius: 6px; font-weight: 600; outline: 2px solid var(--pc-accent); outline-offset: 2px; }}
.stApp [data-testid="stMain"]:focus-visible {{ outline: 2px solid var(--pc-accent); outline-offset: -4px; }}
/* Expander headers: 44px to tap, and the same solid focus ring as links (Streamlit's own is a faint glow) */
.stApp [data-testid="stExpander"] summary {{ min-height: 44px; display: flex; align-items: center; }}
.stApp [data-testid="stExpander"] summary:focus-visible, .stApp a:focus-visible {{ outline: 2px solid var(--pc-accent);
    outline-offset: 2px; box-shadow: none !important; }}
.stApp [data-testid="stMain"] [data-testid="stPageLink-NavLink"] p {{ color: var(--pc-accent); font-weight: 600; }}
.stApp [data-testid="stMain"] [data-testid="stPageLink-NavLink"]:hover p {{ text-decoration: underline; }}
.pc-hero {{ font-family: {SERIF}; font-size: 2.6rem; font-weight: 700; line-height: 1.15; max-width: 22ch;
            margin: 0.5rem 0 1rem 0; letter-spacing: -0.01em; }}
.pc-intro {{ color: var(--pc-muted); font-size: 1rem; line-height: 1.6; max-width: 72ch; margin-bottom: 1.25rem; }}
.pc-card {{ background: var(--pc-surface); border: 1px solid var(--pc-border); border-radius: 10px; padding: 20px; height: 100%; }}
.pc-eyebrow {{ color: var(--pc-accent); font-size: 0.9rem; font-weight: 600; }}
.pc-stat {{ font-size: 2.4rem; font-weight: 700; line-height: 1.2; margin: 6px 0 8px 0; }}
.pc-body {{ color: var(--pc-muted); font-size: 1rem; line-height: 1.5; }}
.pc-metric {{ background: var(--pc-surface); border: 1px solid var(--pc-border); border-radius: 10px; padding: 14px 16px; height: 100%; }}
.pc-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin: 4px 0 16px 0; }}
/* Five cards sit three over two on wide screens, instead of four and one left alone */
@media (min-width: 641px) {{
  .pc-grid.pc-grid-5 {{ grid-template-columns: repeat(6, minmax(0, 1fr)); }}
  .pc-grid-5 > * {{ grid-column: span 2; }}
  .pc-grid-5 > :nth-child(n+4) {{ grid-column: span 3; }}
  .pc-table .pc-badge, .pc-nowrap {{ white-space: nowrap; }}
}}
.pc-metric-label {{ color: var(--pc-muted); font-size: 0.85rem; font-weight: 600; }}
.pc-metric-value {{ font-size: 2rem; font-weight: 700; line-height: 1.25; margin: 4px 0; }}
.pc-metric-value.pc-long {{ font-size: 1.35rem; padding: 6px 0 5px 0; }}
.pc-metric-note {{ color: var(--pc-muted); font-size: 0.85rem; }}
.pc-name {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; font-size: 1.5rem; font-weight: 600; }}
.pc-place {{ color: var(--pc-muted); font-size: 1rem; margin: 4px 0 12px 0; }}
.pc-state-head {{ display: flex; align-items: center; gap: 1rem; margin: 0 0 1rem; }}
.pc-state-head svg {{ flex-shrink: 0; width: auto; height: auto; max-width: 96px; max-height: 80px; }}
.pc-tag {{ display: inline-flex; align-items: center; gap: 6px; font-size: 0.85rem; font-weight: 600; }}
.pc-dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
.pc-badge {{ display: inline-block; padding: 2px 10px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; }}
.pc-table {{ width: 100%; border-collapse: separate; border-spacing: 0; background: var(--pc-surface);
             border: 1px solid var(--pc-border); border-radius: 10px; overflow: hidden; margin-bottom: 0.5rem; }}
.pc-table th {{ color: var(--pc-muted); font-size: 0.85rem; font-weight: 600; text-align: left; padding: 12px 16px; }}
.pc-table td {{ padding: 12px 16px; border-top: 1px solid var(--pc-border); }}
.pc-muted, .pc-table td.pc-muted {{ color: var(--pc-muted); }}
/* The share link box wraps instead of scrolling sideways: a scrolling box needs keyboard focus to read, and Streamlit
   doesn't give it one (axe: scrollable-region-focusable) */
.stApp [data-testid="stCode"] pre, .stApp [data-testid="stCode"] code {{ white-space: pre-wrap !important;
  overflow-wrap: anywhere; }}
.stApp [data-testid="stCode"] pre {{ overflow: visible !important; }}
/* Expanders: the control gray outline (3:1 or better) instead of the faint divider color, on the 10px card corner */
.stApp [data-testid="stExpander"] details {{ border-color: var(--pc-control); border-radius: 10px; }}
.stApp [data-testid="stExpander"] summary {{ border-radius: 10px; }}
.pc-notice {{ color: var(--pc-body); padding: 0;
             margin: 0.25rem 0 1rem; max-width: 72ch; }}
/* How they voted lately: a short list with the vote word in a chip. Yea is filled, Nay is outlined, a missed vote is
   dashed, so the mark reads without color as well as with it. */
.pc-lately {{ list-style: none; margin: 0 0 0.5rem; padding: 0; background: var(--pc-surface);
             border: 1px solid var(--pc-border); border-radius: 10px; }}
.pc-lately li {{ display: flex; gap: 12px; align-items: flex-start; padding: 12px 16px; margin: 0;
                border-top: 1px solid var(--pc-border); }}
.pc-lately li:first-child {{ border-top: 0; }}
.pc-vote {{ flex: 0 0 5.5rem; box-sizing: border-box; text-align: center; font-size: 0.85rem; font-weight: 700;
           line-height: 1.3; padding: 3px 6px; border-radius: 6px; border: 2px solid var(--pc-nay); color: var(--pc-text); }}
.pc-vote-yea {{ background: var(--pc-yea); border-color: var(--pc-yea); color: var(--pc-bg); }}
.pc-vote-other {{ border-style: dashed; border-color: var(--pc-control); color: var(--pc-muted); font-weight: 600; }}
.pc-lately-title {{ margin: 0; color: var(--pc-text); font-weight: 600; line-height: 1.4; overflow-wrap: anywhere; }}
.pc-lately-title a {{ color: var(--pc-text); text-decoration: underline; text-decoration-color: var(--pc-control);
                      text-underline-offset: 3px; }}
.pc-lately-title a:hover {{ text-decoration-color: var(--pc-accent); }}
.pc-status {{ color: var(--pc-body); margin: -4px 0 4px 0; }}
.pc-lately-meta {{ margin: 2px 0 0; font-size: 0.9rem; color: var(--pc-muted); }}
@media (max-width: 480px) {{
  .pc-lately li {{ flex-direction: column; gap: 6px; }}
  .pc-vote {{ flex: none; min-width: 4.5rem; }}
}}
.pc-table-wrap {{ overflow-x: auto; border-radius: 10px; margin-bottom: 0.5rem; }}
.pc-table-wrap .pc-table {{ margin-bottom: 0; }}
.pc-table-wrap:focus-visible {{ outline: 2px solid var(--pc-accent); outline-offset: 2px; }}
.pc-table th, .pc-table td {{ overflow-wrap: normal; word-break: normal; }}
@media (max-width: 640px) {{ .pc-table th, .pc-table td {{ padding: 10px 12px; }} }}
.pc-bars {{ display: grid; grid-template-columns: 130px minmax(120px, 1fr) 140px; gap: 10px 12px; align-items: center; margin: 14px 0 8px 0; }}
@media (max-width: 640px) {{ .pc-bars {{ grid-template-columns: auto minmax(0, 1fr); gap: 4px 12px; }}
                             .pc-bars > div:nth-child(3n) {{ grid-column: 1 / -1; margin-bottom: 8px; }} }}
.pc-bar {{ display: flex; gap: 2px; height: 22px; }}
.pc-bar span {{ display: block; height: 100%; border-radius: 6px; }}
.pc-chips {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
.pc-explain {{ border: 1px solid var(--pc-border); background: var(--pc-surface); border-radius: 10px; padding: 12px 16px;
               max-width: 72ch; color: var(--pc-body); font-size: 1rem; line-height: 1.55; margin: 0 0 18px 0; }}
.pc-explain-title {{ color: var(--pc-accent); font-weight: 600; font-size: 0.9rem; margin-bottom: 4px; }}
.pc-share, .pc-jumps {{ display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 8px 0 4px 0; }}
.pc-share span, .pc-jumps span {{ color: var(--pc-muted); font-size: 0.9rem; margin-right: 4px; }}
.pc-share a, .pc-jumps a {{ border: 1px solid var(--pc-control); border-radius: 999px; padding: 4px 12px; font-size: 0.9rem; font-weight: 600;
              color: var(--pc-text) !important; text-decoration: none; }}
.pc-share a:hover, .pc-jumps a:hover {{ border-color: var(--pc-accent); }}
.pc-person {{ margin: 6px 0 14px 0; }}
.pc-who {{ display: flex; align-items: center; gap: 14px; margin: 4px 0 12px 0; }}
.pc-who img {{ flex: none; width: 72px; border-radius: 6px; border: 1px solid var(--pc-border); }}
.pc-who .pc-place {{ margin: 0; }}
.pc-facts {{ color: var(--pc-muted); font-size: 1rem; line-height: 1.7; }}
.pc-facts b {{ color: var(--pc-text); font-weight: 600; }}
.pc-facts a {{ color: var(--pc-accent); }}
@media (max-width: 640px) {{ .pc-who img {{ width: 56px; }} .pc-hero {{ font-size: 2rem; }}
  /* Number cards two to a row on phones (one per row ran about 700px), an odd last card across both */
  .pc-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
  .pc-grid > :last-child:nth-child(odd) {{ grid-column: span 2; }}
  .pc-grid .pc-metric {{ padding: 12px; }}
  .pc-metric-value {{ font-size: 1.5rem; }}
  .pc-metric-value.pc-long, .pc-metric-value.pc-word {{ font-size: 1rem; padding: 4px 0; }}
}}
.pc-chip {{ border: 1px solid var(--pc-border); border-radius: 999px; padding: 3px 10px; font-size: 0.85rem; font-weight: 600; }}
/* Color beyond the data. The aisle stripe across the top of every page is the site's mark: party blue, a gap
   for the aisle, party red. */
.stApp::before {{ content: ""; position: fixed; top: 0; left: 0; right: 0; height: 5px; z-index: 1000000;
                  background: linear-gradient(90deg, var(--pc-dem) 0 49.2%, transparent 49.2% 50.8%, var(--pc-rep) 50.8% 100%); }}
.stApp h2, .stApp h3 {{ color: var(--pc-head); }}
.stApp h1::after {{ content: ""; display: block; width: 64px; height: 5px; margin-top: 12px; border-radius: 999px;
                    background: linear-gradient(90deg, var(--pc-dem) 0 45%, transparent 45% 55%, var(--pc-rep) 55% 100%); }}
.stApp [data-testid="stSidebar"] {{ background: color-mix(in srgb, var(--pc-hero) 7%, var(--pc-bg)); }}
.pc-panel {{ background: var(--pc-hero); color: var(--pc-hero-text); border-radius: 16px; padding: 34px 36px 0 36px;
             margin: 0.5rem 0 1.5rem 0; overflow: hidden; }}
.pc-panel .pc-hero {{ color: var(--pc-hero-text); margin-top: 0; }}
.pc-panel .pc-intro {{ color: color-mix(in srgb, var(--pc-hero-text) 82%, var(--pc-hero)); margin-bottom: 26px; }}
.pc-aisle {{ display: grid; grid-template-columns: 1fr 22px 1fr; height: 10px; margin: 0 -36px; }}
.pc-aisle span:first-child {{ background: var(--pc-dem); }}
.pc-aisle span:last-child {{ background: var(--pc-rep); }}
.pc-tone1 {{ --pc-tone: var(--pc-tone1); }}
.pc-tone2 {{ --pc-tone: var(--pc-tone2); }}
.pc-tone3 {{ --pc-tone: var(--pc-tone3); }}
.pc-card {{ border-top: 4px solid var(--pc-tone, var(--pc-accent));
            background: color-mix(in srgb, var(--pc-tone, var(--pc-accent)) 7%, var(--pc-surface)); }}
.pc-card .pc-eyebrow {{ color: var(--pc-tone, var(--pc-accent)); }}
.pc-explain {{ background: color-mix(in srgb, var(--pc-tone3) 8%, var(--pc-surface)); }}
.pc-explain-title {{ color: var(--pc-tone3); }}
@media (max-width: 640px) {{ .pc-panel {{ padding: 24px 20px 0 20px; }} .pc-aisle {{ margin: 0 -20px; }} }}
/* Headings: h2 is the section level under each page title, sized as sections were before */
.stApp [data-testid="stMain"] h2 {{ font-size: 1.75rem; }}
.stApp [data-testid="stMain"] h3 {{ font-size: 1.5rem; }}
/* Heading link icons are 16px targets and extra tab stops; every page has its own share link instead */
.stApp a[aria-label="Link to heading"] {{ display: none; }}
/* A collapsed sidebar sits off screen; hide it so keyboard focus skips its links until it is opened */
.stApp [data-testid="stSidebar"][data-collapsed="true"] {{ visibility: hidden; }}
/* Captions use the muted token so they pass 4.5:1 in both themes */
/* Streamlit also fades captions to 60% opacity; with the muted color that stacks to under 3:1, so drop the fade */
.stApp [data-testid="stCaptionContainer"] {{ opacity: 1; }}
.stApp [data-testid="stCaptionContainer"], .stApp [data-testid="stCaptionContainer"] p {{ color: var(--pc-muted); }}
/* Everything people tap is at least 44px */
.stApp [data-testid="stPageLink-NavLink"], .stApp [data-testid="stSidebarNavLink"] {{ min-height: 44px; display: flex; align-items: center; }}
.stApp [data-testid="stButtonGroup"] button, .stApp [data-testid^="stBaseButton"] {{ min-height: 44px; }}
/* Unselected pills and secondary buttons sit on the page color, so their outline is the only thing showing their
   shape: the control gray (3:1 or better in both themes) instead of the faint divider color */
.stApp button[data-variant="pills"]:not([data-selected="true"]),
.stApp [data-testid="stBaseButton-secondary"] {{ border-color: var(--pc-control); }}
.stApp button[data-variant="segmented_control"]:not([data-selected="true"]) {{
  border-top-color: var(--pc-control); border-bottom-color: var(--pc-control); border-left-color: var(--pc-control); }}
.stApp button[data-variant="segmented_control"]:last-child:not([data-selected="true"]) {{ border-right-color: var(--pc-control); }}
.stApp .react-aria-ComboBox [role="group"], .stApp [data-testid="stTextInputRootElement"] {{ min-height: 46px; }}
.stApp [data-testid="stTextInputRootElement"] input {{ min-height: 44px; height: 44px; }}
.stApp label:has(input[type="checkbox"]), .stApp label:has(input[type="radio"]) {{ min-height: 44px; align-items: center; }}
.stApp .react-aria-ComboBox [role="group"] button {{ min-width: 44px; }}
.stApp [data-testid="stExpandSidebarButton"], .stApp [data-testid="stMainMenuButton"],
.stApp [data-testid="stToolbarActionButton"] button {{ min-width: 44px; min-height: 44px; }}
.stApp [data-testid="stTooltipHoverTarget"] button {{ min-width: 44px; min-height: 44px; margin: -14px; }}
.pc-share a, .pc-jumps a {{ display: inline-flex; align-items: center; min-height: 44px; padding: 0 16px; }}
.pc-table td a {{ display: inline-block; padding: 12px 0; margin: -12px 0; }}
.pc-link-target {{ display: inline-flex; align-items: center; min-height: 44px; }}
/* Field outlines at 3:1, and a clear focus ring on fields and chart buttons */
.stApp .react-aria-ComboBox [role="group"], .stApp [data-testid="stTextInputRootElement"] {{ border-color: var(--pc-control) !important; }}
.stApp .react-aria-ComboBox [role="group"]:focus-within, .stApp [data-testid="stTextInputRootElement"]:focus-within {{
    outline: 2px solid var(--pc-accent); outline-offset: 2px; }}
.stApp .modebar-btn:focus-visible {{ outline: 2px solid var(--pc-accent) !important; outline-offset: 2px; }}
.stApp label:has(input[type="checkbox"]:focus-visible), .stApp label:has(input[type="radio"]:focus-visible) {{
    outline: 2px solid var(--pc-accent); outline-offset: 2px; border-radius: 6px; }}
/* Toggle and checkbox boxes: a 3:1 outline so the off state is visible */
.stApp label:has(input[type="checkbox"]) > div:first-of-type {{ box-shadow: inset 0 0 0 1px var(--pc-control); }}
/* The Home question is an h1 but keeps the hero look, without the rule other titles get */
.stApp h1.pc-hero {{ padding: 0; margin: 0 0 0.75rem 0; }}
.stApp h1.pc-hero::after {{ content: none; }}
/* Visually hidden headings for screen readers */
.pc-sr-only {{ position: absolute !important; width: 1px; height: 1px; padding: 0 !important; margin: -1px;
              overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }}
/* Shortcuts under each page's intro */
.pc-shortcuts {{ display: flex; flex-wrap: wrap; align-items: center; gap: 0 10px; margin: -0.75rem 0 1rem 0;
                font-weight: 600; }}
.pc-shortcuts a {{ color: var(--pc-accent); text-decoration: none; }}
.pc-shortcuts a:hover {{ text-decoration: underline; }}
.pc-shortcuts span {{ color: var(--pc-muted); }}
.pc-shortcuts-solo {{ margin: -0.5rem 0 0.5rem 0; }}
/* Sidebar "View more" is a 44px target */
.stApp [data-testid="stSidebarNavViewButton"] {{ min-height: 44px; }}
/* Toggle labels and page links wrap instead of being cut off */
.stApp label:has(input[type="checkbox"]) [data-testid="stWidgetLabel"],
.stApp label:has(input[type="checkbox"]) [data-testid="stWidgetLabel"] *:not(button),
.stApp [data-testid="stPageLink-NavLink"] span, .stApp [data-testid="stPageLink-NavLink"] span * {{
    white-space: normal !important; overflow: visible !important; text-overflow: clip !important; min-width: 0; }}
.stApp label:has(input[type="checkbox"]) {{ min-width: 0; }}
/* Phones: the chart download size setting is for desktop downloads */
@media (max-width: 640px) {{ .stApp .st-key-pc_export {{ display: none; }} }}
/* Phones: stacked tables show each row as a small card */
@media (max-width: 640px) {{
  .pc-table-stack thead {{ display: none; }}
  .pc-table-stack, .pc-table-stack tbody, .pc-table-stack tr {{ display: block; width: 100%; }}
  .pc-table-stack tr {{ padding: 12px 16px; border-top: 1px solid var(--pc-border); }}
  .pc-table-stack tr:first-child {{ border-top: none; }}
  .pc-table-stack td {{ display: flex; justify-content: space-between; align-items: baseline; gap: 12px;
                        padding: 4px 0; border: none; text-align: right; }}
  .pc-table-stack td::before {{ content: attr(data-label); color: var(--pc-muted); font-size: 0.85rem; font-weight: 600;
                                text-align: left; flex-shrink: 0; }}
  .pc-table-stack td:first-child {{ display: block; text-align: left; font-weight: 700; font-size: 1rem; padding-bottom: 6px; }}
  .pc-table-stack td:first-child::before {{ content: none; }}
  .pc-table-stack td {{ flex-wrap: wrap; }}
  .pc-table-stack td > .pc-badge {{ white-space: nowrap; margin-left: auto; }}
  .pc-table-stack td.pc-td-wide {{ display: block; text-align: left; }}
  .pc-table-stack td.pc-td-wide::before {{ display: block; }}
}}
/* Phones: 16px fields so iPhones don't zoom in on tap */
@media (max-width: 767px) {{ .stApp input, .stApp textarea, .stApp select {{ font-size: 16px !important; }} }}
/* Touch screens: no chart toolbar (its 24px buttons only appear on mouse hover). Phones: less space above the title */
@media (hover: none), (max-width: 640px) {{ .stApp .modebar-container {{ display: none !important; }} }}
@media (max-width: 640px) {{ .stApp [data-testid="stMainBlockContainer"] {{ padding-top: 4rem; }} }}
/* Elements with nothing to show (the style blocks and the theme listener) still took a 16px gap each, which pushed
   every page down about 64px. Their styles still apply while hidden. */
.stApp [data-testid="stElementContainer"]:has([data-testid="stMarkdownContainer"] > style):not(:has([data-testid="stMarkdownContainer"] > :not(style))),
.stApp .st-key-pc_theme {{ display: none; }}
/* Phones: a smaller opening so the ZIP and name lookups are on the first screen */
@media (max-width: 640px) {{
  .pc-panel {{ padding: 22px 20px 0 20px; border-radius: 10px; }}
  .stApp h1.pc-hero {{ font-size: 1.75rem; line-height: 1.2; }}
  .pc-panel .pc-intro {{ font-size: 1rem; line-height: 1.5; margin-bottom: 18px; }}
}}
</style>
"""


def inject_css() -> None:
    """Site styles plus the color variables for the visitor's light or dark theme."""
    t = tokens()
    names = {"bg": "bg", "surface": "surface", "border": "border", "text": "text", "body": "body", "muted": "muted",
             "accent": "accent", "dem": "dem", "rep": "rep", "ind": "ind", "yea": "yea", "nay": "nay",
             "hero": "hero", "hero_text": "hero-text", "head": "head", "tone1": "tone1", "tone2": "tone2",
             "tone3": "tone3", "control": "control"}
    global _card_count
    _card_count = 0
    root = "".join(f"--pc-{css}: {t[key]}; " for key, css in names.items())
    st.markdown(f"<style>:root {{ {root}}}</style>" + CSS, unsafe_allow_html=True)


def intro(text: str, shortcuts: bool = True) -> None:
    """A page's opening line. shortcuts adds links to the two pages most visitors come for (Members and States),
    which otherwise sit low in the sidebar on phones; the Members and States pages leave them off."""
    links = SHORTCUTS_HTML.format(extra="") if shortcuts else ""
    st.markdown(f'<div class="pc-intro">{escape(text)}</div>{links}', unsafe_allow_html=True)


SHORTCUTS_HTML = ('<div class="pc-shortcuts{extra}"><a class="pc-link-target" href="Member_Explorer" target="_self">'
                  'Find your member</a><span aria-hidden="true">·</span>'
                  '<a class="pc-link-target" href="States" target="_self">Your state</a></div>')


def shortcuts() -> None:
    """The Find your member and Your state links, for pages that write their own intro instead of using intro()."""
    st.markdown(SHORTCUTS_HTML.format(extra=" pc-shortcuts-solo"), unsafe_allow_html=True)


def section_heading(text: str) -> None:
    """A section heading for screen readers where the section already has a visible chart title or card row."""
    st.markdown(f'<h2 class="pc-sr-only">{escape(text)}</h2>', unsafe_allow_html=True)


def hero_panel(question: str, intro_text: str) -> None:
    """The home page's opening: the question on navy, with the aisle stripe along the bottom."""
    st.markdown(f'<div class="pc-panel"><h1 class="pc-hero">{escape(question)}</h1>'
                f'<div class="pc-intro">{escape(intro_text)}</div>'
                '<div class="pc-aisle"><span></span><span></span><span></span></div></div>', unsafe_allow_html=True)


def explainer(text: str) -> None:
    """A short plain-language note for first-time visitors, shown under a page's intro."""
    st.markdown(f'<div class="pc-explain"><div class="pc-explain-title">What this means</div>{escape(text)}</div>',
                unsafe_allow_html=True)


_card_count = 0


def card(eyebrow: str, stat: str, body: str) -> None:
    """A headline finding. Cards take turns through three tones so a row of them doesn't read as one gray block."""
    global _card_count
    tone = _card_count % 3 + 1
    _card_count += 1
    st.markdown(f'<div class="pc-card pc-tone{tone}"><div class="pc-eyebrow">{escape(eyebrow)}</div>'
                f'<div class="pc-stat">{escape(stat)}</div><div class="pc-body">{escape(body)}</div></div>',
                unsafe_allow_html=True)


def metric_html(label: str, value: str, note: str = "") -> str:
    # Words ("Consistent", "Not scored") get the smaller size too on phones, where a half-width card would break
    # them mid-word at the number size
    long = " pc-long" if len(value) > 11 else "" if any(c.isdigit() for c in value) else " pc-word"
    return (f'<div class="pc-metric"><div class="pc-metric-label">{escape(label)}</div>'
            f'<div class="pc-metric-value{long}">{escape(value)}</div>'
            f'<div class="pc-metric-note">{escape(note)}</div></div>')


def metric_card(label: str, value: str, note: str = "") -> None:
    st.markdown(metric_html(label, value, note), unsafe_allow_html=True)


def notice(text: str) -> None:
    """A plain status line for empty results and short notes, in the site's own type instead of Streamlit's blue
    info box. **bold** in the text is kept."""
    body = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escape(text))
    st.markdown(f'<p class="pc-notice" role="status">{body}</p>', unsafe_allow_html=True)


def metric_row(items: list[tuple[str, str, str]]) -> None:
    """Cards in a grid that wraps to fewer per row on narrow screens instead of squeezing the numbers."""
    cls = "pc-grid pc-grid-5" if len(items) == 5 else "pc-grid"
    st.markdown(f'<div class="{cls}">' + "".join(metric_html(*i) for i in items) + "</div>", unsafe_allow_html=True)


def party_tag(party: str) -> str:
    color = PARTY_VARS.get(party, "var(--pc-muted)")
    return f'<span class="pc-tag"><span class="pc-dot" style="background:{color}"></span>{escape(party)}</span>'


def pattern_badge(label: str) -> str:
    if label not in PATTERN_COLORS:
        return f'<span style="color:var(--pc-muted)">{escape(label)}</span>'
    fill = to_mode(PATTERN_COLORS[label])
    return f'<span class="pc-badge" style="background:{fill};color:{text_on(fill)}">{escape(label)}</span>'


def html_table(header: list[str], rows: list[list[str]], raw_cols: tuple[int, ...] = (), muted_cols: tuple[int, ...] = (),
               label: str = "Table", stack: bool = False, wide_cols: tuple[int, ...] = (),
               nowrap_cols: tuple[int, ...] = (), limit: int | None = None, more: str | None = None) -> None:
    """Small table with design-system styling. Cells in raw_cols are trusted HTML (badges); others are escaped.
    stack shows each row as a small card on phones (first column as its title, the others as label and value pairs)
    instead of a table that scrolls sideways. In a stacked card, wide_cols (long text) sit under their label instead
    of beside it. With limit, only the first rows show and the rest open under "Show N more" (or the more label)."""
    if limit and len(rows) > limit:
        kw = dict(raw_cols=raw_cols, muted_cols=muted_cols, stack=stack, wide_cols=wide_cols, nowrap_cols=nowrap_cols)
        html_table(header, rows[:limit], label=label, **kw)
        with st.expander(more or f"Show {len(rows) - limit} more"):
            html_table(header, rows[limit:], label=f"{label}, the rest", **kw)
        return
    # Stacked cards change the table's display on phones, which can drop its table meaning for screen readers, so
    # the roles are spelled out.
    role = (lambda r: f' role="{r}"') if stack else (lambda r: "")
    head = "".join(f'<th scope="col"{role("columnheader")}>{escape(h)}</th>' for h in header)
    body = ""
    for r in rows:
        cells = []
        for i, c in enumerate(r):
            classes = ((["pc-muted"] if i in muted_cols else []) + (["pc-td-wide"] if stack and i in wide_cols else [])
                       + (["pc-nowrap"] if i in nowrap_cols else []))
            cls = f' class="{" ".join(classes)}"' if classes else ""
            lab = f' data-label="{escape(header[i])}"' if stack and i < len(header) else ""
            cells.append(f"<td{cls}{lab}{role('cell')}>{c if i in raw_cols else escape(str(c))}</td>")
        body += f"<tr{role('row')}>" + "".join(cells) + "</tr>"
    # The wrapper scrolls sideways on narrow screens instead of squeezing words; it takes keyboard focus so it can
    # be scrolled without a mouse.
    table_cls = "pc-table pc-table-stack" if stack else "pc-table"
    st.markdown(f'<div class="pc-table-wrap" role="region" tabindex="0" aria-label="{escape(label)}">'
                f'<table class="{table_cls}"{role("table")}><thead{role("rowgroup")}><tr{role("row")}>{head}</tr></thead>'
                f'<tbody{role("rowgroup")}>{body}</tbody></table></div>',
                unsafe_allow_html=True)


def display_name(name: str) -> str:
    """'Schumer, Charles Ellis (Chuck)' -> 'Chuck Schumer'; 'King, Angus Stanley, Jr.' -> 'Angus King Jr.'"""
    parts = [p.strip() for p in str(name).split(",")]
    if len(parts) < 2:
        return str(name)
    last, given = parts[0], parts[1]
    nick = re.search(r"\(([^)]+)\)", given)
    first = nick.group(1) if nick else given.split()[0] if given.split() else ""
    tail = parts[2] if len(parts) > 2 else ""
    if tail.lower() in {"ii", "iii", "iv"}:  # Voteview writes "Iii"
        tail = tail.upper()
    suffix = f" {tail}" if tail else ""
    return f"{first} {last}{suffix}".strip()


SITE = "https://partycohesion.streamlit.app"


SHARE = "https://rendellrich.github.io/partycohesion/s"


def share_url(path: str = "", params: dict | None = None) -> str:
    """The link to share: a small page on GitHub Pages (built by scripts/build_share_pages.py) that carries this view's
    title and image for link previews and sends visitors on to the app. Streamlit Cloud's own page head shows only
    "Streamlit" in a Facebook or LinkedIn preview. Extra query parameters are passed through to the app."""
    from urllib.parse import urlencode
    rest = dict(params or {})
    if path == "States" and "state" in rest:
        base = f"{SHARE}/state/{rest.pop('state')}/"
    elif path == "Member_Explorer" and "member" in rest:
        base = f"{SHARE}/member/{rest.pop('member')}/"
    else:
        base = f"{SHARE}/{path}/" if path else f"{SHARE}/"
    return base + (f"?{urlencode(rest)}" if rest else "")


def share_bar(text: str, path: str = "", params: dict | None = None) -> None:
    """Share links for LinkedIn, X, Facebook, Reddit, email and Instagram (through the share cards), plus the page
    link to copy. path is the page's URL path
    (e.g. "Members"); params are query parameters that open the same view (e.g. a member's profile)."""
    from urllib.parse import quote
    url = share_url(path, params)
    u, t = quote(url, safe=""), quote(text, safe="")
    links = [("LinkedIn", f"https://www.linkedin.com/sharing/share-offsite/?url={u}"),
             ("X", f"https://twitter.com/intent/tweet?text={t}&url={u}"),
             ("Facebook", f"https://www.facebook.com/sharer/sharer.php?u={u}"),
             ("Reddit", f"https://www.reddit.com/submit?url={u}&title={t}"),
             ("Email", f"mailto:?subject={t}&body={quote(text + chr(10) + chr(10) + url, safe='')}"),
             # Instagram has no share link, so this opens the card page with images sized for it and a share button
             ("Instagram", "https://rendellrich.github.io/partycohesion/cards/")]
    st.markdown('<div class="pc-share"><span>Share</span>' + "".join(
        f'<a href="{escape(h)}" target="_blank" rel="noopener" aria-label="Share on {n}">{n}</a>' for n, h in links)
        + "</div>", unsafe_allow_html=True)
    st.caption("Or copy this link:")
    st.code(url, language=None)


BILL_PREFIXES = (("HCONRES", "H.Con.Res. "), ("SCONRES", "S.Con.Res. "), ("HJRES", "H.J.Res. "), ("SJRES", "S.J.Res. "),
                 ("HRES", "H.Res. "), ("SRES", "S.Res. "), ("HR", "H.R. "), ("S", "S. "))


def bill_label(bill: str) -> str:
    """HR8404 -> H.R. 8404"""
    for raw, nice in BILL_PREFIXES:
        if str(bill).startswith(raw) and str(bill)[len(raw):].isdigit():
            return nice + str(bill)[len(raw):]
    return str(bill)


def last_name(name: str) -> str:
    return str(name).split(",")[0].strip()


PARTY_ADJ = {"Democrat": "Democratic"}


def party_adj(party: str) -> str:
    """The party as an adjective: "Democratic platform", "Republican majority". "Democrat" stays the noun for a member
    ("a Democrat", the party tag); used before another noun it reads as the other side's usage, which a neutral record
    can't have."""
    return PARTY_ADJ.get(str(party), str(party))


def page_title(text: str = "") -> None:
    """The browser tab title, which screen readers announce on each page change: "Ted Cruz · PartyCohesion"."""
    st.set_page_config(page_title=f"{text} · PartyCohesion" if text else "PartyCohesion")


def congress_years(first: int, last: int, newest: int, left: int | None = None) -> str:
    """left is the year a member left office partway through the newest Congress, so they aren't shown as serving now."""
    start = 2 * int(first) + 1787
    end = str(left) if left else "now" if int(last) == int(newest) else str(2 * int(last) + 1788)
    return f"{start} to {end}"


def member_header(name: str, party: str, state: str, chamber: str, first: int, last: int, newest: int,
                  as_title: bool = False, left: int | None = None, photo: str = "") -> None:
    """The member's name, party and seat. as_title makes the name the page's h1 (the Members page with a member open)."""
    from chart_utils import ordinal
    span = f"{ordinal(first)} Congress" if int(first) == int(last) else f"{ordinal(first)} to {ordinal(last)} Congress"
    place = f"{STATES.get(state, state)}, {chamber}, {span} " \
            f"({congress_years(first, last, newest, left)})" + ("; data starts in 2007" if int(first) == 110 else "")
    if as_title:
        st.title(display_name(name))
        line = f'<div class="pc-place">{party_tag(party)} · {escape(place)}</div>'
        # The official photo sits beside the party and seat line, so the page starts with who this is in one glance
        st.markdown(f'<div class="pc-who">{photo}{line}</div>' if photo else line, unsafe_allow_html=True)
        return
    st.markdown(f'<div class="pc-name">{escape(display_name(name))} {party_tag(party)}</div>'
                f'<div class="pc-place">{escape(place)}</div>', unsafe_allow_html=True)


def chips(items: list[str]) -> str:
    return '<div class="pc-chips">' + "".join(f'<span class="pc-chip">{escape(i)}</span>' for i in items) + "</div>"


def fmt_date(value) -> str:
    """e.g. Sep 30, 2026 (portable: %-d is not supported on Windows)."""
    ts = pd.Timestamp(value)
    return f"{ts:%b} {ts.day}, {ts.year}"


def vote_card(v: pd.Series, broke: pd.DataFrame, link: str | None = None) -> None:
    """One vote: what it was, how each party split, and who broke with their party. broke needs name, party and
    state_abbrev columns. link, if given, is shown at the bottom (e.g. the vote's full record on Voteview)."""
    parties = [("Democrat", v["dem_yea"], v["dem_nay"]), ("Republican", v["rep_yea"], v["rep_nay"]),
               ("Independent", v["other_yea"], v["other_nay"])]
    widest = max(y + n for _, y, n in parties) or 1
    bars = ""
    for party, y, n in parties:
        if y + n == 0:
            continue
        seg = "".join(f'<span style="width:{max(cnt / widest * 100, 1.2 if cnt else 0):.1f}%;background:{VOTE_VARS[k]}"></span>'
                      for cnt, k in ((y, "Yea"), (n, "Nay")) if cnt)
        bars += f'<div>{party_tag(party)}</div><div class="pc-bar">{seg}</div>' \
                f'<div class="pc-body">{int(y)} Yea · {int(n)} Nay</div>'
    legend = " ".join(f'<span class="pc-tag" style="margin-right:14px"><span class="pc-dot" style="border-radius:2px;'
                      f'background:{VOTE_VARS[k]}"></span>{k}</span>' for k in ("Yea", "Nay"))
    eyebrow = f"{v['chamber']} · {fmt_date(v['date'])} · roll call {int(v['rollnumber'])}"
    result = f"{v['vote_question']} · {v['vote_result']}, {int(v['yea_count'])} Yea to {int(v['nay_count'])} Nay"
    if broke.empty:
        who = '<div class="pc-body" style="margin-top:12px">No Democrat or Republican voted against their party\'s majority.</div>'
    else:
        names = [f"{last_name(r.name)} ({r.party[0]}-{r.state_abbrev})" for r in broke.sort_values(["party", "name"]).itertuples()]
        who = (f'<div style="margin-top:14px;font-weight:600">{len(broke)} member{"s" if len(broke) != 1 else ""} voted '
               f"against their party's majority</div>{chips(names)}")
    source = (f'<div style="margin-top:6px"><a class="pc-link-target" href="{escape(link)}" target="_blank" rel="noopener" '
              f'style="color:var(--pc-accent)">Full record on Voteview</a></div>') if link else ""
    st.markdown(f'<div class="pc-card"><div class="pc-eyebrow">{escape(eyebrow)}</div>'
                f'<div style="font-size:1.4rem;font-weight:600;margin:6px 0 4px 0">{escape(str(v["label"]))}</div>'
                f'<div class="pc-body">{escape(result)}</div><div class="pc-bars">{bars}</div>'
                f'<div class="pc-body" style="font-size:0.85rem">{legend}</div>{who}{source}</div>', unsafe_allow_html=True)


EARLY_MIN_VOTES, EARLY_SHARE = 50, 0.8  # same rule as the member spotlights (scripts/member_spotlights.py)


def early_congress(members: pd.DataFrame) -> int | None:
    """The newest Congress if it has only just begun: fewer than 80% of its members have 50 party-line votes yet.
    Rates built on a handful of votes swing a lot, so pages default to the Congress before and say why."""
    newest = int(members["congress"].max())
    cur = members[members["congress"] == newest].drop_duplicates(["chamber", "icpsr"])
    if (members["congress"] == newest - 1).sum() == 0 or len(cur) == 0:
        return None
    ready = (cur["unity_votes_cast"] >= EARLY_MIN_VOTES).sum() >= EARLY_SHARE * len(cur)
    return None if ready else newest


def early_congress_note(members: pd.DataFrame) -> str | None:
    from chart_utils import ordinal
    newest = early_congress(members)
    if newest is None:
        return None
    cur = members[members["congress"] == newest]
    most = int(cur["unity_votes_cast"].max()) if len(cur) else 0
    return (f"The {ordinal(newest)} Congress has only just begun: no member has more than {most} party-line votes in "
            f"it yet, so its rates will swing a lot in the first weeks. Until most members pass 50, the headline numbers "
            f"use the {ordinal(newest - 1)} Congress's full two-year record. You can still pick the {ordinal(newest)} "
            "in the Congress menu.")
