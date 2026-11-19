"""States: every current member of Congress from one state or territory, with their voting record, searchable by
name. Opens from the map on Home (?state=FL); with no state picked it shows the map."""

from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

import find_members
from state_map import DELEGATE_PLACES, load_records, outline_svg, show_state_map, state_summary
from ui import STATES, html_table, inject_css, intro, metric_row, party_tag, pattern_badge, share_bar

DATA_DIR = Path(__file__).parent.parent / "data"

inject_css()


st.title("States")
intro("Every current member of Congress from one state, with how often they vote with their party, whether their "
      "votes change with the White House, and how many votes they miss.", shortcuts=False)

seats, _ = find_members.load_cached()
codes = sorted(seats["state_abbrev"].unique(), key=lambda a: STATES.get(a, a))
wanted = st.query_params.get("state", "").upper()
state = st.selectbox("State", codes, index=codes.index(wanted) if wanted in codes else None,
                     format_func=lambda a: STATES.get(a, a), placeholder="Choose a state", key="st_state")

if not state:
    if "state" in st.query_params:
        del st.query_params["state"]
    show_state_map("states_map")
    st.stop()

st.query_params["state"] = state
name = STATES.get(state, state)
row = state_summary(seats).set_index("state").loc[state]
records = load_records()
delegation = seats[seats["state_abbrev"] == state].copy()
delegation = delegation.join(records, on="bioguide_id")

# The state's outline, in its party-mix color from the map, beside its name
outline = outline_svg(state, row["rep_share"])
st.markdown(f'<div style="display:flex;align-items:center;gap:1.25rem;margin:0.25rem 0 1rem">{outline}<div>'
            f'<div style="font-size:1.6rem;font-weight:700;line-height:1.2">{escape(name)}</div>'
            f'<div class="pc-body">{escape(row["seats_line"])}. {escape(row["mix"])}.</div></div></div>',
            unsafe_allow_html=True)

scored = delegation.dropna(subset=["party_unity_pct"])
flip_scored = delegation[delegation["label"].notna() & (delegation["label"] != "Not enough votes")]
metric_row([
    (f"Members from {name}", str(row["members"]), row["seats_line"]),
    ("Party mix", row["short"], row["mix"]),
    ("Average party unity", f"{scored['party_unity_pct'].mean():.0f}%" if len(scored) else "None",
     "share of party-line votes cast with their own party"),
    ("Position Flips: consistent", f"{(flip_scored['label'] == 'Consistent').sum()} of {len(flip_scored)}",
     "members with enough comparable votes"),
])
if state not in DELEGATE_PLACES:
    house_link = (f', and its <a href="Same_State_Different_Vote?state={state}&chamber=house" target="_self">House '
                  "members of the same party</a>" if row["house"] >= 2 else "")
    st.markdown(f'See how often {escape(name)}\'s <a href="Same_State_Different_Vote?state={state}" target="_self">'
                f"senators</a>{house_link} vote opposite ways.", unsafe_allow_html=True)
share_bar(f"{name}'s members of Congress and how they vote, on PartyCohesion", "States", {"state": state})

# Search and filter within the state
c1, c2 = st.columns([2, 1])
query = c1.text_input("Search by name", placeholder="e.g. Scott", key="st_query")
if state in DELEGATE_PLACES:
    chamber = "All"
else:
    chamber = c2.segmented_control("Chamber", ["All", "Senate", "House"], default="All", key="st_chamber") or "All"

shown = delegation
if chamber != "All":
    shown = shown[shown["chamber"] == chamber]
if query.strip():
    shown = shown[shown["name"].str.contains(query.strip(), case=False, regex=False)]
shown = shown.assign(order=(shown["chamber"] != "Senate").astype(int)).sort_values(["order", "district", "name"])


def seat(r) -> str:
    if state in DELEGATE_PLACES:
        return "Delegate" if state != "PR" else "Resident Commissioner"
    if r.chamber == "Senate":
        return f"Senate, {r.senate_rank}" if isinstance(r.senate_rank, str) else "Senate"
    return find_members.district_label(state, r.district)


def member_cell(r) -> str:
    label = escape(str(r.name))
    if pd.notna(r.congress):
        return f'<a href="Member_Explorer?member={escape(r.bioguide_id)}" target="_self">{label}</a>'
    return f'{label} <span class="pc-muted">(not in the voting data yet)</span>'


rows = [[member_cell(r), seat(r), party_tag(r.party),
         f"{r.party_unity_pct:.1f}%" if pd.notna(r.party_unity_pct) else "None",
         pattern_badge(r.label) if isinstance(r.label, str) else "None",
         f"{r.missed_pct:.1f}%" if pd.notna(r.missed_pct) else "None"]
        for r in shown.itertuples()]
if rows:
    html_table(["Member", "Seat", "Party", "Party unity", "Position Flips", "Missed votes"], rows, raw_cols=(0, 2, 4),
               label="Members from this state", stack=True)
    st.caption("Party unity and missed votes are from each member's latest Congress in the data. Position Flips "
               "compares the same kinds of votes under presidents of both parties. Click a name for the full record.")
else:
    st.info("No members match that search. Try part of a last name, or clear the search.")

with st.expander("Pick a different state on the map"):
    show_state_map("states_map_more", height=420)
