"""Cosponsored, Then Voted No: members who put their name on a bill and then voted against it on final passage,
with whether the bill's text had changed before the vote."""

from pathlib import Path

import pandas as pd
import streamlit as st

from chart_utils import ordinal
from ui import display_name, fmt_date, inject_css, intro, metric_row
from vote_index import voteview_url

DATA_DIR = Path(__file__).parent.parent / "data"


@st.cache_data
def load():
    votes = pd.read_csv(DATA_DIR / "cosponsor_votes.csv")
    nays = pd.read_csv(DATA_DIR / "cosponsor_nays.csv")
    members = pd.read_csv(DATA_DIR / "members_processed.csv").drop_duplicates(["congress", "chamber", "icpsr"])
    titles = pd.read_csv(DATA_DIR / "all_votes.csv", usecols=["congress", "chamber", "rollnumber", "vote_desc"])
    rows = (nays.merge(votes, on=["congress", "chamber", "rollnumber", "bill"])
            .merge(members[["congress", "chamber", "icpsr", "name", "party", "state_abbrev"]],
                   on=["congress", "chamber", "icpsr"], how="left")
            .merge(titles, on=["congress", "chamber", "rollnumber"], how="left"))
    return votes, rows


def bill_label(bill: str) -> str:
    for raw, nice in (("HJRES", "H.J.Res. "), ("SJRES", "S.J.Res. "), ("HR", "H.R. "), ("S", "S. ")):
        if bill.startswith(raw):
            return nice + bill[len(raw):]
    return bill


inject_css()
votes, rows = load()

st.title("Cosponsored, Then Voted No")
intro("Members who put their name on a bill as its sponsor or a cosponsor, and then voted against it on final "
      "passage. A bill often changes between signing and the vote, so each case shows whether its text had changed "
      "first.")

cast = int(votes["signers_voting"].sum())
unchanged = rows[~rows["changed_before_vote"]]
metric_row([
    ("Final passage votes", f"{len(votes):,}", "on bills and joint resolutions since 2007"),
    ("Votes cast by the bill's own signers", f"{cast:,}", f"{int(votes['signers_yea'].sum()):,} of them Yea"),
    ("Voted no on a bill they signed", f"{len(rows):,}", f"{len(rows) / cast * 100:.1f}% · {rows['icpsr'].nunique()} members"),
    ("No, with the text unchanged", f"{len(unchanged):,}", f"{unchanged['icpsr'].nunique()} members"),
])
st.caption("Text changed before the vote means a committee reported the bill with changes, a rule replaced its text "
           "with a substitute, an amendment was agreed to, or the House passed it \"as amended\". Then the member may "
           "have voted against a different bill from the one they signed. A roll call can't show a member's reasons.")

c1, c2, c3 = st.columns([1.2, 1, 1.4])
with c1:
    congress = st.selectbox("Congress", ["All", *sorted(rows["congress"].unique(), reverse=True)], key="cs_cong",
                            format_func=lambda c: "All (2007 to now)" if c == "All" else
                            f"{ordinal(c)} ({2 * c + 1787} to {2 * c + 1788})")
with c2:
    party = st.selectbox("Party", ["All", "Democrat", "Republican", "Independent"], key="cs_party")
with c3:
    name = st.text_input("Member or bill", "", key="cs_q", placeholder="e.g. Smith or H.R. 82")
only_unchanged = st.toggle("Only bills whose text hadn't changed", key="cs_unchanged")

view = rows
if congress != "All":
    view = view[view["congress"] == congress]
if party != "All":
    view = view[view["party"] == party]
if name:
    key = name.replace(".", "").replace(" ", "").upper()
    view = view[view["name"].str.contains(name, case=False, na=False) | (view["bill"] == key)]
if only_unchanged:
    view = view[~view["changed_before_vote"]]
view = view.sort_values(["date", "bill", "name"], ascending=[False, True, True])

st.caption(f"{len(view):,} cases")
st.dataframe(pd.DataFrame({
    "Date": [fmt_date(d) for d in view["date"]],
    "Bill": [bill_label(b) for b in view["bill"]],
    "Title": view["vote_desc"].fillna(""),
    "Vote": view["vote_question"] + " · " + view["vote_result"],
    "Member": [f"{display_name(n)} ({str(p)[0]}-{s})" for n, p, s in zip(view["name"], view["party"],
                                                                          view["state_abbrev"])],
    "Role": view["role"],
    "Signed on": [fmt_date(d) if isinstance(d, str) and d else "" for d in view["signed"]],
    "Text changed before vote": view["changed_before_vote"].map({True: "Yes", False: "No"}),
    "Voteview": [voteview_url(c, ch, r) for c, ch, r in zip(view["congress"], view["chamber"], view["rollnumber"])],
}), hide_index=True, width="stretch", height=480,
    column_config={"Title": st.column_config.TextColumn(width="large"),
                   "Voteview": st.column_config.LinkColumn(display_text="Open")})

top = (view.groupby(["congress", "chamber", "bill", "vote_desc"], dropna=False).size().sort_values(ascending=False)
       .head(5))
if len(top):
    st.subheader("Bills with the most signers voting no")
    for (c, ch, b, t), n in top.items():
        v = votes[(votes["congress"] == c) & (votes["chamber"] == ch) & (votes["bill"] == b)].iloc[0]
        changed = "text changed before the vote" if v["changed_before_vote"] else "text unchanged"
        st.markdown(f"**{bill_label(b)}** {'' if pd.isna(t) else '· ' + str(t)} ({ch}, {fmt_date(v['date'])}): "
                    f"{n} of its {int(v['signers_voting'])} signers who voted said no; {changed}.")

st.caption("Sources: GovInfo bill status files (the Congress.gov record of each bill's sponsor, cosponsors, actions "
           "and amendments) and Voteview roll-call records. Cosponsors who withdrew are not counted.")
