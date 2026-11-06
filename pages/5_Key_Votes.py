"""Key Votes – party unity rates plus high-profile vote series with party splits and members who broke ranks."""

import textwrap

import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
from chart_utils import show_chart, ordinal, chamber_label, PARTY_COLORS, VOTE_COLORS

DATA_DIR = Path(__file__).parent.parent / "data"
SERIES_ORDER = ["Funding & Appropriations", "Cabinet Confirmations", "Biggest Party Breaks"]
SERIES_RULES = {
    "Funding & Appropriations": "Final passage votes on appropriations bills and continuing resolutions (stopgap funding). "
                                "Procedural rule votes and authorization bills are not included.",
    "Cabinet Confirmations": "Senate confirmation votes for the heads of the 15 executive departments and the Attorney General. "
                             "Nominees confirmed by voice vote have no roll call and do not appear.",
    "Biggest Party Breaks": "The 10 party-unity votes in each chamber (final passage or nomination votes only) where the most "
                            "members voted against their own party's majority.",
}


@st.cache_data
def load_data():
    members = pd.read_csv(DATA_DIR / "members_processed.csv")
    summary = pd.read_csv(DATA_DIR / "unity_summary.csv")
    votes = pd.read_csv(DATA_DIR / "key_votes.csv")
    defectors = pd.read_csv(DATA_DIR / "key_vote_defectors.csv")
    votes["label"] = votes["vote_desc"].fillna(votes["bill_number"].fillna("") + " " + votes["vote_question"].fillna(""))
    # Hand-picked votes carry a short plain-language note; use it as the name when present
    votes["label"] = votes["note"].where(votes["note"].notna() & (votes["note"].astype(str).str.strip() != ""), votes["label"])
    return members, summary, votes, defectors


members, summary, votes, defectors = load_data()



def split(y, n) -> str:
    return f"{int(y)}–{int(n)}"


st.title("Key Votes & Party Unity")
st.markdown("Party-unity rates, plus how each party split on high-profile votes and exactly who voted against their own party.")

f1, f2 = st.columns(2)
with f1:
    congress = st.selectbox("Congress", sorted(members["congress"].unique(), reverse=True), key="kv_cong")
with f2:
    chamber = st.selectbox("Chamber", ["Both", "House", "Senate"], key="kv_cham")

# ---------------------------------------------------------------------------
# Party unity summary
# ---------------------------------------------------------------------------
current = members[(members["congress"] == congress) & members["party"].isin(["Democrat", "Republican"])]
if chamber != "Both":
    current = current[current["chamber"] == chamber]
s = summary[summary["congress"] == congress]
n_unity = int(s["party_unity_votes"].sum() if chamber == "Both" else s.loc[s["chamber"] == chamber, "party_unity_votes"].sum())

st.subheader(f"{ordinal(congress)} Congress: Party Unity Rates")
st.caption(
    "Party-unity votes are roll calls where a majority of Democrats opposed a majority of Republicans. "
    "The rate is the share of those votes on which a member voted with their own party's majority. "
    f"{n_unity:,} party-unity votes identified from Voteview roll-call data."
)

unity = current.dropna(subset=["party_unity_pct"])
if not unity.empty:
    c1, c2, c3, c4 = st.columns(4)
    dem = unity.loc[unity["party"] == "Democrat", "party_unity_pct"]
    rep = unity.loc[unity["party"] == "Republican", "party_unity_pct"]
    c1.metric("Dem. mean unity", f"{dem.mean():.1f}%")
    c2.metric("Rep. mean unity", f"{rep.mean():.1f}%")
    c3.metric("Dem. median", f"{dem.median():.1f}%")
    c4.metric("Rep. median", f"{rep.median():.1f}%")

    fig = px.box(
        unity, x="party", y="party_unity_pct", color="party", points="all", hover_name="name",
        color_discrete_map=PARTY_COLORS, labels={"party_unity_pct": "Party Unity %", "party": "Party"},
    )
    fig.update_layout(showlegend=False, height=400, margin=dict(l=40, r=40, t=20, b=40))
    show_chart(fig, f"Party unity rates, {ordinal(congress)} Congress, {chamber_label(chamber)}", f"party_unity_{congress}_{chamber.lower()}")

    with st.expander("Members with the lowest party-unity rates"):
        low = unity.nsmallest(15, "party_unity_pct")[
            ["name", "chamber", "state_abbrev", "party", "party_unity_pct", "votes_with_party", "unity_votes_cast"]
        ].rename(columns={"name": "Name", "chamber": "Chamber", "state_abbrev": "State", "party": "Party",
                          "party_unity_pct": "Unity %", "votes_with_party": "With Party", "unity_votes_cast": "Of"})
        st.dataframe(low, width="stretch", hide_index=True)

# ---------------------------------------------------------------------------
# High-profile vote series
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("High-Profile Vote Series")
st.caption("Each series is selected by a published rule, so anyone can check why a vote is included. "
           "Party columns show Yea–Nay. Independents are listed separately.")

kv = votes[votes["congress"] == congress]
if chamber != "Both":
    kv = kv[kv["chamber"] == chamber]

series_names = [s for s in SERIES_ORDER if s in set(kv["series"])] + sorted(set(kv["series"]) - set(SERIES_ORDER))
if not series_names:
    st.info("No key votes in this selection.")
else:
    tabs = st.tabs(series_names)
    for tab, name in zip(tabs, series_names):
        with tab:
            sv = kv[kv["series"] == name].sort_values(["date", "rollnumber"], ascending=False)
            st.caption(SERIES_RULES.get(name, "Hand-picked roll calls listed in data/key_votes_custom.csv."))
            table = pd.DataFrame({
                "Date": sv["date"],
                "Chamber": sv["chamber"],
                "Roll Call": sv["rollnumber"],
                "Vote": sv["label"],
                "Result": sv["vote_result"],
                "Total": [split(y, n) for y, n in zip(sv["yea_count"], sv["nay_count"])],
                "Dem.": [split(y, n) for y, n in zip(sv["dem_yea"], sv["dem_nay"])],
                "Rep.": [split(y, n) for y, n in zip(sv["rep_yea"], sv["rep_nay"])],
                "Ind.": [split(y, n) if y + n else "" for y, n in zip(sv["other_yea"], sv["other_nay"])],
                "Broke With Party": (sv["dem_defectors"] + sv["rep_defectors"]).astype(int),
            })
            st.dataframe(table, width="stretch", hide_index=True,
                         column_config={"Vote": st.column_config.TextColumn(width="large")})

            # Detail for one vote
            labels = {f"{d} · {c} roll call {r} · {lbl[:90]}": i for i, d, c, r, lbl in
                      zip(sv.index, sv["date"], sv["chamber"], sv["rollnumber"], sv["label"])}
            pick = st.selectbox("Look at one vote", list(labels), key=f"kv_pick_{name}")
            v = sv.loc[labels[pick]]

            st.markdown(f"**{v['label']}**  \n{v['vote_question']} · {v['vote_result']} · "
                        f"{int(v['yea_count'])} Yea, {int(v['nay_count'])} Nay")
            if pd.notna(v.get("note")) and str(v.get("note")).strip():
                st.caption(v["note"])

            bars = pd.DataFrame({
                "Party": ["Democrat", "Democrat", "Republican", "Republican", "Independent", "Independent"],
                "Vote": ["Yea", "Nay"] * 3,
                "Members": [v["dem_yea"], v["dem_nay"], v["rep_yea"], v["rep_nay"], v["other_yea"], v["other_nay"]],
            })
            bars = bars[bars.groupby("Party")["Members"].transform("sum") > 0]
            fig_v = px.bar(bars, y="Party", x="Members", color="Vote", orientation="h", text="Members",
                           color_discrete_map=VOTE_COLORS,
                           category_orders={"Party": ["Democrat", "Republican", "Independent"], "Vote": ["Yea", "Nay"]})
            fig_v.update_layout(height=230, margin=dict(l=40, r=40, t=10, b=30), legend_title_text="")
            show_chart(fig_v, f"{textwrap.shorten(v['label'], 70, placeholder='…')} ({v['chamber']}, {v['date']})", f"vote_{v['chamber'].lower()}_{congress}_{int(v['rollnumber'])}", key=f"kv_chart_{name}")

            broke = defectors[(defectors["congress"] == congress) & (defectors["chamber"] == v["chamber"])
                              & (defectors["rollnumber"] == v["rollnumber"])]
            if broke.empty:
                st.caption("No Democrat or Republican voted against their party's majority on this vote.")
            else:
                st.markdown(f"**Voted against their party's majority ({len(broke)})**")
                st.dataframe(
                    broke.sort_values(["party", "name"])[["name", "party", "state_abbrev", "vote", "party_position"]]
                    .rename(columns={"name": "Name", "party": "Party", "state_abbrev": "State",
                                     "vote": "Their Vote", "party_position": "Party Majority"}),
                    width="stretch", hide_index=True, height=min(38 + 35 * len(broke), 400),
                )

st.markdown("---")
st.caption("Source: Voteview roll-call, vote and member files. Counts include only actual Yea and Nay floor votes. "
           "Party majority positions use Democrats and Republicans only; ties are not counted as a party position.")
