"""Compare Members: two members side by side. How often they voted the same way while serving together,
their party unity over time, and the key votes where they split. Layout follows the "Compare" mockup in
the PartyCohesion Figma design system."""

from html import escape
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from chart_utils import PAIR_COLORS, ordinal, show_chart
from flip_utils import add_chamber_control, flip_scores
from ui import STATES, card, display_name, html_table, inject_css, intro, last_name, metric_card, party_tag, pattern_badge

DATA_DIR = Path(__file__).parent.parent / "data"
MATRIX_DIR = DATA_DIR / "matrices"
PREFIX = {"House": "H", "Senate": "S"}
VOTE_WORD = {1: "Yea", -1: "Nay", 0: "Did not vote"}
FLIP_CATEGORIES = ["All categories", "Debt limit", "Stopgap funding", "Full-year funding", "Disaster aid", "War powers limits"]


@st.cache_data
def load():
    members = pd.read_csv(DATA_DIR / "members_processed.csv")
    key_votes = pd.read_csv(DATA_DIR / "key_votes.csv")
    key_votes["label"] = key_votes["vote_desc"].fillna(key_votes["bill_number"].fillna("") + " " + key_votes["vote_question"].fillna(""))
    key_votes["label"] = key_votes["note"].where(key_votes["note"].notna() & (key_votes["note"].astype(str).str.strip() != ""), key_votes["label"])
    flips = add_chamber_control(pd.read_csv(DATA_DIR / "flip_member_votes.csv"), members)
    return members, key_votes, flips


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
    members = load()[0]
    icpsr, _, votes = load_matrix(congress, chamber)
    party = members[(members["congress"] == congress) & (members["chamber"] == chamber)].set_index("icpsr")["party"]
    p = party.reindex(icpsr).to_numpy()

    def position(rows):
        yea = (votes[rows] == 1).sum(axis=0)
        nay = (votes[rows] == -1).sum(axis=0)
        return np.sign(yea - nay)  # 1 Yea, -1 Nay, 0 tie or no votes

    d, r = position(p == "Democrat"), position(p == "Republican")
    return (d != 0) & (r != 0) & (d != r)


def flip_cell(icpsr: int, category: str) -> str:
    """Pattern badge plus the shift and vote count, for one member and one kind of vote."""
    mv = flips[flips["icpsr"] == icpsr]
    s = flip_scores(mv, category)
    if s.empty:
        return '<span class="pc-body">No votes</span>'
    r = s.iloc[0]
    n = int(r["matched_own"] + r["matched_other"])
    if r["label"] == "Not enough votes":
        return f'<span class="pc-body">Not enough matched votes ({n})</span>'
    return f'{pattern_badge(r["label"])} <span class="pc-body">{r["shift"]:+.0f} · {n} votes compared</span>'


def member_card(rows: pd.DataFrame, color: str, newest: int) -> None:
    last = rows.iloc[-1]
    first_c, last_c = int(rows["congress"].min()), int(rows["congress"].max())
    end = "now" if last_c == newest else str(2 * last_c + 1788)
    place = (f"{STATES.get(last['state_abbrev'], last['state_abbrev'])} · {', '.join(sorted(rows['chamber'].unique()))} · "
             f"{ordinal(first_c)} to {ordinal(last_c)} Congress ({2 * first_c + 1787} to {end})"
             + (" · data starts in 2007" if first_c == int(members["congress"].min()) else ""))
    scored = rows.dropna(subset=["party_unity_pct"])
    if scored.empty:
        label, value, note = "Party unity", "None", "No party-line votes scored"
    else:
        u = scored.iloc[-1]
        label = f"Party unity, {ordinal(u['congress'])} Congress"
        value = f"{u['party_unity_pct']:.1f}%"
        note = f"{int(u['votes_with_party']):,} of {int(u['unity_votes_cast']):,} party-line votes"
    st.markdown(
        f'<div class="pc-card" style="border-top: 4px solid {color}">'
        f'<div class="pc-name">{escape(display_name(last["name"]))} {party_tag(last["party"])}</div>'
        f'<div class="pc-place">{escape(place)}</div>'
        f'<div class="pc-metric-label">{escape(label)}</div><div class="pc-metric-value">{escape(value)}</div>'
        f'<div class="pc-metric-note">{escape(note)}</div></div>', unsafe_allow_html=True)


inject_css()
members, key_votes, flips = load()
newest = int(members["congress"].max())

st.title("Compare Members")
intro("Pick any two members to see how often they voted the same way while serving together, their party unity side "
      "by side, and the key votes where they split.")

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
a_name, b_name = last_name(a_rows["name"].iloc[-1]), last_name(b_rows["name"].iloc[-1])
if a_name == b_name:
    a_name, b_name = display_name(a_rows["name"].iloc[-1]), display_name(b_rows["name"].iloc[-1])

m1, m2 = st.columns(2)
with m1:
    member_card(a_rows, PAIR_COLORS[0], newest)
with m2:
    member_card(b_rows, PAIR_COLORS[1], newest)
st.write("")

# ---------------------------------------------------------------------------
# Votes while serving together
# ---------------------------------------------------------------------------
shared = a_rows.merge(b_rows, on=["congress", "chamber"], suffixes=("_a", "_b"))[["congress", "chamber"]]
per_congress, splits = [], []
tot_both = tot_same = tot_unity = tot_unity_same = 0
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
    same, u_both = int((va[both] == vb[both]).sum()), both & unity
    u_same = int((va[u_both] == vb[u_both]).sum())
    tot_both, tot_same, tot_unity, tot_unity_same = (tot_both + int(both.sum()), tot_same + same,
                                                     tot_unity + int(u_both.sum()), tot_unity_same + u_same)
    per_congress.append({
        "Congress": ordinal(cong), "Chamber": cham, "Votes both cast": int(both.sum()),
        "Voted the same way": f"{same / both.sum() * 100:.1f}%" if both.any() else "None",
        "Party-line votes both cast": int(u_both.sum()),
        "Same way on party-line votes": f"{u_same / u_both.sum() * 100:.1f}%" if u_both.any() else "None",
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

if tot_both:
    n_cong = len(per_congress)
    g1, g2 = st.columns(2)
    with g1:
        card("When they served together", f"{tot_same / tot_both * 100:.0f}%",
             f"of the {tot_both:,} roll calls they both voted on, {a_name} and {b_name} voted the same way. They served "
             f"together in {n_cong} Congress{'es' if n_cong != 1 else ''}.")
    with g2:
        metric_card("Same way on party-line votes",
                    f"{tot_unity_same / tot_unity * 100:.1f}%" if tot_unity else "None",
                    f"{tot_unity:,} party-line votes both cast")
        st.write("")
        metric_card("Key votes where they split", str(len(splits)), "Listed below" if splits else "None in this data")
else:
    st.info(f"{a_name} and {b_name} never served in the same chamber during the same Congress in this data, so their "
            "individual votes can't be compared. Their party unity is shown below.")

# ---------------------------------------------------------------------------
# Position Flips side by side
# ---------------------------------------------------------------------------
if flips["icpsr"].isin([a_id, b_id]).any():
    st.subheader("Same question, different president")
    st.markdown("Whether each member's vote on the same kind of bill changed when the White House changed parties. "
                "The number is the shift in percentage points, comparing only matched votes (same type of vote, same position "
                "in the chamber); near zero means the same vote under both parties' presidents.")
    html_table(["Type of vote", a_name, b_name],
               [["All five types" if c == "All categories" else c, flip_cell(a_id, c), flip_cell(b_id, c)]
                for c in FLIP_CATEGORIES], raw_cols=(1, 2))
    st.page_link("pages/9_How_It_Works.py", label="How this is measured →")

# ---------------------------------------------------------------------------
# Party unity side by side
# ---------------------------------------------------------------------------
history = pd.concat([a_rows.assign(Member=a_name), b_rows.assign(Member=b_name)]).dropna(subset=["party_unity_pct"])
if not history.empty:
    st.subheader("Party unity across Congresses")
    fig = px.line(history, x="congress", y="party_unity_pct", color="Member", markers=True,
                  hover_data={"chamber": True, "party": True}, color_discrete_sequence=PAIR_COLORS,
                  labels={"congress": "Congress", "party_unity_pct": "Party Unity %"})
    fig.update_layout(height=360, xaxis=dict(dtick=1), legend_title_text="")
    show_chart(fig, f"Party unity across Congresses: {a_name} vs. {b_name}",
               f"compare_unity_{a_name.lower()}_{b_name.lower()}".replace(" ", "_"))

if tot_both:
    st.subheader("Key votes where they split")
    if splits:
        st.caption(f"Key votes where {a_name} and {b_name} voted on opposite sides. Key votes are the series listed on "
                   "the Key Votes page.")
        st.dataframe(pd.DataFrame(splits).sort_values("Date", ascending=False), width="stretch", hide_index=True,
                     column_config={"Vote": st.column_config.TextColumn(width="large")})
    else:
        st.caption("They voted the same way on every key vote they both cast while serving together.")
    with st.expander("Agreement in each Congress they served together"):
        st.dataframe(pd.DataFrame(per_congress), width="stretch", hide_index=True)
        st.caption("Counts only roll calls where both members actually voted Yea or Nay. A party-line vote is one where "
                   "most Democrats and most Republicans voted on opposite sides.")

st.markdown("---")
st.caption("Source: Voteview roll-call records. Only actual Yea and Nay floor votes are counted.")
