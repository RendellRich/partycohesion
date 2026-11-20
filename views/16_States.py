"""States: every current member of Congress from one state or territory, with their voting record. A ZIP code narrows
the list to the visitor's own members. Opens from the map on Home (?state=FL); with no state picked it shows the map."""

from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

import find_members
from state_map import DELEGATE_PLACES, load_records, outline_svg, show_state_map, state_summary
from ui import STATES, html_table, page_title, inject_css, intro, party_tag, pattern_badge, share_bar

DATA_DIR = Path(__file__).parent.parent / "data"
INTRO = ("Every current member of Congress from one state, with how often they vote with their party, whether their "
         "votes change with the White House, and how many votes they miss.")

inject_css()

seats, zips = find_members.load_cached()
codes = sorted(seats["state_abbrev"].unique(), key=lambda a: STATES.get(a, a))
wanted = st.query_params.get("state", "").upper()
state = wanted if wanted in codes else None


def state_picker(key: str) -> None:
    """Choosing a state opens it. The link (?state=) is the one source of truth, so the map, a shared link and this
    picker can't disagree about which state is open."""
    def open_state() -> None:
        if st.session_state.get(key):
            st.query_params["state"] = st.session_state[key]
    st.selectbox("State", codes, index=codes.index(state) if state else None, format_func=lambda a: STATES.get(a, a),
                 placeholder="Choose a state", key=key, on_change=open_state)


if not state:
    if "state" in st.query_params:
        del st.query_params["state"]
    st.title("States")
    intro(INTRO, shortcuts=False)
    state_picker("st_state")
    show_state_map("states_map")
    st.stop()

name = STATES.get(state, state)
page_title(f"{name} members of Congress")
place = state in DELEGATE_PLACES
row = state_summary(seats).set_index("state").loc[state]
records = load_records()
# A House seat with no one in it (between a death or resignation and the special election) still belongs on the page:
# a visitor in that district otherwise sees no House member and can't tell why.
vacant = [] if place else find_members.vacant_districts(state, seats, zips)
vacant_line = ""
if vacant:
    labels = [find_members.district_label(state, d) for d in vacant]
    vacant_line = (f" {labels[0]} is vacant." if len(labels) == 1
                   else f" {', '.join(labels[:-1])} and {labels[-1]} are vacant.")
delegation = seats[seats["state_abbrev"] == state].copy().join(records, on="bioguide_id")

# The state's name is the page title, so a shared state link opens on it. Its outline, in its party-mix color from
# the map, sits beside the seat count and party mix.
st.title(name)
outline = outline_svg(state, row["rep_share"])
scored = delegation.dropna(subset=["party_unity_pct"])
flip_scored = delegation[delegation["label"].notna() & (delegation["label"] != "Not enough votes")]
summary = []
if len(scored) and not place:
    summary.append(f"Average party unity {scored['party_unity_pct'].mean():.0f}%.")
if len(flip_scored) and not place:
    summary.append(f"Position Flips: {(flip_scored['label'] == 'Consistent').sum()} of {len(flip_scored)} members "
                   "with enough comparable votes were consistent.")
st.markdown(f'<div class="pc-state-head">{outline}<div class="pc-body">{escape(row["seats_line"])}. '
            f'{escape(row["mix"])}.{escape(vacant_line)}' + (f'<br><span class="pc-muted">{escape(" ".join(summary))}</span>' if summary else "")
            + "</div></div>", unsafe_allow_html=True)

# Find your own members: by ZIP code (for visitors who don't know who represents them) or by name. A ZIP code
# entered on Home arrives as ?zip=; it fills the box once and leaves the address, so a shared link carries no ZIP code.
if "zip" in st.query_params:
    st.session_state["st_zip"] = find_members.clean_zip(st.query_params["zip"]) or ""
    del st.query_params["zip"]
c1, c2 = st.columns(2)
zip_text = c1.text_input("Your ZIP code", placeholder="5 digits",
                         key="st_zip", help="Shows only your two senators and your House member.")
query = c2.text_input("Or search by name", placeholder="e.g. Scott", key="st_query")

shown = delegation
shown_vacant = vacant
mine_note = ""
if zip_text.strip():
    z = find_members.clean_zip(zip_text)
    res = find_members.lookup_zip(z, seats, zips) if z else {"found": False}
    if not z:
        c1.markdown('<p role="alert">Enter a 5-digit ZIP code, like 34219.</p>', unsafe_allow_html=True)
    elif not res["found"]:
        c1.markdown('<p role="alert">That ZIP code isn\'t in the Census Bureau\'s ZIP list. The House\'s '
                    f'<a href="{find_members.OFFICIAL_LOOKUP}" target="_blank" rel="noopener">official lookup</a> '
                    "can find your district from your address.</p>", unsafe_allow_html=True)
    elif res["state"] != state:
        other = STATES.get(res["state"], res["state"])
        c1.markdown(f'<p role="alert">ZIP code {escape(z)} is in {escape(other)}. '
                    f'<a href="States?state={res["state"]}" target="_self">See {escape(other)}\'s members</a></p>',
                    unsafe_allow_html=True)
    else:
        ids = set(res["senators"]["bioguide_id"])
        for d in res["districts"]:
            ids |= set(d["member"]["bioguide_id"])
        shown = delegation[delegation["bioguide_id"].isin(ids)]
        several = len(res["districts"]) > 1
        if res["lines_current"]:
            shown_vacant = [int(d["district"]) for d in res["districts"] if d["member"].empty]
        empty = [find_members.district_label(state, d) for d in shown_vacant]
        mine_note = (f"Your members for ZIP code {z}."
                     + (" This ZIP code crosses district lines, so more than one House district is listed." if several
                        else "")
                     + (f" Your House seat, {empty[0]}, is vacant right now, so no one votes for it until a special "
                        "election fills it." if len(empty) == 1 and not several else
                        f" {', '.join(empty)} {'is' if len(empty) == 1 else 'are'} vacant right now." if empty else "")
                     + ("" if res["lines_current"] else " New district lines aren't matched to ZIP codes yet, so every "
                        "House member from the state is listed."))
if query.strip():
    shown = shown[shown["name"].str.contains(query.strip(), case=False, regex=False)]
    shown_vacant = []
if mine_note:
    st.markdown(f'<p role="status">{escape(mine_note)} Clear the ZIP code to see everyone from {escape(name)}.</p>',
                unsafe_allow_html=True)


def seat(r) -> str:
    if place:
        return "Delegate" if state != "PR" else "Resident Commissioner"
    if r.chamber == "Senate":
        return f"Senate, {r.senate_rank}" if isinstance(r.senate_rank, str) else "Senate"
    return find_members.district_label(state, r.district)


def member_cell(r) -> str:
    label = escape(str(r.name))
    if pd.notna(r.congress):
        return f'<a href="Member_Explorer?member={escape(r.bioguide_id)}" target="_self">{label}</a>'
    return f'{label} <span class="pc-muted">(not in the voting data yet)</span>'


# What's typical, so a visitor can tell whether their member's numbers are usual: medians across every current
# member of that chamber (delegates left out, since they vote on only some roll calls)
nation = seats[~seats["state_abbrev"].isin(DELEGATE_PLACES)].join(records, on="bioguide_id")


def typical(chamber: str, who: str) -> str:
    peers = nation[nation["chamber"] == chamber]
    unity, missed = peers["party_unity_pct"].median(), peers["missed_pct"].median()
    return f"Typical {who}: party unity {unity:.1f}%, missed votes {missed:.1f}%."


NO_DATA = '<span class="pc-muted">No votes yet</span>'


def member_table(group: pd.DataFrame, label: str, empty_seats: list[int] = ()) -> None:
    """One row per member, plus a row for each vacant district in its place in district order"""
    rows = [(int(r.district) if r.chamber == "House" else 0,
             [member_cell(r), escape(seat(r)), party_tag(r.party),
              f"{r.party_unity_pct:.1f}%" if pd.notna(r.party_unity_pct) else NO_DATA,
              pattern_badge(r.label) if isinstance(r.label, str) else NO_DATA,
              f"{r.missed_pct:.1f}%" if pd.notna(r.missed_pct) else NO_DATA])
            for r in group.itertuples()]
    none = '<span class="pc-muted">No votes</span>'
    rows += [(d, ["Seat vacant", escape(find_members.district_label(state, d)), '<span class="pc-muted">No member</span>',
                  none, none, none]) for d in empty_seats]
    rows.sort(key=lambda dr: dr[0])
    html_table(["Member", "Seat", "Party", "Party unity", "Position Flips", "Missed votes"], [r for _, r in rows],
               raw_cols=(0, 1, 2, 3, 4, 5), label=label, stack=True, nowrap_cols=(0, 1, 3, 5))


senators = shown[shown["chamber"] == "Senate"].sort_values("name")
house = shown[shown["chamber"] == "House"].sort_values(["district", "name"])
if shown.empty and not shown_vacant:
    if zip_text.strip() or query.strip():
        st.markdown('<p role="status">No members match. Try part of a last name, or clear the search.</p>',
                    unsafe_allow_html=True)
else:
    st.markdown('<p class="pc-muted">Party unity is the share of party-line votes where a member voted with their own '
                "party. Missed votes is the share of roll calls they didn't vote on. Position Flips shows whether their "
                "votes on the same kinds of questions changed when the White House changed parties. Tap or click a "
                "name for the full record.</p>", unsafe_allow_html=True)
    if len(senators):
        st.header("Senators")
        st.caption(typical("Senate", "senator"))
        member_table(senators, f"Senators from {name}")
    if len(house) or shown_vacant:
        st.header("Delegate" if place and state != "PR" else "Resident Commissioner" if place else "House, by district")
        st.caption(typical("House", "House member") + (" Delegates can vote only on some House roll calls, so their "
                                                         "missed votes count only those." if place else ""))
        # Big delegations (California has 52 seats) are a long scroll on a phone; a district picker narrows it to one
        empty_seats = shown_vacant
        if len(house) + len(empty_seats) > 10:
            all_d = sorted(set(int(d) for d in house["district"]) | set(empty_seats))
            districts = [find_members.district_label(state, d) for d in all_d]
            pick = st.selectbox("Go to a district", ["All districts"] + districts, key=f"st_district_{state}",
                                help="Don't know your district? Enter your ZIP code above.")
            if pick != "All districts":
                house = house[[find_members.district_label(state, d) == pick for d in house["district"]]]
                empty_seats = [d for d in empty_seats if find_members.district_label(state, d) == pick]
        member_table(house, f"House members from {name}", empty_seats)
    st.caption("Numbers are from each member's latest Congress in the data.")

if not place:
    house_link = (f', and its <a href="Same_State_Different_Vote?state={state}&chamber=house" target="_self">House '
                  "members of the same party</a>" if row["house"] >= 2 else "")
    st.markdown(f'See how often {escape(name)}\'s <a href="Same_State_Different_Vote?state={state}" target="_self">'
                f"senators</a>{house_link} vote opposite ways.", unsafe_allow_html=True)

share_bar(f"{name}'s members of Congress and how they vote, on PartyCohesion", "States", {"state": state})

with st.expander("Pick a different state"):
    state_picker(f"st_state_{state}")
    show_state_map("states_map_more", height=420)
