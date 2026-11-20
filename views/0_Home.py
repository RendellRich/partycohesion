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
from state_map import show_state_map
from flip_utils import add_chamber_control, flip_scores
from platform_utils import all_member_platform_votes, load_platform, party_totals
import find_members
from theme import narrow
from ui import STATES, card, display_name, early_congress, fmt_date, hero_panel, inject_css, metric_row, section_heading

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
           "Every roll-call vote since 2007: how often each member sides with their party, and whether their "
           "position on the same question changes when the White House changes hands. No scorecards, no opinions.")

# Find your own members, the most common reason someone opens the site: by ZIP code first (most visitors don't know
# who represents them), or by name. Side by side on wide screens, ZIP code on top on phones.
pick_list = current.sort_values("congress").drop_duplicates("icpsr", keep="last").sort_values("name")
pick_list = pick_list[pick_list["bioguide_id"].notna()]
labels = {f"{display_name(r.name)} ({r.party[0]}-{r.state_abbrev}, {r.chamber})": r.bioguide_id
          for r in pick_list.itertuples()}
c_zip, c_name = st.columns(2)
zip_text = c_zip.text_input("Find your members by ZIP code", placeholder="5 digits", key="home_zip")
who = c_name.selectbox("Or look up a member by name", list(labels), index=None,
                       placeholder="e.g. Ocasio-Cortez or Cruz", key="home_lookup")
if who:
    st.switch_page("views/2_Member_Explorer.py", query_params={"member": labels[who]})
if zip_text.strip():
    seats, zips = find_members.load_cached()
    z = find_members.clean_zip(zip_text)
    res = find_members.lookup_zip(z, seats, zips) if z else {"found": False}
    if not z:
        st.markdown('<p role="alert">Enter a 5-digit ZIP code, like 34219.</p>', unsafe_allow_html=True)
    elif not res["found"]:
        st.markdown('<p role="alert">That ZIP code isn\'t in the Census Bureau\'s ZIP list. Pick your state on the map '
                    f'below, or use the House\'s <a href="{find_members.OFFICIAL_LOOKUP}" target="_blank" '
                    'rel="noopener">official lookup</a>.</p>', unsafe_allow_html=True)
    else:
        st.switch_page("views/16_States.py", query_params={"state": res["state"], "zip": z})

# Members of Congress by state: hover a state for its delegation, click it to see every member
section_heading("Members of Congress by state")
# The map can't be reached by keyboard or read by a screen reader, so the same choice is offered as a list
codes = sorted(find_members.load_cached()[0]["state_abbrev"].unique(), key=lambda a: STATES.get(a, a))
state_pick = st.selectbox("Or pick a state", codes, index=None, format_func=lambda a: STATES.get(a, a),
                          placeholder="Choose a state or territory", key="home_state")
if state_pick:
    st.switch_page("views/16_States.py", query_params={"state": state_pick})
show_state_map("home_state_map")
st.write("")

# The chamber at a glance: every current member as one seat, arranged left to right by ideology score
section_heading("The chamber at a glance")
chamber = st.segmented_control("Chamber", ["House", "Senate"], default="House", key="home_chamber",
                               label_visibility="collapsed") or "House"
in_chamber = (current[current["chamber"] == chamber].sort_values("party_unity_pct")
              .drop_duplicates("icpsr", keep="last").copy())
in_chamber["label"] = [f"{display_name(r.name)} ({r.party[0]}-{r.state_abbrev})" for r in in_chamber.itertuples()]
# On phones the dots are a few pixels wide and a scroll can land as a tap, so a tap only shows who a dot is
phone = narrow()
event = show_chart(seat_map(in_chamber, chamber), f"The {chamber}, {ordinal(latest)} Congress",
                   f"seat_map_{chamber.lower()}",
                   key=f"seat_map_{chamber}_{st.session_state.get('seat_clicks', 0)}",
                   on_select=None if phone else "rerun")
st.caption("One dot per member, placed left to right by their Voteview ideology score (lower scores lean liberal, "
           "higher scores lean conservative). "
           + ("Tap a dot to see who it is and their record with their party; the lookup at the top opens a member's "
              "page." if phone else "Hover over a dot for their record with their party, or click it to open their "
              "page.")
           + " The count includes members who left office and their replacements.")
picked = event.get("selection", {}).get("points", []) if event and not phone else []
if picked and picked[0].get("customdata") and picked[0]["customdata"][2]:
    st.session_state["seat_clicks"] = st.session_state.get("seat_clicks", 0) + 1  # a fresh chart next visit
    st.switch_page("views/2_Member_Explorer.py", query_params={"member": picked[0]["customdata"][2]})
st.write("")

# Finding 1: Position Flips, current members
scores = flip_scores(flip_votes).merge(current[["icpsr"]].drop_duplicates(), on="icpsr")
scored = scores[scores["label"] != "Not enough votes"]
CHANGED = ("Partly changed", "Changed with the White House")  # a shift of 25 points or more toward their own president
pct_changed = scored["label"].isin(CHANGED).mean() * 100 if len(scored) else 0

# Finding 2: party unity, current Congress
dr = stat_members[stat_members["party"].isin(["Democrat", "Republican"])].dropna(subset=["party_unity_pct"])
means = dr.groupby("party")["party_unity_pct"].mean()
n_unity = int(summary.loc[summary["congress"] == stat_congress, "party_unity_votes"].sum())

# Finding 3: the biggest party break among final votes in the current Congress
breaks = key_votes[(key_votes["congress"] == stat_congress) & (key_votes["series"] == "Biggest Party Breaks")].copy()
breaks["broke"] = breaks["dem_defectors"] + breaks["rep_defectors"]
top = breaks.sort_values("broke", ascending=False).iloc[0] if len(breaks) else None

section_heading("What the record shows")
c1, c2, c3 = st.columns(3, gap="medium")
with c1:
    card("Position flips", f"{pct_changed:.0f}%",
         f"of current members ({len(scored)} with enough comparable votes) gave the president noticeably more room on "
         "debt limits, government funding, disaster aid and war powers when he was from their own party (a shift of "
         "25 points or more), comparing like with like.")
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

# The same cards as the rest of the site (Streamlit's own metric cut "Data through Nov 18, …" short on desktop)
try:
    through = fmt_date(summary["latest_vote_date"].max())
except Exception:
    through = "None yet"
metric_row([("Congress", ordinal(latest), "House and Senate"),
            ("Members scored", f"{current['party_unity_pct'].notna().sum():,}", "with party unity rates"),
            ("Party-line votes", f"{n_unity:,}", f"so far in the {ordinal(latest)} Congress"),
            ("Data through", through, "refreshed automatically twice a week")])

st.markdown("---")
st.caption("Sources: Voteview roll-call records (Lewis, Poole, Rosenthal, Boche, Rudkin & Sonnet) and White House "
           "Statements of Administration Policy. Coverage: 110th Congress (2007) to present. PartyCohesion is an "
           "independent educational project and does not endorse any party or candidate.")
