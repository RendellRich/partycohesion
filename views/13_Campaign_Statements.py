"""Campaign Statements and Votes: what House members said on their own campaign websites, next to how they voted on
the closest roll call once in office. Built by scripts/campaign_statements.py from CampaignView data."""

from pathlib import Path

import pandas as pd
import streamlit as st

from ui import display_name, inject_css, intro, metric_row
from vote_index import voteview_url

DATA_DIR = Path(__file__).parent.parent / "data"
CITATION = ("Porter, Rachel, Colin R. Case, and Sarah A. Treul. 2025. \"CampaignView, a Database of Policy Platforms "
            "and Biographical Narratives for Congressional Candidates.\" Harvard Dataverse. "
            "https://doi.org/10.7910/DVN/JIEAPT")


@st.cache_data
def load() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "campaign_statement_votes.csv")


def member(r) -> str:
    return f"{display_name(r['name'])} ({str(r['party'])[0]}-{r['state_abbrev']}-{int(r['district'])})"


inject_css()
rows = load()

st.title("Campaign Statements and Votes")
intro("What House members wrote on their own campaign websites, next to how they voted on the closest roll call "
      "after the election. The statements are in the candidates' own words. The site only marks whether the vote "
      "went in the same direction as the statement.")

topic = st.selectbox("Topic", sorted(rows["topic"].unique()), key="cmp_topic")
view = rows[rows["topic"] == topic]
same = (view["same_direction"] == "Yes").sum()
diff = view[view["same_direction"] == "No"]
metric_row([
    ("Campaign statements with a clear side", f"{len(view):,}",
     f"from {view['bioguide_id'].nunique()} members · {(view['stance'] == 'Supports').sum()} supported, "
     f"{(view['stance'] == 'Opposes').sum()} opposed"),
    ("Votes in the same direction", f"{same:,} of {len(view):,}",
     f"as the campaign statement · {(view['same_direction'] == 'Did not vote').sum()} did not vote"),
    ("Votes in a different direction", f"{len(diff):,}", f"{diff['bioguide_id'].nunique()} members"),
])
st.caption("A campaign statement counts only when it takes a clear side. Statements that only describe an opponent's "
           "view, or that hedge, are left out. A roll call can't show a member's reasons, and the bill voted on is "
           "rarely the same as the campaign promise word for word.")

st.subheader("The votes")
for _, t in view.drop_duplicates(["congress", "rollnumber"]).iterrows():
    sub = view[(view["congress"] == t["congress"]) & (view["rollnumber"] == t["rollnumber"])]
    n_same = (sub["same_direction"] == "Yes").sum()
    st.markdown(f"**{t['vote_label']}** · statements from the {t['campaign_year']} campaign · "
                f"{n_same} of {len(sub)} voted in the same direction · "
                f"[Voteview]({voteview_url(t['congress'], t['chamber'], t['rollnumber'])})  \n{t['vote_note']}")

if len(diff):
    st.subheader("Votes in a different direction from the campaign statement")
    for _, r in diff.iterrows():
        with st.container(border=True):
            st.markdown(f"**{member(r)}**")
            st.markdown(f"{r['campaign_year']} campaign website: *\"{r['statement']}\"*")
            st.markdown(f"Vote: **{r['actual_vote']}** on {r['vote_label']}. The campaign stance points to "
                        f"{r['expected_vote']}.  \n{r['vote_note']}")

st.subheader("All statements")
c1, c2 = st.columns(2)
with c1:
    party = st.selectbox("Party", ["All", "Democrat", "Republican"], key="cmp_party")
with c2:
    which = st.selectbox("Vote direction", ["All", "Same as the statement", "Different from the statement",
                                            "Did not vote"], key="cmp_dir")
table = view
if party != "All":
    table = table[table["party"] == party]
if which != "All":
    table = table[table["same_direction"] == {"Same as the statement": "Yes", "Different from the statement": "No",
                                              "Did not vote": "Did not vote"}[which]]
st.dataframe(pd.DataFrame({
    "Member": [member(r) for _, r in table.iterrows()],
    "Campaign": table["campaign_year"].astype(str),
    "Stance": table["stance"],
    "Campaign website text": table["statement"],
    "Vote": table["vote_label"],
    "Their vote": table["actual_vote"],
    "Same direction": table["same_direction"],
    "Voteview": [voteview_url(c, ch, n) for c, ch, n in zip(table["congress"], table["chamber"], table["rollnumber"])],
}), hide_index=True, width="stretch", height=480,
    column_config={"Campaign website text": st.column_config.TextColumn(width="large"),
                   "Voteview": st.column_config.LinkColumn(display_text="Open")})

st.caption(f"Statements: CampaignView, campaign website issue pages of 2018, 2020 and 2022 House primary candidates "
           f"(text taken from official House.gov pages is left out). Cite as: {CITATION}. Stances are coded by "
           f"PartyCohesion. Votes: Voteview roll-call records.")
