"""Same Bill, Different Vote: members who voted for a bill at one stage and against it at another (or the reverse),
in the same chamber and Congress. Built by scripts/vote_changes.py."""

from pathlib import Path

import pandas as pd
import streamlit as st

from chart_utils import ordinal
from ui import SITE, bill_label, display_name, explainer, fmt_date, inject_css, intro, metric_row
from vote_index import voteview_url

DATA_DIR = Path(__file__).parent.parent / "data"


@st.cache_data
def load():
    changes = pd.read_csv(DATA_DIR / "vote_changes.csv")
    bills = pd.read_csv(DATA_DIR / "vote_change_bills.csv")
    changes["party_short"] = changes["party"].fillna("").str[0]
    return changes, bills


def vote_text(date, stage, vote) -> str:
    return f"{vote} · {stage} · {fmt_date(date)}"


inject_css()
changes, bills = load()

st.title("Same Bill, Different Vote")
intro("A bill can get more than one up-or-down vote in the same chamber: when it first passes, again on the final "
      "version after the other chamber changes it, and sometimes on a veto override. On each of those, Yea means "
      "supporting the bill. This page lists every member who voted Yea at one stage and Nay at another.")
explainer("A changed vote is a fact about the record, not a judgment. The bill's text often changes between votes, "
          "sometimes a lot, and a roll call can't show a member's reasons. The most telling cases are members who "
          "changed while most of their own party voted the same way both times.")

apart = changes[changes["apart"]]
chances = int(bills["voted_twice"].sum())
metric_row([
    ("Bills with two or more support votes", f"{len(bills):,}", "same chamber and Congress, since 2007"),
    ("Changed their vote", f"{len(changes):,}", f"{len(changes) / chances:.1%} of {chances:,} times a member voted "
                                                 "at two stages"),
    ("Changed while their party didn't", f"{len(apart):,}", f"{len(apart) / chances:.1%} · on "
                                                              f"{len(apart[['congress', 'chamber', 'bill_number']].drop_duplicates())} bills"),
    ("Members who did that at least once", f"{apart['icpsr'].nunique():,}", "since 2007"),
])
st.caption("Counted: passage, the final version (a conference report or agreeing to the other chamber's changes) and "
           "veto overrides. Not counted: procedural votes such as cloture, motions to recommit, rules and amendments, "
           "because voting against one of those and for passage is the same position. \"Their party\" means how "
           "most members of the party they caucus with voted on each of the two roll calls.")

c1, c2, c3, c4 = st.columns([1.2, 0.8, 0.9, 1.4])
with c1:
    congress = st.selectbox("Congress", ["All", *sorted(changes["congress"].unique(), reverse=True)], key="sb_cong",
                            format_func=lambda c: "All (2007 to now)" if c == "All" else
                            f"{ordinal(c)} ({2 * c + 1787} to {2 * c + 1788})")
with c2:
    chamber = st.selectbox("Chamber", ["All", "House", "Senate"], key="sb_cham")
with c3:
    party = st.selectbox("Party", ["All", "Democrat", "Republican", "Independent"], key="sb_party")
with c4:
    query = st.text_input("Member or bill", "", key="sb_q", placeholder="e.g. Gallagher or H.R. 8404")
t1, t2 = st.columns(2)
with t1:
    only_apart = st.toggle("Only members who changed while their party didn't", value=True, key="sb_apart")
with t2:
    same_title = st.toggle("Only bills whose title stayed the same", value=False, key="sb_title",
                           help="Hides bills whose current title shares almost no words with how the first vote "
                                "described them. That can be a rename, or a bill number reused for a different bill.")

view = changes
if congress != "All":
    view = view[view["congress"] == congress]
if chamber != "All":
    view = view[view["chamber"] == chamber]
if party != "All":
    view = view[view["party"].fillna("").str.startswith(party)]
if query:
    key = query.replace(".", "").replace(" ", "").upper()
    view = view[view["name"].str.contains(query, case=False, na=False) | (view["bill_number"] == key)]
if only_apart:
    view = view[view["apart"]]
if same_title:
    view = view[~view["title_changed"].fillna(False).astype(bool)]
view = view.sort_values(["final_date", "bill_number", "name"], ascending=[False, True, True])

st.caption(f"{len(view):,} changed votes")
st.dataframe(pd.DataFrame({
    "Member": [f"{display_name(n)} ({p}-{s})" for n, p, s in zip(view["name"], view["party_short"],
                                                                 view["state_abbrev"])],
    "Bill": [bill_label(b) for b in view["bill_number"]],
    "Title now": view["title"].fillna(view["first_vote_desc"]).fillna(""),
    "First vote": [vote_text(d, s, v) for d, s, v in zip(view["first_date"], view["first_stage"], view["first_vote"])],
    "Final vote": [vote_text(d, s, v) for d, s, v in zip(view["final_date"], view["final_stage"], view["final_vote"])],
    "Their party": view["party_first"] + " then " + view["party_final"],
    "Title changed": view["title_changed"].map({True: "Yes", False: "No"}).fillna("No"),
    "Member page": [f"{SITE}/Member_Explorer?member={b}" if isinstance(b, str) else None for b in view["bioguide_id"]],
    "First roll call": [voteview_url(c, ch, r) for c, ch, r in zip(view["congress"], view["chamber"],
                                                                   view["first_rollnumber"])],
    "Final roll call": [voteview_url(c, ch, r) for c, ch, r in zip(view["congress"], view["chamber"],
                                                                   view["final_rollnumber"])],
}), hide_index=True, width="stretch", height=480,
    column_config={"Title now": st.column_config.TextColumn(width="large"),
                   "Member page": st.column_config.LinkColumn(display_text="Open"),
                   "First roll call": st.column_config.LinkColumn(display_text="Voteview"),
                   "Final roll call": st.column_config.LinkColumn(display_text="Voteview")})

st.subheader("Bills where the most members changed while their party didn't")
pool = view if (congress != "All" or chamber != "All" or party != "All" or query or same_title) else apart
top = (pool[pool["apart"]].groupby(["congress", "chamber", "bill_number"]).agg(
    n=("icpsr", "size"), dem=("caucus", lambda s: (s == "Democrat").sum()),
    rep=("caucus", lambda s: (s == "Republican").sum())).sort_values("n", ascending=False).head(8))
if top.empty:
    st.caption("No members changed apart from their party in this selection.")
for (c, ch, b), r in top.iterrows():
    info = bills[(bills["congress"] == c) & (bills["chamber"] == ch) & (bills["bill_number"] == b)].iloc[0]
    title = info["title"] if isinstance(info["title"], str) and info["title"] else info["first_desc"]
    parties = ", ".join(x for x in [f"{int(r['dem'])} Democrats" if r["dem"] else "",
                                    f"{int(r['rep'])} Republicans" if r["rep"] else ""] if x)
    renamed = " The title changed between votes." if info["title_changed"] else ""
    st.markdown(f"**{bill_label(b)}** · {title} ({ch}, {ordinal(c)} Congress): {int(r['n'])} members ({parties}) "
                f"changed while their party didn't, between {fmt_date(info['first_date'])} and "
                f"{fmt_date(info['final_date'])}.{renamed}")

st.caption("Sources: Voteview roll-call records, and GovInfo bill status files for each bill's current title. "
           "Paired and announced positions are not counted, only votes cast on the floor.")
