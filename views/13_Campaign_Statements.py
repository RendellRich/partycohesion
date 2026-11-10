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
    """Hand-coded floor remarks from the Congressional Record, built by scripts/floor_statements.py."""
    return pd.read_csv(DATA_DIR / "floor_statements.csv", dtype=str).fillna("")


# Topics with coded floor remarks: the debate window, each chamber's final vote, and an earlier vote where there was one
FLOOR = {
    "Military aid to Ukraine": dict(
        subject="Ukraine aid", window="from January 2023 to the final votes in April 2024",
        final={"House": "the Ukraine Security Supplemental Appropriations Act (H.R. 8035, Apr. 20, 2024)",
               "Senate": "the final national security package (H.R. 815, Apr. 23, 2024), which also carried aid "
                         "for Israel and Taiwan"},
        earlier={"Senate": "Senate passage on Feb. 13, 2024"}, earlier_short="the Senate's February vote"),
    "Same-sex marriage": dict(
        subject="the Respect for Marriage Act", window="from the House's first vote in July 2022 to the final "
                                                       "vote in December 2022",
        final={"House": "the House vote to pass the Senate's version, with its religious liberty amendment "
                        "(H.R. 8404, Dec. 8, 2022)",
               "Senate": "Senate passage (H.R. 8404, Nov. 29, 2022)"},
        earlier={"House": "first House passage on July 19, 2022"}, earlier_short="the House's July vote"),
}
MONTHS = ["Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec."]


def when(iso: str) -> str:
    d = pd.Timestamp(iso)
    return f"{MONTHS[d.month - 1]} {d.day}, {d.year}"


def cast(v: str) -> str:
    return v if v in ("Yea", "Nay") else "Did not vote"


def expected(stance: str):
    if stance.startswith("Opposes"):
        return "Nay"
    if stance.startswith("Supports"):
        return "Yea"
    return None


def member(r) -> str:
    return f"{display_name(r['name'])} ({str(r['party'])[0]}-{r['state_abbrev']}-{int(r['district'])})"


def floor_section(topic: str) -> None:
    """What members said in floor debates on this topic, next to their final vote, in both chambers."""
    cfg = FLOOR[topic]
    f = load_floor()
    f = f[f["topic"] == topic].copy()
    f["expected"] = f["stance"].map(expected)
    clear = f[f["expected"].notna() & f["vote_final"].isin(["Yea", "Nay"])]
    differ = clear[clear["vote_final"] != clear["expected"]]
    switched = f[f["vote_earlier"].isin(["Yea", "Nay"]) & f["vote_final"].isin(["Yea", "Nay"])
                 & (f["vote_earlier"] != f["vote_final"])]
    changed = switched[~switched["bioguide_id"].isin(differ["bioguide_id"])]
    cond = f[(f["stance"] == "With conditions") & (f["quote"] != "")
             & ~f["bioguide_id"].isin(pd.concat([differ, changed])["bioguide_id"])]

    st.subheader("Said on the floor of Congress")
    st.markdown(f"Members also argue about {cfg['subject']} in floor debates, which the Congressional Record prints "
                f"word for word. This covers both chambers, {cfg['window']}. Each member's remarks were read and "
                "coded by PartyCohesion; the quotes are their own words.")
    metric_row([
        ("Members who spoke on the floor", f"{len(f):,}", f"{(f['stance'] != 'No clear stance').sum()} took a side"),
        ("Final vote in the same direction", f"{len(clear) - len(differ)} of {len(clear)}",
         "members who clearly spoke for or against"),
        ("Final vote in a different direction", f"{len(differ)}", "members"),
        ("Changed their vote along the way", f"{len(switched)}",
         f"between {cfg['earlier_short']} and the final vote"),
    ])
    finals = "; ".join(f"in the {ch}, {txt}" for ch, txt in cfg["final"].items())
    st.caption(f"Final votes: {finals}. A floor speech can be about a different version of the bill than the one "
               "finally voted on.")

    def card(r) -> None:
        with st.container(border=True):
            st.markdown(f"**{display_name(r['name'])}** ({r['party'][0]}-{r['state_abbrev']}, {r['chamber']})")
            if r["quote"]:
                st.markdown(f"On the floor, {when(r['remark_date'])}: *\"{r['quote']}\"* "
                            f"[Read the remarks]({r['source_url']})")
            if r["reason_quote"]:
                st.markdown(f"Their stated reason: *\"{r['reason_quote']}\"*")
            votes = f"Final vote: **{cast(r['vote_final'])}**"
            if r["vote_earlier"] and r["chamber"] in cfg["earlier"]:
                earlier = cfg["earlier"][r["chamber"]]
                votes += f". {earlier[0].upper() + earlier[1:]}: **{cast(r['vote_earlier'])}**"
            st.markdown(votes + ".")
            if r["bioguide_id"] in set(differ["bioguide_id"]) and not r["reason_quote"]:
                st.caption("Their remarks in this record don't say why their vote went the other way.")

    if len(differ):
        st.markdown("##### Spoke one way, then cast a final vote the other way")
        for _, r in differ.iterrows():
            card(r)
    if len(changed):
        st.markdown("##### Changed their vote between the two votes")
        for _, r in changed[changed["quote"] != ""].iterrows():
            card(r)
        others = changed[changed["quote"] == ""]
        if len(others):
            names = "; ".join(f"{display_name(r['name'])} ({r['party'][0]}-{r['state_abbrev']}), "
                              f"{cast(r['vote_earlier'])} then {cast(r['vote_final'])}" for _, r in others.iterrows())
            st.caption(f"Also changed, without a clear stance in their floor remarks: {names}.")
    if len(cond):
        st.markdown("##### Tied their vote to conditions")
        for _, r in cond.iterrows():
            card(r)

    with st.expander(f"All {len(f)} members who spoke on the floor"):
        st.dataframe(pd.DataFrame({
            "Member": [f"{display_name(r['name'])} ({r['party'][0]}-{r['state_abbrev']})" for _, r in f.iterrows()],
            "Chamber": f["chamber"],
            "What they said": f["stance"],
            "Final vote": f["vote_final"].map(cast),
            "Remarks": f["source_url"],
        }), hide_index=True, width="stretch", height=420,
            column_config={"Remarks": st.column_config.LinkColumn(display_text="Read")})
    st.caption("Floor remarks: Congressional Record, via GovInfo (U.S. Government Publishing Office). Stances are coded "
               "by PartyCohesion. \"No clear stance\" means the member spoke on the topic without taking a side.")


inject_css()
rows = load()

st.title("Campaign Statements and Votes")
intro("What House members wrote on their own campaign websites, next to how they voted on the closest roll call "
      "after the election. The statements are in the candidates' own words. The site only marks whether the vote "
      "went in the same direction as the statement.")
explainer('Candidates tell voters where they stand on their campaign websites. This page lines those words up '
          "with the next vote on the same issue. Nearly all match; the few that don't are worth a closer look, "
          "but one vote can't show why it went that way. For Ukraine aid and same-sex marriage, the page also lines up "
          "what members of both chambers said in floor debates with their final vote.")

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

if topic in FLOOR:
    floor_section(topic)

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
