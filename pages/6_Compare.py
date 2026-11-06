"""Compare Members – two members side by side: party unity over time, how often they voted
the same way while serving together, and the key votes where they split."""

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from pathlib import Path
from chart_utils import show_chart, ordinal, PAIR_COLORS

DATA_DIR = Path(__file__).parent.parent / "data"
MATRIX_DIR = DATA_DIR / "matrices"
PREFIX = {"House": "H", "Senate": "S"}
VOTE_WORD = {1: "Yea", -1: "Nay", 0: "Did not vote"}


@st.cache_data
def load():
    members = pd.read_csv(DATA_DIR / "members_processed.csv")
    key_votes = pd.read_csv(DATA_DIR / "key_votes.csv")
    key_votes["label"] = key_votes["vote_desc"].fillna(key_votes["bill_number"].fillna("") + " " + key_votes["vote_question"].fillna(""))
    key_votes["label"] = key_votes["note"].where(key_votes["note"].notna() & (key_votes["note"].astype(str).str.strip() != ""), key_votes["label"])
    return members, key_votes


@st.cache_data
def load_matrix(congress: int, chamber: str):
    path = MATRIX_DIR / f"{PREFIX[chamber]}{congress}.npz"
    if not path.exists():
        return None
    with np.load(path) as f:
        return f["icpsr"], f["rollnumber"], f["votes"]


@st.cache_data
def unity_rollcalls(congress: int, chamber: str) -> np.ndarray:
    """Boolean mask over the matrix columns: True where a majority of voting Democrats
    opposed a majority of voting Republicans."""
    members, _ = load()
    icpsr, _, votes = load_matrix(congress, chamber)
    party = members[(members["congress"] == congress) & (members["chamber"] == chamber)].set_index("icpsr")["party"]
    p = party.reindex(icpsr).to_numpy()

    def position(rows):
        yea = (votes[rows] == 1).sum(axis=0)
        nay = (votes[rows] == -1).sum(axis=0)
        return np.sign(yea - nay)  # 1 Yea, -1 Nay, 0 tie or no votes

    d, r = position(p == "Democrat"), position(p == "Republican")
    return (d != 0) & (r != 0) & (d != r)


members, key_votes = load()

st.title("Compare Members")
st.markdown("Pick any two members to see their party unity side by side, how often they voted the same way "
            "while serving together, and the key votes where they split.")

# One entry per person (Voteview ID), labeled with their most recent party, state and chamber
latest = members.sort_values("congress").groupby("icpsr").tail(1)
latest = latest.assign(label=latest["name"] + " (" + latest["party"].str[0] + "-" + latest["state_abbrev"] + ", "
                       + latest["chamber"] + ")")
dupes = latest["label"].duplicated(keep=False)
latest.loc[dupes, "label"] = latest.loc[dupes, "label"] + " #" + latest.loc[dupes, "icpsr"].astype(str)
options = dict(zip(latest.sort_values("label")["label"], latest.sort_values("label")["icpsr"]))

c1, c2 = st.columns(2)
with c1:
    a_label = st.selectbox("First member", list(options), index=None, placeholder="Type a name…", key="cmp_a")
with c2:
    b_label = st.selectbox("Second member", list(options), index=None, placeholder="Type a name…", key="cmp_b")

if not a_label or not b_label:
    st.info("Choose two members to compare. Start typing a last name to search.")
    st.stop()
if a_label == b_label:
    st.warning("Pick two different members.")
    st.stop()

a_id, b_id = options[a_label], options[b_label]
a_rows = members[members["icpsr"] == a_id].sort_values("congress")
b_rows = members[members["icpsr"] == b_id].sort_values("congress")
a_name, b_name = a_rows["name"].iloc[-1].split(",")[0], b_rows["name"].iloc[-1].split(",")[0]
if a_name == b_name:
    a_name, b_name = a_label.split(" (")[0], b_label.split(" (")[0]

# ---------------------------------------------------------------------------
# Party unity side by side
# ---------------------------------------------------------------------------
m1, m2 = st.columns(2)
for col, rows, name in ((m1, a_rows, a_name), (m2, b_rows, b_name)):
    last = rows.iloc[-1]
    with col:
        st.markdown(f"**{last['name']}**  \n{last['party']}, {last['state_abbrev']} · "
                    f"{', '.join(sorted(rows['chamber'].unique()))} · "
                    f"{ordinal(rows['congress'].min())}–{ordinal(rows['congress'].max())} Congress")
        scored = rows.dropna(subset=["party_unity_pct"])
        if scored.empty:
            st.metric("Party unity, latest Congress", "—")
        else:
            st.metric(f"Party unity, {ordinal(scored['congress'].iloc[-1])} Congress",
                      f"{scored['party_unity_pct'].iloc[-1]:.1f}%",
                      help=f"Average across all Congresses shown: {scored['party_unity_pct'].mean():.1f}%")

history = pd.concat([
    a_rows.assign(Member=a_name), b_rows.assign(Member=b_name)
]).dropna(subset=["party_unity_pct"])
if not history.empty:
    fig = px.line(history, x="congress", y="party_unity_pct", color="Member", markers=True,
                  hover_data={"chamber": True, "party": True},
                  color_discrete_sequence=PAIR_COLORS,
                  labels={"congress": "Congress", "party_unity_pct": "Party Unity %"})
    fig.update_layout(height=380, xaxis=dict(dtick=1), legend_title_text="")
    show_chart(fig, f"Party unity across Congresses: {a_name} vs. {b_name}",
               f"compare_unity_{a_name.lower()}_{b_name.lower()}".replace(" ", "_"))

# ---------------------------------------------------------------------------
# Votes while serving together
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("When they served together")

shared = a_rows.merge(b_rows, on=["congress", "chamber"], suffixes=("_a", "_b"))[["congress", "chamber"]]
if shared.empty:
    st.info(f"{a_name} and {b_name} never served in the same chamber during the same Congress in this data, "
            "so their individual votes can't be compared. The party unity chart above still applies.")
    st.stop()

summary_rows, splits = [], []
for cong, cham in shared.itertuples(index=False):
    mat = load_matrix(cong, cham)
    if mat is None:
        continue
    icpsr, rolls, votes = mat
    ia, ib = np.where(icpsr == a_id)[0], np.where(icpsr == b_id)[0]
    if not len(ia) or not len(ib):
        continue
    va, vb = votes[ia[0]], votes[ib[0]]
    both = (va != 0) & (vb != 0)
    unity = unity_rollcalls(cong, cham)
    summary_rows.append({
        "Congress": ordinal(cong),
        "Chamber": cham,
        "Votes both cast": int(both.sum()),
        "Voted the same way": f"{(va[both] == vb[both]).mean() * 100:.1f}%" if both.any() else "—",
        "Party-unity votes both cast": int((both & unity).sum()),
        "Same way on party-unity votes": f"{(va[both & unity] == vb[both & unity]).mean() * 100:.1f}%" if (both & unity).any() else "—",
    })
    kv = key_votes[(key_votes["congress"] == cong) & (key_votes["chamber"] == cham)].drop_duplicates("rollnumber")
    col = {r: i for i, r in enumerate(rolls)}
    for _, v in kv.iterrows():
        i = col.get(int(v["rollnumber"]))
        if i is None:
            continue
        if va[i] != 0 and vb[i] != 0 and va[i] != vb[i]:
            series = ", ".join(sorted(key_votes.loc[(key_votes["congress"] == cong) & (key_votes["chamber"] == cham)
                                                    & (key_votes["rollnumber"] == v["rollnumber"]), "series"]))
            splits.append({"Date": v["date"], "Chamber": cham, "Vote": v["label"], "Series": series,
                           a_name: VOTE_WORD[int(va[i])], b_name: VOTE_WORD[int(vb[i])], "Result": v["vote_result"]})

st.dataframe(pd.DataFrame(summary_rows), width="stretch", hide_index=True)
st.caption("Counts only roll calls where both members actually voted Yea or Nay. A party-unity vote is one where "
           "most Democrats and most Republicans voted on opposite sides.")

st.subheader("Key votes where they split")
if splits:
    st.caption(f"{len(splits)} key votes where {a_name} and {b_name} voted on opposite sides. "
               "Key votes are the series listed on the Key Votes page.")
    st.dataframe(pd.DataFrame(splits).sort_values("Date", ascending=False), width="stretch", hide_index=True,
                 column_config={"Vote": st.column_config.TextColumn(width="large")})
else:
    st.caption("They voted the same way on every key vote they both cast while serving together.")

st.markdown("---")
st.caption("Source: Voteview roll-call records. Only actual Yea and Nay floor votes are counted.")
