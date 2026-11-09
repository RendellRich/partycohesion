"""Key Votes: high-profile vote series with each party's split and the members who broke ranks, then each
party's unity rate. Layout follows the "Key Votes" mockup in the PartyCohesion Figma design system."""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from chart_utils import PARTY_COLORS, chamber_label, ordinal, show_chart
from ui import explainer, inject_css, intro, metric_row, vote_card
from vote_index import voteview_url

DATA_DIR = Path(__file__).parent.parent / "data"
SERIES_ORDER = ["Funding & Appropriations", "Cabinet Confirmations", "Biggest Party Breaks", "Major Legislation"]
SERIES_RULES = {
    "Funding & Appropriations": "Final passage votes on appropriations bills and continuing resolutions (stopgap "
                                "funding). Procedural rule votes and authorization bills are not included.",
    "Cabinet Confirmations": "Senate confirmation votes for the heads of the 15 executive departments and the Attorney "
                             "General. Nominees confirmed by voice vote have no roll call and do not appear.",
    "Biggest Party Breaks": "The 10 party-line votes in each chamber (final passage or nomination votes only) where the "
                            "most members voted against their own party's majority.",
    "Major Legislation": "Hand-picked votes on widely covered bills, listed in data/key_votes_custom.csv. Unlike the "
                         "other series this list is chosen by hand, and so far it covers only the 119th Congress.",
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


def split(y, n) -> str:
    return f"{int(y)}–{int(n)}"


def congress_label(c: int) -> str:
    return f"{ordinal(c)} ({2 * c + 1787} to {2 * c + 1788})"


inject_css()
members, summary, votes, defectors = load_data()

st.title("Key Votes")
intro("The highest-profile votes in each Congress, how each party split, and exactly who voted against their own "
      "party. Three series are picked by a published rule, and one hand-picked list is labeled as such.")
explainer('These are the highest-profile votes of each Congress. The bars show how each party split, and the '
          'names show who crossed party lines. A member may cross for their district, their beliefs or a change '
          "to the bill, and the vote alone doesn't say which.")

f1, f2, _ = st.columns([1.2, 1, 0.8])
with f1:
    congress = st.selectbox("Congress", sorted(members["congress"].unique(), reverse=True), key="kv_cong",
                            format_func=congress_label)
with f2:
    chamber = st.selectbox("Chamber", ["Both", "House", "Senate"], key="kv_cham", format_func=chamber_label)

# ---------------------------------------------------------------------------
# High-profile vote series
# ---------------------------------------------------------------------------
kv = votes[votes["congress"] == congress]
if chamber != "Both":
    kv = kv[kv["chamber"] == chamber]

series_names = [s for s in SERIES_ORDER if s in set(kv["series"])] + sorted(set(kv["series"]) - set(SERIES_ORDER))
if not series_names:
    st.info("No key votes in this selection.")
else:
    counts = kv["series"].value_counts()
    tabs = st.tabs([f"{n} ({counts[n]})" for n in series_names])
    for tab, name in zip(tabs, series_names):
        with tab:
            sv = kv[kv["series"] == name].sort_values(["date", "rollnumber"], ascending=False)
            st.caption(SERIES_RULES.get(name, "Hand-picked roll calls listed in data/key_votes_custom.csv."))
            labels = {f"{d} · {c} roll call {r} · {lbl[:90]}": i for i, d, c, r, lbl in
                      zip(sv.index, sv["date"], sv["chamber"], sv["rollnumber"], sv["label"])}
            pick = st.selectbox("Look at one vote", list(labels), key=f"kv_pick_{name}")
            v = sv.loc[labels[pick]]
            broke = defectors[(defectors["congress"] == congress) & (defectors["chamber"] == v["chamber"])
                              & (defectors["rollnumber"] == v["rollnumber"])]
            vote_card(v, broke, link=voteview_url(congress, v["chamber"], v["rollnumber"]))

            st.subheader(f"All {len(sv)} votes in this series")
            st.dataframe(pd.DataFrame({
                "Date": sv["date"],
                "Chamber": sv["chamber"],
                "Roll Call": sv["rollnumber"],
                "Vote": sv["label"],
                "Result": sv["vote_result"],
                "Total": [split(y, n) for y, n in zip(sv["yea_count"], sv["nay_count"])],
                "Dem.": [split(y, n) for y, n in zip(sv["dem_yea"], sv["dem_nay"])],
                "Rep.": [split(y, n) for y, n in zip(sv["rep_yea"], sv["rep_nay"])],
                "Ind.": [split(y, n) if y + n else "" for y, n in zip(sv["other_yea"], sv["other_nay"])],
                "Broke Ranks": (sv["dem_defectors"] + sv["rep_defectors"]).astype(int),
            }), width="stretch", hide_index=True, column_config={"Vote": st.column_config.TextColumn(width="large")})
            st.caption("Party columns show Yea–Nay. Independents are listed separately.")

# ---------------------------------------------------------------------------
# Party unity summary
# ---------------------------------------------------------------------------
st.markdown("---")
current = members[(members["congress"] == congress) & members["party"].isin(["Democrat", "Republican"])]
if chamber != "Both":
    current = current[current["chamber"] == chamber]
s = summary[summary["congress"] == congress]
if chamber != "Both":
    s = s[s["chamber"] == chamber]
n_unity = int(s["party_unity_votes"].sum())

st.subheader("How united was each party?")
st.markdown(f"On the {n_unity:,} party-line votes in the {ordinal(congress)} Congress (most Democrats against most "
            "Republicans), the share of the time members sided with their own party.")
unity = current.dropna(subset=["party_unity_pct"])
if not unity.empty:
    dem = unity.loc[unity["party"] == "Democrat", "party_unity_pct"]
    rep = unity.loc[unity["party"] == "Republican", "party_unity_pct"]
    split_note = ", ".join(f"{int(r.party_unity_votes):,} {r.chamber}" for r in s.itertuples())
    metric_row([("Democrats, average", f"{dem.mean():.1f}%", f"Median {dem.median():.1f}%"),
                ("Republicans, average", f"{rep.mean():.1f}%", f"Median {rep.median():.1f}%"),
                ("Party-line votes", f"{n_unity:,}", split_note)])
    st.write("")
    with st.expander("Every member's unity rate, and the 15 lowest"):
        fig = px.box(unity, x="party", y="party_unity_pct", color="party", points="all", hover_name="name",
                     color_discrete_map=PARTY_COLORS, labels={"party_unity_pct": "Party Unity %", "party": "Party"})
        fig.update_layout(showlegend=False, height=400)
        show_chart(fig, f"Party unity rates, {ordinal(congress)} Congress, {chamber_label(chamber)}",
                   f"party_unity_{congress}_{chamber.lower()}")
        low = unity.nsmallest(15, "party_unity_pct")[
            ["name", "chamber", "state_abbrev", "party", "party_unity_pct", "votes_with_party", "unity_votes_cast"]
        ].rename(columns={"name": "Name", "chamber": "Chamber", "state_abbrev": "State", "party": "Party",
                          "party_unity_pct": "Unity %", "votes_with_party": "With Party", "unity_votes_cast": "Of"})
        st.dataframe(low, width="stretch", hide_index=True)

st.markdown("---")
st.caption("Source: Voteview roll-call, vote and member files. Counts include only actual Yea and Nay floor votes. "
           "Party majority positions use Democrats and Republicans only; ties are not counted as a party position.")
