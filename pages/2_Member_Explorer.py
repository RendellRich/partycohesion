"""Member Explorer – look up individual members."""

import streamlit as st
import numpy as np
import pandas as pd
import plotly.express as px
from pathlib import Path
from chart_utils import show_chart, ordinal, chamber_label


DATA_PATH = Path(__file__).parent.parent / "data" / "members_processed.csv"

@st.cache_data
def load_members():
    return pd.read_csv(DATA_PATH)

df = load_members()

DATA_DIR = DATA_PATH.parent
PREFIX = {"House": "H", "Senate": "S"}


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

st.title("Member Explorer")
st.markdown("Search any member of Congress from the 110th (2007) to the present and see how often they voted with their own party, where they sit ideologically, and how that changed over time.")

# Filters
c1, c2, c3 = st.columns(3)
with c1:
    congress = st.selectbox("Congress", options=sorted(df["congress"].unique(), reverse=True), index=0, key="me_cong")
with c2:
    chamber = st.selectbox("Chamber", options=["All", "House", "Senate"], index=0, key="me_cham")
with c3:
    party_filter = st.selectbox("Party", options=["All", "Democrat", "Republican", "Independent"], index=0, key="me_party")

filtered = df[df["congress"] == congress].copy()
if chamber != "All":
    filtered = filtered[filtered["chamber"] == chamber]
if party_filter != "All":
    filtered = filtered[filtered["party"] == party_filter]

# Search
search = st.text_input("Search by name or state (e.g. 'Smith' or 'TX')", "")
if search:
    mask = (
        filtered["name"].str.contains(search, case=False, na=False)
        | filtered["state_abbrev"].str.contains(search, case=False, na=False)
    )
    filtered = filtered[mask]

st.caption(f"Showing {len(filtered)} members")

# Table
display_cols = ["name", "chamber", "state_abbrev", "party", "party_unity_pct", "unity_votes_cast", "nominate_dim1", "cohesion_proxy"]
rename = {
    "name": "Name",
    "chamber": "Chamber",
    "state_abbrev": "State",
    "party": "Party",
    "nominate_dim1": "Ideology (Dim 1)",
    "cohesion_proxy": "Cohesion Proxy",
    "party_unity_pct": "Party Unity %",
    "unity_votes_cast": "Party-Unity Votes Cast",
}
table = filtered[display_cols].rename(columns=rename).sort_values("Name")

st.dataframe(
    table,
    width="stretch",
    height=420,
    hide_index=True,
)

st.markdown("---")

# Detail view
st.subheader("Member Detail")
if len(filtered) > 0:
    names = sorted(filtered["name"].unique())
    selected = st.selectbox("Select a member for detail", options=names)

    member = filtered[filtered["name"] == selected].iloc[0]

    d2, d3, d4, d5 = st.columns(4)
    with d2:
        st.metric("Party-State", f"{member['party'][0]}-{member['state_abbrev']}", help=member["party"])
    with d3:
        st.metric("Party Unity %", f"{member['party_unity_pct']:.1f}%" if pd.notna(member["party_unity_pct"]) else "—")
    with d4:
        st.metric("Ideology (Dim 1)", f"{member['nominate_dim1']:.3f}")
    with d5:
        st.metric("Cohesion Proxy", f"{member['cohesion_proxy']:.1f}" if pd.notna(member["cohesion_proxy"]) else "—")

    caucus = member.get("caucus")
    party_text = member["party"] if member["party"] in ("Democrat", "Republican") or pd.isna(caucus) else \
        f"{member['party']} (caucuses with {caucus}s)"
    if pd.notna(member["party_unity_pct"]):
        st.markdown(
            f"**{party_text}, {member['chamber']}**  |  Voted with the {caucus} majority on "
            f"**{int(member['votes_with_party'])} of {int(member['unity_votes_cast'])}** party-unity votes."
        )
    else:
        st.markdown(
            f"**{party_text}, {member['chamber']}**  |  No party unity rate: members are scored with the party they belong to "
            "or caucus with, and must have cast at least one party-unity vote."
        )

    # Party unity across every Congress this member served in (same Voteview ID)
    history = df[(df["icpsr"] == member["icpsr"]) & df["party_unity_pct"].notna()].sort_values("congress")
    if len(history) > 1:
        party_avg = (
            df[df["party"] == member["party"]]
            .groupby(["congress", "chamber"])["party_unity_pct"]
            .mean()
            .reset_index()
            .rename(columns={"party_unity_pct": "party_avg"})
        )
        history = history.merge(party_avg, on=["congress", "chamber"], how="left")
        fig_h = px.line(
            history,
            x="congress",
            y=["party_unity_pct", "party_avg"],
            markers=True,
            labels={"congress": "Congress", "value": "Party Unity %", "variable": ""},
            title=f"Party unity across Congresses: {selected}",
            color_discrete_sequence=["#e03131", "#868e96"],
        )
        names = {"party_unity_pct": selected.split(",")[0], "party_avg": f"{member['party']} average"}
        fig_h.for_each_trace(lambda t: t.update(name=names.get(t.name, t.name)))
        fig_h.update_layout(height=360, margin=dict(l=40, r=40, t=50, b=40), xaxis=dict(dtick=1))
        show_chart(fig_h, f"Party unity across Congresses: {selected}", f"party_unity_history_{selected.split(',')[0].lower().replace(' ', '_')}")

    # How often they voted with each president's stated position (White House statements, 2009 on)
    rows = []
    for (cong, cham), _ in df[df["icpsr"] == member["icpsr"]].groupby(["congress", "chamber"]):
        ps = president_support(int(cong), cham)
        if ps.empty:
            continue
        ps = ps.merge(df[(df["congress"] == cong) & (df["chamber"] == cham)][["icpsr", "caucus"]], on="icpsr", how="left")
        mine = ps[ps["icpsr"] == member["icpsr"]]
        same = ps[(ps["caucus"] == member.get("caucus")) & (ps["votes"] > 0)]
        for pres, grp in mine.groupby("president", sort=False):
            peers = same[same["president"] == pres]
            rows.append({"president": pres, "president_party": grp["president_party"].iloc[0], "votes": int(grp["votes"].sum()),
                         "agreed": int(grp["agreed"].sum()), "peer_votes": int(peers["votes"].sum()), "peer_agreed": int(peers["agreed"].sum())})
    if rows:
        sup = pd.DataFrame(rows).groupby(["president", "president_party"], sort=False).sum().reset_index()
        sup = sup[sup["votes"] > 0]
    if rows and not sup.empty:
        st.markdown("**Voted with the president's stated position**")
        st.caption("On bills where the White House issued an official position before the vote (2009 on). This shows whose "
                   "positions a member sided with. It is **not** a consistency score: agreeing more with one party's presidents "
                   "can simply reflect a member's views. For consistency on the same question, see Position Flips.")
        st.dataframe(pd.DataFrame({
            "President": sup["president"] + " (" + sup["president_party"].str[0] + ")",
            "Votes with a White House position": sup["votes"],
            "Voted with the president": [f"{a} ({a / v * 100:.0f}%)" for a, v in zip(sup["agreed"], sup["votes"])],
            f"{member.get('caucus') or member['party']} average": [f"{a / v * 100:.0f}%" if v else "—"
                                                                  for a, v in zip(sup["peer_agreed"], sup["peer_votes"])],
        }), width="stretch", hide_index=True)

    # Context: where this member sits relative to their party
    party_members = df[
        (df["congress"] == congress)
        & (df["chamber"] == member["chamber"])
        & (df["party"] == member["party"])
    ]

    if len(party_members) > 5:
        fig = px.histogram(
            party_members,
            x="nominate_dim1",
            nbins=25,
            title=f"Ideology distribution of {member['party']}s in the {member['chamber']} ({congress}th)",
            labels={"nominate_dim1": "DW-NOMINATE Dimension 1"},
            color_discrete_sequence=["#5c7cfa"],
        )
        # Add vertical line for the selected member
        fig.add_vline(
            x=member["nominate_dim1"],
            line_dash="dash",
            line_color="#e03131",
            annotation_text=selected.split(",")[0],
            annotation_position="top",
        )
        fig.update_layout(height=380, margin=dict(l=40, r=40, t=50, b=40))
        show_chart(fig, f"{selected.split(',')[0]} among {member['party']}s in the {member['chamber']}, {ordinal(congress)} Congress", f"ideology_position_{selected.split(',')[0].lower().replace(' ', '_')}_{congress}")
else:
    st.info("No members match the current filters.")

st.markdown("---")
st.caption("Party unity % is the share of party-unity votes (a majority of Democrats opposed a majority of Republicans) on which the member voted with their own party's majority, computed from Voteview roll-call records. Ideology scores are DW-NOMINATE first-dimension estimates. The cohesion proxy reflects distance from the party median within the same chamber and Congress.")
