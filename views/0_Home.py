"""
PartyCohesion home page: the site's question, three headline findings computed from the data,
and current coverage. Layout follows the "Home" mockup in the PartyCohesion Figma design system.
"""

from pathlib import Path

import pandas as pd
import streamlit as st

import plotly.graph_objects as go

from chart_utils import BG, PARTY_COLORS, ordinal, show_chart
from seat_map import seat_map
from flip_utils import add_chamber_control, flip_scores
from platform_utils import all_member_platform_votes, load_platform, party_totals
import find_members
from ui import STATES, card, display_name, early_congress, fmt_date, hero_panel, inject_css

DATA_DIR = Path(__file__).parent.parent / "data"

inject_css()


@st.cache_data
def load():
    members = pd.read_csv(DATA_DIR / "members_processed.csv")
    summary = pd.read_csv(DATA_DIR / "unity_summary.csv")
    key_votes = pd.read_csv(DATA_DIR / "key_votes.csv")
    flip_votes = add_chamber_control(pd.read_csv(DATA_DIR / "flip_member_votes.csv"), members)
    return members, summary, key_votes, flip_votes


members, summary, key_votes, flip_votes = load()
latest = int(members["congress"].max())
current = members[members["congress"] == latest]
# In the first weeks of a new Congress, the headline numbers use the one before (see ui.early_congress)
stat_congress = latest - 1 if early_congress(members) else latest
stat_members = members[members["congress"] == stat_congress]

hero_panel("Do members of Congress vote the same way no matter who is president?",
           "PartyCohesion uses the official roll-call record, every vote since 2007, to show how often each member "
           "sides with their party, and whether their position on the same question changes when the White House "
           "changes hands. No scorecards, no opinions: the votes and the method.")

# Look up a member: the most common reason someone opens the site
pick_list = current.sort_values("congress").drop_duplicates("icpsr", keep="last").sort_values("name")
pick_list = pick_list[pick_list["bioguide_id"].notna()]
labels = {f"{display_name(r.name)} ({r.party[0]}-{r.state_abbrev}, {r.chamber})": r.bioguide_id
          for r in pick_list.itertuples()}
who = st.selectbox("Look up your representative or senator", list(labels), index=None,
                   placeholder="Type a name, e.g. Ocasio-Cortez or Cruz", key="home_lookup")
if who:
    st.switch_page("views/2_Member_Explorer.py", query_params={"member": labels[who]})

# Or find them by ZIP code or state, for visitors who don't know who represents them
with st.expander("Don't know who represents you? Find your members by ZIP code or state"):
    seats, zips = find_members.load_cached()
    have_data = set(current["bioguide_id"].dropna())
    z_col, s_col = st.columns(2)
    zip_text = z_col.text_input("ZIP code", max_chars=10, placeholder="e.g. 34219", key="home_zip")
    state_pick = s_col.selectbox("Or pick a state", sorted(STATES, key=STATES.get), index=None,
                                 format_func=lambda a: STATES[a], placeholder="Choose a state", key="home_state")

    def member_button(r, note: str = "") -> None:
        label = f"{r.name} ({str(r.party)[:1]}), {note or r.chamber}"
        if r.bioguide_id in have_data:
            if st.button(label, key=f"find_{r.bioguide_id}"):
                st.switch_page("views/2_Member_Explorer.py", query_params={"member": r.bioguide_id})
        else:
            st.markdown(f"{label} · not in the voting data yet")

    if zip_text:
        z = find_members.clean_zip(zip_text)
        res = find_members.lookup_zip(z, seats, zips) if z else {"found": False}
        if not res["found"]:
            st.caption("That ZIP code isn't in the Census Bureau's ZIP list. Try your state instead, or the House's "
                       f"official lookup: {find_members.OFFICIAL_LOOKUP}")
        else:
            st.markdown(f"**Senators for {STATES.get(res['state'], res['state'])}**")
            for r in res["senators"].itertuples():
                member_button(r, "Senate")
            several = len(res["districts"]) > 1
            st.markdown("**House**" + (" (this ZIP code crosses district lines)" if several and res["lines_current"] else ""))
            for d in res["districts"]:
                where = find_members.district_label(res["state"], d["district"])
                if several and d["share"] is not None:
                    where += f", {d['share']:.0%} of the ZIP's land"
                if d["member"].empty:
                    st.markdown(f"{where}: seat currently vacant")
                for r in d["member"].itertuples():
                    member_button(r, where)
            if several or not res["lines_current"]:
                st.caption("To be sure which district your address is in, use the House's official lookup: "
                           f"{find_members.OFFICIAL_LOOKUP}")
            if not res["lines_current"]:
                st.caption("Some states drew new district lines for the 120th Congress, and the Census Bureau hasn't "
                           "published ZIP codes for them yet, so this lists every House member from the state.")
    elif state_pick:
        sens, house = find_members.state_members(state_pick, seats)
        st.markdown(f"**Senators for {STATES[state_pick]}**")
        for r in sens.itertuples():
            member_button(r, "Senate")
        st.markdown("**House**")
        for r in house.itertuples():
            member_button(r, find_members.district_label(state_pick, r.district))
    st.caption("ZIP codes to districts: U.S. Census Bureau, 2020 ZIP Code Tabulation Areas and 119th Congress "
               "districts. Current members: unitedstates/congress-legislators.")

# The chamber at a glance: every current member as one seat, arranged left to right by ideology score
chamber = st.segmented_control("Chamber", ["House", "Senate"], default="House", key="home_chamber",
                               label_visibility="collapsed") or "House"
in_chamber = (current[current["chamber"] == chamber].sort_values("party_unity_pct")
              .drop_duplicates("icpsr", keep="last").copy())
in_chamber["label"] = [f"{display_name(r.name)} ({r.party[0]}-{r.state_abbrev})" for r in in_chamber.itertuples()]
event = show_chart(seat_map(in_chamber, chamber), f"The {chamber}, {ordinal(latest)} Congress",
                   f"seat_map_{chamber.lower()}",
                   key=f"seat_map_{chamber}_{st.session_state.get('seat_clicks', 0)}", on_select="rerun")
st.caption("One dot per member, placed left to right by their Voteview ideology score (lower scores lean liberal, "
           "higher scores lean conservative). Hover a dot for their record "
           "with their party; click it to open their page. The count includes members who left office and their "
           "replacements.")
picked = (event or {}).get("selection", {}).get("points", []) if event else []
if picked and picked[0].get("customdata") and picked[0]["customdata"][2]:
    st.session_state["seat_clicks"] = st.session_state.get("seat_clicks", 0) + 1  # a fresh chart next visit
    st.switch_page("views/2_Member_Explorer.py", query_params={"member": picked[0]["customdata"][2]})
st.write("")

# Finding 1: Position Flips, current members
scores = flip_scores(flip_votes).merge(current[["icpsr"]].drop_duplicates(), on="icpsr")
scored = scores[scores["label"] != "Not enough votes"]
pct_consistent = (scored["label"] == "Consistent").mean() * 100 if len(scored) else 0

# Finding 2: party unity, current Congress
dr = stat_members[stat_members["party"].isin(["Democrat", "Republican"])].dropna(subset=["party_unity_pct"])
means = dr.groupby("party")["party_unity_pct"].mean()
n_unity = int(summary.loc[summary["congress"] == stat_congress, "party_unity_votes"].sum())

# Finding 3: the biggest party break among final votes in the current Congress
breaks = key_votes[(key_votes["congress"] == stat_congress) & (key_votes["series"] == "Biggest Party Breaks")].copy()
breaks["broke"] = breaks["dem_defectors"] + breaks["rep_defectors"]
top = breaks.sort_values("broke", ascending=False).iloc[0] if len(breaks) else None

c1, c2, c3 = st.columns(3, gap="medium")
with c1:
    card("Position flips", f"{pct_consistent:.0f}%",
         f"of current members ({len(scored)} with enough comparable votes) cast the same vote on debt limits, "
         "government funding, disaster aid and war powers under presidents of both parties, comparing like with like.")
    st.page_link("views/7_Position_Flips.py", label="See every member")
    st.page_link("views/9_How_It_Works.py", label="How this is measured")
with c2:
    card("Party unity", f"{means.min():.0f}–{means.max():.0f}%",
         f"Average share of the {ordinal(stat_congress)} Congress's {n_unity:,} party-line votes on which members sided "
         "with their own party" + ("." if stat_congress == latest else ", its full two-year record."))
    st.page_link("views/2_Member_Explorer.py", label="Explore members")
with c3:
    if top is not None:
        label = str(top["vote_desc"] if pd.notna(top["vote_desc"]) else top["bill_number"])
        card("Biggest party break", f"{int(top['broke'])} members",
             f"voted against their own party's majority on {label[:90]} ({top['chamber']}, {fmt_date(top['date'])}).")
    st.page_link("views/5_Key_Votes.py", label="See who broke ranks")

# Finding 4: Platform Votes, every Congress in the data
plat_topics, plat_links = load_platform()
plat = party_totals(all_member_platform_votes()).set_index("party")
pd_, pr_ = plat.loc["Democrat"], plat.loc["Republican"]
st.write("")
p1, p2 = st.columns(2, gap="medium")
with p1:
    card("Platform votes, Democrats", f"{int(pd_['members_against'])} of {int(pd_['members'])}",
         "Democrats voted against their own party's platform at least once, on topics where the two parties' "
         f"platforms take opposite, specific positions ({len(plat_topics)} topics since 2007).")
with p2:
    card("Platform votes, Republicans", f"{int(pr_['members_against'])} of {int(pr_['members'])}",
         "Republicans voted against their own party's platform at least once, on the same topics. The totals depend "
         "on which topics qualify under the published rules, so they describe these votes, not which party is more "
         "loyal.")
st.page_link("views/11_Platform_Votes.py", label="See every topic, vote and member")

# Findings 5 to 7: missed votes, cosponsored then voted no, campaign statements
missed = pd.read_csv(DATA_DIR / "missed_votes.csv")
missed_pct = 100 * missed["missed"].sum() / missed["eligible"].sum()
house_median = (100 * missed["missed"] / missed["eligible"])[missed["chamber"] == "House"].median()
co_votes = pd.read_csv(DATA_DIR / "cosponsor_votes.csv")
co_nays = pd.read_csv(DATA_DIR / "cosponsor_nays.csv").merge(
    co_votes[["congress", "chamber", "rollnumber", "changed_before_vote"]], on=["congress", "chamber", "rollnumber"])
camp = pd.read_csv(DATA_DIR / "campaign_statement_votes.csv")
camp_diff = camp[camp["same_direction"] == "No"]
st.write("")
f1, f2, f3 = st.columns(3, gap="medium")
with f1:
    card("Missed votes", f"{missed_pct:.1f}%",
         f"of roll calls held while they served were missed by members since 2007. The typical House member misses "
         f"{house_median:.1f}% in a Congress, and a small group accounts for most absences.")
    st.page_link("views/2_Member_Explorer.py", label="Look up a member")
with f2:
    card("Cosponsored, then voted no", f"{len(co_nays):,}",
         f"times a bill's own sponsor or cosponsor voted against it on final passage. Only "
         f"{int((~co_nays['changed_before_vote']).sum())} of those came on text that hadn't changed since they signed.")
    st.page_link("views/12_Cosponsored_Then_No.py", label="See every case")
with f3:
    card("Campaign statements", f"{(camp['same_direction'] == 'Yes').sum()} of {len(camp)}",
         f"clear positions on House members' own campaign websites were followed by a vote in the same direction. "
         f"{len(camp_diff)} went the other way.")
    st.page_link("views/13_Campaign_Statements.py", label="Read the statements")

st.write("")
# Party unity over time: the one chart on Home
unity = (members[members["party"].isin(["Democrat", "Republican"])]
         .groupby(["congress", "party"])["party_unity_pct"].mean().reset_index())
unity["year"] = 2 * unity["congress"] + 1787
fig = go.Figure()
for party in ("Democrat", "Republican"):
    u = unity[unity["party"] == party]
    fig.add_trace(go.Scatter(
        x=u["year"], y=u["party_unity_pct"], name=party, mode="lines+markers",
        line=dict(color=PARTY_COLORS[party], width=2), marker=dict(size=8, line=dict(color=BG, width=2)),
        customdata=u["congress"].map(ordinal),
        hovertemplate=f"{party}s, %{{customdata}} Congress (%{{x}}): %{{y:.1f}}%<extra></extra>"))
    end = u.iloc[-1]
    fig.add_annotation(x=end["year"], y=end["party_unity_pct"], text=f"{party}s {end['party_unity_pct']:.0f}%",
                       xanchor="left", xshift=10, showarrow=False, font=dict(size=13))
fig.update_layout(height=360, hovermode="x unified", margin=dict(r=140, l=10, b=10),
                  yaxis=dict(range=[80, 100], ticksuffix="%", title=None),
                  xaxis=dict(dtick=4, title=None, range=[2005.5, int(unity["year"].max()) + 0.8]))
show_chart(fig, "Share of party-line votes cast with their own party, average member, by Congress",
           "party_unity_over_time")
st.caption("A party-line vote is one where most Democrats and most Republicans voted on opposite sides. The vertical "
           "axis starts at 80% so the change between Congresses is visible.")
st.write("")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Congress", ordinal(latest), help="House and Senate")
m2.metric("Members scored", f"{current['party_unity_pct'].notna().sum():,}")
m3.metric("Party-line votes", f"{n_unity:,}", help=f"so far in the {ordinal(latest)} Congress")
try:
    m4.metric("Data through", fmt_date(summary["latest_vote_date"].max()),
              help="Refreshed automatically twice a week")
except Exception:
    m4.metric("Data through", "—")

st.markdown("---")
st.caption("Sources: Voteview roll-call records (Lewis, Poole, Rosenthal, Boche, Rudkin & Sonnet) and White House "
           "Statements of Administration Policy. Coverage: 110th Congress (2007) to present. PartyCohesion is an "
           "independent educational project and does not endorse any party or candidate.")
