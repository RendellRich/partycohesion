"""Members: one member's profile (party unity, Position Flips, votes with each president's stated
position, ideology), plus a browsable table of every member. Layout follows the "Members" mockup in
the PartyCohesion Figma design system."""

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from chart_utils import ACCENT, MUTED, PARTY_COLORS, ordinal, show_chart
from flip_utils import add_chamber_control, flip_scores
from ui import display_name, html_table, inject_css, intro, last_name, member_header, metric_row, pattern_badge

DATA_DIR = Path(__file__).parent.parent / "data"
PREFIX = {"House": "H", "Senate": "S"}
CATEGORIES = ["Debt limit", "Stopgap funding", "Full-year funding", "Disaster aid", "War powers limits"]


@st.cache_data
def load_members():
    return pd.read_csv(DATA_DIR / "members_processed.csv")


@st.cache_data
def load_flips():
    return add_chamber_control(pd.read_csv(DATA_DIR / "flip_member_votes.csv"), load_members())


@st.cache_data
def load_matrix(congress: int, chamber: str):
    path = DATA_DIR / "matrices" / f"{PREFIX[chamber]}{congress}.npz"
    if not path.exists():
        return None
    with np.load(path) as f:
        return f["icpsr"], f["rollnumber"], f["votes"]


@st.cache_data
def president_support(congress: int, chamber: str) -> pd.DataFrame:
    """Every member's agreement with the president's stated position on votes with a White House statement."""
    pv = pd.read_csv(DATA_DIR / "president_position_votes.csv")
    pv = pv[(pv["congress"] == congress) & (pv["chamber"] == chamber)]
    mat = load_matrix(congress, chamber)
    if mat is None or pv.empty:
        return pd.DataFrame()
    icpsr, rolls, votes = mat
    col = {r: i for i, r in enumerate(rolls)}
    pv = pv[pv["rollnumber"].isin(col)]
    sub = votes[:, [col[r] for r in pv["rollnumber"]]]
    target = np.where(pv["president_vote"].to_numpy() == "Yea", 1, -1)
    voted = sub != 0
    agree = (sub == target) & voted
    out = []
    for pres in pv["president"].unique():
        m = (pv["president"] == pres).to_numpy()
        out.append(pd.DataFrame({"icpsr": icpsr, "president": pres,
                                 "president_party": pv.loc[pv["president"] == pres, "president_party"].iloc[0],
                                 "votes": voted[:, m].sum(axis=1), "agreed": agree[:, m].sum(axis=1)}))
    return pd.concat(out, ignore_index=True)


inject_css()
df = load_members()
flips = load_flips()
newest = int(df["congress"].max())

st.title("Members")
intro("Look up any member of Congress since 2007: how often they vote with their party, whether their votes change "
      "with the White House, and where they sit ideologically.")

# One entry per person, labeled with their most recent party, state and chamber
latest = df.sort_values("congress").groupby("icpsr").tail(1)
latest = latest.assign(label=latest["name"] + " (" + latest["party"].str[0] + "-" + latest["state_abbrev"] + ", "
                       + latest["chamber"] + ")")
dupes = latest["label"].duplicated(keep=False)
latest.loc[dupes, "label"] = latest.loc[dupes, "label"] + " #" + latest.loc[dupes, "icpsr"].astype(str)
options = dict(zip(latest.sort_values("label")["label"], latest.sort_values("label")["icpsr"]))

pick = st.selectbox("Find a member", list(options), index=None, placeholder="Type a name…", key="me_member")

if pick:
    icpsr = options[pick]
    rows = df[df["icpsr"] == icpsr].sort_values("congress")
    member = rows.iloc[-1]
    short = last_name(member["name"])
    member_header(member["name"], member["party"], member["state_abbrev"], member["chamber"],
                  rows["congress"].min(), rows["congress"].max(), newest)
    caucus = member.get("caucus")
    if member["party"] not in ("Democrat", "Republican") and pd.notna(caucus):
        st.caption(f"Caucuses with the {caucus}s, so party unity and Position Flips compare them with {caucus}s.")

    # Headline metrics
    scored = rows.dropna(subset=["party_unity_pct"])
    if scored.empty:
        unity = ("Party unity", "None", "No party-line votes scored")
    else:
        u = scored.iloc[-1]
        unity = (f"Party unity, {ordinal(u['congress'])}", f"{u['party_unity_pct']:.1f}%",
                 f"{int(u['votes_with_party']):,} of {int(u['unity_votes_cast']):,} party-line votes")
    overall = flip_scores(flips[flips["icpsr"] == icpsr])
    if overall.empty:
        flip = ("Position Flips", "No votes", "No votes in these categories")
    else:
        o = overall.iloc[0]
        n = int(o["matched_own"] + o["matched_other"])
        flip = ("Position Flips", o["label"],
                f"{o['shift']:+.0f} point shift, {n} matched votes" if o["label"] != "Not enough votes"
                else f"{int(o['n_own'] + o['n_other'])} votes, too few matched")
    ideo = member["nominate_dim1"]
    chambers = " and ".join(sorted(rows["chamber"].unique()))
    metric_row([
        unity, flip,
        ("Ideology score", f"{ideo:.2f}" if pd.notna(ideo) else "None", "−1 liberal to +1 conservative"),
        ("In this data since", str(2 * int(rows["congress"].min()) + 1787),
         f"{rows['congress'].nunique()} Congress{'es' if rows['congress'].nunique() > 1 else ''}, {chambers}"
         + (" (data starts in 2007)" if int(rows["congress"].min()) == int(df["congress"].min()) else "")),
    ])

    # Same question, different president
    st.subheader("Same question, different president")
    st.markdown("How often this member gave the president room on the same kinds of votes, under their own party's "
                "presidents and under the other party's.")
    table_rows = []
    for cat in CATEGORIES:
        s = flip_scores(flips[(flips["icpsr"] == icpsr) & (flips["category"] == cat)])
        if s.empty:
            continue
        r = s.iloc[0]
        own = f"{r['rate_own']:.0f}% of {int(r['n_own'])}" if r["n_own"] else "None"
        other = f"{r['rate_other']:.0f}% of {int(r['n_other'])}" if r["n_other"] else "None"
        shift = f"{r['shift']:+.0f}" if pd.notna(r["shift"]) else "None"
        table_rows.append([cat, own, other, shift, pattern_badge(r["label"])])
    if table_rows:
        html_table(["Type of vote", "Own party's president", "Other party's president", "Shift", "Pattern"], table_rows,
                   raw_cols=(4,), muted_cols=(1, 2))
        st.caption("The first two columns count every vote. The shift compares only matched votes: the same type of "
                   "vote, cast when the member's party was in the same position in the chamber.")
        st.page_link("pages/9_How_It_Works.py", label="How this is measured →")
    else:
        st.caption("This member cast no Yea or Nay votes on debt limit, funding, disaster aid or war powers bills in this data.")

    # Party unity over time
    if len(scored) > 1:
        st.subheader("Party unity over time")
        compare_party = caucus if pd.notna(caucus) else member["party"]
        avg = (df[df["caucus"] == compare_party].groupby(["congress", "chamber"])["party_unity_pct"].mean()
               .reset_index().rename(columns={"party_unity_pct": "party_avg"}))
        hist = scored.merge(avg, on=["congress", "chamber"], how="left")
        fig_h = px.line(hist, x="congress", y=["party_unity_pct", "party_avg"], markers=True,
                        labels={"congress": "Congress", "value": "Party Unity %", "variable": ""},
                        color_discrete_sequence=[ACCENT, MUTED])
        names = {"party_unity_pct": short, "party_avg": f"{compare_party} average, same chamber"}
        fig_h.for_each_trace(lambda t: t.update(name=names.get(t.name, t.name)))
        fig_h.update_layout(height=360, xaxis=dict(dtick=1), legend=dict(orientation="h", y=-0.25, x=0))
        show_chart(fig_h, f"Party unity across Congresses: {display_name(member['name'])}",
                   f"party_unity_history_{short.lower().replace(' ', '_')}")

    # How often they voted with each president's stated position (White House statements, 2009 on)
    sup_rows = []
    for (cong, cham), _ in rows.groupby(["congress", "chamber"]):
        ps = president_support(int(cong), cham)
        if ps.empty:
            continue
        ps = ps.merge(df[(df["congress"] == cong) & (df["chamber"] == cham)][["icpsr", "caucus"]], on="icpsr", how="left")
        mine = ps[ps["icpsr"] == icpsr]
        peers = ps[(ps["caucus"] == caucus) & (ps["votes"] > 0)]
        for pres, grp in mine.groupby("president", sort=False):
            pp = peers[peers["president"] == pres]
            sup_rows.append({"president": pres, "president_party": grp["president_party"].iloc[0],
                             "votes": int(grp["votes"].sum()), "agreed": int(grp["agreed"].sum()),
                             "peer_votes": int(pp["votes"].sum()), "peer_agreed": int(pp["agreed"].sum())})
    sup = pd.DataFrame(sup_rows)
    if not sup.empty:
        sup = sup.groupby(["president", "president_party"], sort=False).sum().reset_index()
        sup = sup[sup["votes"] > 0]
    if not sup.empty:
        st.subheader("Voted with the president's stated position")
        st.markdown("Bills where the White House published a position before the vote (2009 on). This shows whose "
                    "positions this member sided with. It is **not** a consistency score: agreeing more with one "
                    "party's presidents can simply reflect a member's views.")
        metric_row([(f"{r.president} ({r.president_party[0]})", f"{r.agreed / r.votes * 100:.0f}%",
                     f"{r.agreed} of {r.votes} votes · {caucus or member['party']} average "
                     f"{r.peer_agreed / r.peer_votes * 100:.0f}%" if r.peer_votes else f"{r.agreed} of {r.votes} votes")
                    for r in sup.itertuples()])

    # Where they sit within their party
    peers = df[(df["congress"] == member["congress"]) & (df["chamber"] == member["chamber"])
               & (df["party"] == member["party"])]
    if len(peers) > 5 and pd.notna(ideo):
        st.subheader("Where they sit in their party")
        fig = px.histogram(peers, x="nominate_dim1", nbins=25, labels={"nominate_dim1": "Ideology score (DW-NOMINATE)"},
                           color_discrete_sequence=[PARTY_COLORS.get(member["party"], MUTED)])
        fig.add_vline(x=ideo, line_dash="dash", line_color=ACCENT, annotation_text=short, annotation_position="top")
        fig.update_layout(height=340, yaxis_title="Members")
        show_chart(fig, f"{short} among {member['party']}s in the {member['chamber']}, {ordinal(member['congress'])} Congress",
                   f"ideology_position_{short.lower().replace(' ', '_')}_{int(member['congress'])}")
else:
    st.info("Start typing a last name to see a member's profile, or browse everyone below.")

# ---------------------------------------------------------------------------
# Browse
# ---------------------------------------------------------------------------
st.write("")
with st.expander("Browse all members in a Congress", expanded=not pick):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        congress = st.selectbox("Congress", sorted(df["congress"].unique(), reverse=True), key="me_cong",
                                format_func=ordinal)
    with c2:
        chamber = st.selectbox("Chamber", ["All", "House", "Senate"], key="me_cham")
    with c3:
        party_filter = st.selectbox("Party", ["All", "Democrat", "Republican", "Independent"], key="me_party")
    with c4:
        search = st.text_input("Name or state", "", key="me_search", placeholder="e.g. Smith or TX")
    filtered = df[df["congress"] == congress]
    if chamber != "All":
        filtered = filtered[filtered["chamber"] == chamber]
    if party_filter != "All":
        filtered = filtered[filtered["party"] == party_filter]
    if search:
        filtered = filtered[filtered["name"].str.contains(search, case=False, na=False)
                            | filtered["state_abbrev"].str.contains(search, case=False, na=False)]
    st.caption(f"{len(filtered)} members")
    st.dataframe(
        filtered[["name", "chamber", "state_abbrev", "party", "party_unity_pct", "unity_votes_cast", "nominate_dim1",
                  "cohesion_proxy"]].rename(columns={
            "name": "Name", "chamber": "Chamber", "state_abbrev": "State", "party": "Party",
            "party_unity_pct": "Party Unity %", "unity_votes_cast": "Party-Line Votes Cast",
            "nominate_dim1": "Ideology Score", "cohesion_proxy": "Cohesion Proxy"}).sort_values("Name"),
        width="stretch", height=420, hide_index=True,
    )

st.markdown("---")
st.caption("Party unity % is the share of party-line votes (a majority of Democrats opposed a majority of Republicans) "
           "on which the member voted with their own party's majority, computed from Voteview roll-call records. "
           "Ideology scores are DW-NOMINATE first-dimension estimates. The cohesion proxy reflects distance from the "
           "party median within the same chamber and Congress.")
