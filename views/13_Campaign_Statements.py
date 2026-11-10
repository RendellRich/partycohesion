"""Campaign Statements and Votes: what House members said on their own campaign websites, next to how they voted on
the closest roll call once in office. Built by scripts/campaign_statements.py from CampaignView data."""

from pathlib import Path

import pandas as pd
import streamlit as st

from ui import explainer, display_name, inject_css, intro, metric_row
from vote_index import voteview_url

DATA_DIR = Path(__file__).parent.parent / "data"
CITATION = ("Porter, Rachel, Colin R. Case, and Sarah A. Treul. 2025. \"CampaignView, a Database of Policy Platforms "
            "and Biographical Narratives for Congressional Candidates.\" Harvard Dataverse. "
            "https://doi.org/10.7910/DVN/JIEAPT")


@st.cache_data
def load() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "campaign_statement_votes.csv")


@st.cache_data
def load_floor() -> pd.DataFrame:
    """Hand-coded floor remarks on Ukraine aid, built by scripts/floor_statements.py."""
    return pd.read_csv(DATA_DIR / "floor_statements_ukraine.csv", dtype=str).fillna("")


FLOOR_TOPIC = "Military aid to Ukraine"
FINAL_VOTE = {"House": ("vote_house_hr8035", "the Ukraine Security Supplemental Appropriations Act (H.R. 8035, Apr. 20, 2024)"),
              "Senate": ("vote_senate_apr23", "the final national security package (H.R. 815, Apr. 23, 2024), which "
                                              "also carried aid for Israel and Taiwan")}
EXPECT = {"Supports more aid": "Yea", "Opposes more aid": "Nay"}


MONTHS = ["Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."]


def when(iso: str) -> str:
    d = pd.Timestamp(iso)
    return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"


def cast(v: str) -> str:
    return v if v in ("Yea", "Nay") else "Did not vote"


def floor_section() -> None:
    """What members said about Ukraine aid in floor debates, next to their final vote, in both chambers."""
    f = load_floor()
    f["final_vote"] = [r[FINAL_VOTE[r["chamber"]][0]] for _, r in f.iterrows()]
    f["expected"] = f["stance"].map(EXPECT)
    clear = f[f["expected"].notna() & f["final_vote"].isin(["Yea", "Nay"])]
    differ = clear[clear["final_vote"] != clear["expected"]]
    cond = f[f["stance"] == "Supports helping Ukraine, with conditions"]

    st.subheader("Said on the floor of Congress")
    st.markdown("Members also argue about Ukraine aid in floor debates, which the Congressional Record prints word for "
                "word. This covers both chambers, from January 2023 to the final votes in April 2024. Each member's "
                "remarks were read and coded by PartyCohesion; the quotes are their own words.")
    metric_row([
        ("Members who spoke about Ukraine", f"{len(f):,}",
         f"{(f['stance'] != 'No clear stance').sum()} took a side"),
        ("Final vote in the same direction", f"{len(clear) - len(differ)} of {len(clear)}",
         "members who clearly spoke for or against more aid"),
        ("Final vote in a different direction", f"{len(differ)}", "all in the Senate's combined package"
         if len(differ) and (differ["chamber"] == "Senate").all() else "members"),
        ("Spoke for helping Ukraine, with conditions", f"{len(cond)}", "border security, offsets or oversight"),
    ])
    st.caption(f"Final votes: in the House, {FINAL_VOTE['House'][1]}; in the Senate, {FINAL_VOTE['Senate'][1]}. "
               "A floor speech can be about a different version of the bill than the one finally voted on.")

    def card(r, extra: str = "") -> None:
        with st.container(border=True):
            st.markdown(f"**{display_name(r['name'])}** ({r['party'][0]}-{r['state_abbrev']}, {r['chamber']})")
            st.markdown(f"On the floor, {when(r['remark_date'])}: *\"{r['quote']}\"* [Read the remarks]({r['source_url']})")
            if r["reason_quote"]:
                st.markdown(f"On the package: *\"{r['reason_quote']}\"*")
            votes = f"Final vote: **{cast(r['final_vote'])}**"
            if r["chamber"] == "Senate" and r["vote_senate_feb13"]:
                votes += f". Senate passage on Feb. 13, 2024: **{cast(r['vote_senate_feb13'])}**"
            st.markdown(votes + "." + (f"  \n{extra}" if extra else ""))

    if len(differ):
        st.markdown("##### Spoke for more aid, then voted against the final package")
        for _, r in differ.iterrows():
            card(r, "" if r["reason_quote"] else "Their remarks in this record don't say why they voted no.")
    if len(cond):
        st.markdown("##### Spoke for helping Ukraine, with conditions")
        for _, r in cond[cond["quote"] != ""].iterrows():
            card(r)

    with st.expander(f"All {len(f)} members who spoke about Ukraine on the floor"):
        st.dataframe(pd.DataFrame({
            "Member": [f"{display_name(r['name'])} ({r['party'][0]}-{r['state_abbrev']})" for _, r in f.iterrows()],
            "Chamber": f["chamber"],
            "What they said": f["stance"],
            "Final vote": f["final_vote"].map(cast),
            "Remarks": f["source_url"],
        }), hide_index=True, width="stretch", height=420,
            column_config={"Remarks": st.column_config.LinkColumn(display_text="Read")})
    st.caption("Floor remarks: Congressional Record, via GovInfo (U.S. Government Publishing Office). Stances are coded "
               "by PartyCohesion. \"No clear stance\" means the member mentioned Ukraine without taking a side on aid.")


def member(r) -> str:
    return f"{display_name(r['name'])} ({str(r['party'])[0]}-{r['state_abbrev']}-{int(r['district'])})"


inject_css()
rows = load()

st.title("Campaign Statements and Votes")
intro("What House members wrote on their own campaign websites, next to how they voted on the closest roll call "
      "after the election. The statements are in the candidates' own words. The site only marks whether the vote "
      "went in the same direction as the statement.")
explainer('Candidates tell voters where they stand on their campaign websites. This page lines those words up '
          "with the next vote on the same issue. Nearly all match; the few that don't are worth a closer look, "
          "but one vote can't show why it went that way. For Ukraine aid, the page also lines up what members of "
          "both chambers said in floor debates with their final vote.")

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

if topic == FLOOR_TOPIC:
    floor_section()

st.subheader("All campaign statements")
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
