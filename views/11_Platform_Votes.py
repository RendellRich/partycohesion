"""Platform Votes: roll calls where the two parties' platforms took opposite, specific positions, and the members
who voted against their own party's platform. Topics and links are hand-listed under published rules in
data/platform_topics.csv and data/platform_votes.csv."""

from html import escape

import pandas as pd
import streamlit as st

from pathlib import Path

from chart_utils import ACCENT, MUTED, ordinal
from platform_utils import load_platform, member_platform_votes, member_summary, member_topics, party_totals
from ui import chips, display_name, fmt_date, html_table, inject_css, intro, metric_row, party_tag
from vote_index import voteview_url

PRESIDENT = {110: "Bush", 111: "Obama", 112: "Obama", 113: "Obama", 114: "Obama", 115: "Trump", 116: "Trump", 117: "Biden", 118: "Biden", 119: "Trump", 120: "Trump"}


@st.cache_data
def load():
    members = pd.read_csv(Path(__file__).parent.parent / "data" / "members_processed.csv")
    topics, links = load_platform()
    mv = member_platform_votes(links, members)
    return members, topics, links, mv


def short(r) -> str:
    return f"{display_name(r.name)} ({r.side[0]}-{r.state_abbrev})"


def badge(text: str) -> str:
    return (f'<span class="pc-chip" style="color:{MUTED};margin-right:6px">{escape(text)}</span>')


def plank_html(t, party: str) -> str:
    p = "dem" if party == "Democrat" else "rep"
    year = t[f"{p}_platform"]
    year_note = " (2016 text, re-adopted in 2020)" if party == "Republican" and t["congress"] in (117, 118) else ""
    return (f'<div style="margin:8px 0">{party_tag(party)} <span class="pc-body">· {year} platform{escape(year_note)} · '
            f'<b>{escape(t[f"{p}_stance"])}</b></span><div class="pc-body" style="margin-top:4px">'
            f'{escape(t[f"{p}_plank"])} <a href="{escape(t[f"{p}_source"])}" target="_blank" rel="noopener" '
            f'style="color:{ACCENT}">Platform text →</a> <span style="font-size:0.85rem">({escape(t[f"{p}_check"])})</span>'
            f'</div></div>')


def vote_html(link, against: pd.DataFrame) -> str:
    tags = badge("Counted" if link.counts else "Shown, not counted")
    if link.link == "related":
        tags += badge("Related: a broader or different measure")
    if link.procedural == "yes":
        tags += badge("Procedural")
    eyebrow = f"{link.chamber} · {fmt_date(link.date)} · roll call {int(link.rollnumber)}"
    result = (f"{link.vote_result}, {int(link.yea_count)} Yea to {int(link.nay_count)} Nay · "
              f"Democrats {int(link.dem_yea)}–{int(link.dem_nay)}, Republicans {int(link.rep_yea)}–{int(link.rep_nay)}")
    platform = (f"Matches the Democratic platform: {link.dem_platform_vote} · "
                f"Matches the Republican platform: {link.rep_platform_vote}")
    if against.empty:
        who = '<div class="pc-body" style="margin-top:10px">Every Democrat and Republican who voted matched their own party\'s platform.</div>'
    else:
        who = (f'<div style="margin-top:12px;font-weight:600">{len(against)} voted against their own party\'s platform</div>'
               + chips([short(r) for r in against.sort_values(["side", "name"]).itertuples()]))
    note = f'<div class="pc-body" style="margin-top:10px;font-size:0.9rem">{escape(link.note)}</div>' if link.note else ""
    url = voteview_url(link.congress, link.chamber, link.rollnumber)
    return (f'<div class="pc-card" style="margin:10px 0"><div class="pc-eyebrow">{escape(eyebrow)}</div>'
            f'<div style="font-size:1.15rem;font-weight:600;margin:6px 0 4px 0">{escape(link.measure)}</div>'
            f'<div style="margin:4px 0 6px 0">{tags}</div><div class="pc-body">{escape(result)}</div>'
            f'<div class="pc-body">{escape(platform)}</div>{who}{note}'
            f'<div style="margin-top:12px"><a href="{escape(url)}" target="_blank" rel="noopener" '
            f'style="color:{ACCENT}">Full record on Voteview →</a></div></div>')


inject_css()
members, topics, links, mv = load()

st.title("Platform Votes")
intro("Votes where the Democratic and Republican platforms took opposite, specific positions, and the members who "
      "voted against their own party's platform. A platform is each party's official policy document, adopted at its "
      "convention. It is not a personal promise from each member, and members often give reasons a roll call can't show.")

totals = party_totals(mv).set_index("party")
counted = links[links["counts"]]
d, r = totals.loc["Democrat"], totals.loc["Republican"]
metric_row([
    ("Topics", str(len(topics)), f"{counted['topic_id'].nunique()} with a counted vote"),
    ("Counted votes", str(len(counted)), f"plus {len(links) - len(counted)} shown for context"),
])
metric_row([
    ("Democrats who voted against it", f"{int(d['members_against'])} of {int(d['members'])}",
     f"at least once · on {int(d['topics_against'])} of {int(d['topics_cast']):,} member topics"),
    ("Republicans who voted against it", f"{int(r['members_against'])} of {int(r['members'])}",
     f"at least once · on {int(r['topics_against'])} of {int(r['topics_cast']):,} member topics"),
])
against = member_topics(mv)
against = against[against["against"]].merge(topics[["topic_id", "topic"]], on="topic_id")
where = []
for side in ("Democrat", "Republican"):
    by_topic = against[against["side"] == side].groupby("topic").size().sort_values(ascending=False)
    if len(by_topic):
        top2 = by_topic.head(2)
        where.append(f"{int(top2.sum())} of the {int(by_topic.sum())} times a {side} voted against their platform on a "
                     f"topic came on {'these topics' if len(top2) > 1 else 'this topic'}: "
                     + " and ".join(f"{name} ({n})" for name, n in top2.items()))
st.caption("Counted votes are direct, non-procedural roll calls. Each member counts once per topic (a member topic): "
           "against their platform if they voted against it on any counted vote on that topic, so a topic with "
           "several nearly identical votes weighs the same as a topic with one. Don't read the two parties' totals as "
           "a ranking: they depend on which topics qualify under the rules, and the list is still growing. "
           + ". ".join(where) + ".")

pres_counts = topics["congress"].map(PRESIDENT).value_counts()
by_president = ", ".join(f"{pres_counts[p]} from the {p} years" for p in ("Bush", "Obama", "Trump", "Biden")
                         if p in pres_counts)
# Which platform backs the measures voted on: the party whose platform vote was Yea on the topic's direct votes
yea_party = links[links["link"] == "direct"].assign(
    backer=lambda d: d["dem_platform_vote"].map({"Yea": "Democratic", "Nay": "Republican"}))
backers = yea_party.groupby("topic_id")["backer"].agg(lambda b: b.iloc[0] if b.nunique() == 1 else "both")
dem_backed, rep_backed, mixed = (int((backers == k).sum()) for k in ("Democratic", "Republican", "both"))
with st.expander("The rules for picking topics and votes", expanded=False):
    st.markdown(f"""
These rules were written down before any member results were computed, and apply the same way to both parties.

1. **Which platform applies.** The one adopted in the presidential election year before the vote: 2004 platforms for
   2007 to 2008, 2008 for 2009 to 2012, 2012 for 2013 to 2016, 2016 for 2017 to 2020, 2020 for 2021 to 2024, and 2024
   for 2025 on. The Republican Party re-adopted its 2016 platform in 2020, so that text applies to 2021 to 2024.
2. **Which topics qualify.** Both parties' platforms must take opposite positions on a specific, testable action (a
   law, a program, a rate, a power), and at least one roll call must be on exactly that action.
3. **Which votes count.** Votes on the measure itself: passage, final approval, a joint resolution, or an amendment
   that adds or removes the policy. Procedural votes such as cloture and budget waivers are shown, but not counted.
   Each member counts once per topic, as against their platform if they voted against it on any counted vote on it.
4. **Direct or related.** A direct vote is on exactly what the planks name. A related vote is on the same topic but a
   different or broader measure. Only direct votes count.
5. **Every qualifying topic is included.** Topics aren't dropped to make the two sides even. Instead, the split is
   published: {by_president}. On {dem_backed} topics the votes were on measures the Democratic platform backs, on
   {rep_backed} on measures the Republican platform backs, and on {mixed} there were votes on both sides' measures. The data starts in 2007, so the Bush years cover only 2007 and 2008.
6. **Everything is public.** Every plank and every vote link is in the site's data files, with a link to the platform
   text and a note on how the wording was checked. Each plank is a paraphrase, not a quote.
7. **Neutral wording.** This page says "voted against their party's platform", never "broke a promise".

**Topics left out so far.** Some well-known votes don't qualify because only one platform takes a position. The
Respect for Marriage Act (2022) is out because the 2020 Democratic platform doesn't mention marriage. Expanded
background checks for gun sales (2013, 2019 and 2021) are out because the Republican platforms don't mention them. The
2014 minimum wage vote and the 2015 Keystone XL pipeline vote are out because only one 2012 platform addresses them.
""")

st.subheader("Look up a member")
ms = member_summary(mv)
ms["label"] = [f"{display_name(n)} ({s[0]}-{st_})" for n, s, st_ in zip(ms["name"], ms["side"], ms["state_abbrev"])]
pick = st.selectbox("Member", ["Choose a member"] + sorted(ms["label"]), key="pv_member")
if pick != "Choose a member":
    row = ms[ms["label"] == pick].iloc[0]
    mine = mv[mv["icpsr"] == row["icpsr"]].merge(links[["congress", "chamber", "rollnumber", "measure", "date"]],
                                                 on=["congress", "chamber", "rollnumber"])
    mine = mine.merge(topics[["topic_id", "topic"]], on="topic_id").sort_values("date")
    st.markdown(f"**{escape(pick)}** voted against the {row['side']} platform on **{int(row['against'])} of "
                f"{int(row['cast'])}** topics they cast a counted vote on. Every vote is listed below.")
    html_table(["Date", "Topic", "Vote", "Their vote", "Platform vote", "Against platform", "Counted"],
               [[fmt_date(x.date), x.topic, x.measure, x.vote, x.platform_vote, "Yes" if x.against else "No",
                 "Yes" if x.counts else "No"] for x in mine.itertuples()], muted_cols=(0, 6))

st.subheader("Who voted against their platform most often")
st.caption("Counted votes only, each topic once. A member can only be counted on votes held while they served in "
           "that chamber.")
top = ms[ms["against"] > 0].head(15)
html_table(["Member", "Topics against their platform", "Topics voted on"],
           [[l, int(a), int(c)] for l, a, c in zip(top["label"], top["against"], top["cast"])], muted_cols=(2,))

st.subheader("Every topic")
cong_options = ["All"] + sorted(topics["congress"].unique(), reverse=True)
cong = st.selectbox("Congress", cong_options, key="pv_cong",
                    format_func=lambda c: "All" if c == "All" else f"{ordinal(c)} ({2 * c + 1787} to {2 * c + 1788}), "
                                                                  f"{PRESIDENT.get(c, '')} years")
shown = topics if cong == "All" else topics[topics["congress"] == cong]
for t in shown.sort_values("congress", ascending=False).to_dict("records"):
    st.markdown(f"#### {escape(t['topic'])}")
    st.markdown(f'<div class="pc-body">{ordinal(t["congress"])} Congress ({2 * t["congress"] + 1787} to '
                f'{2 * t["congress"] + 1788}) · {PRESIDENT.get(t["congress"], "")} years</div>'
                + plank_html(t, "Democrat") + plank_html(t, "Republican"), unsafe_allow_html=True)
    for link in links[links["topic_id"] == t["topic_id"]].sort_values(["counts", "date"], ascending=[False, True]).itertuples():
        here = mv[(mv["congress"] == link.congress) & (mv["chamber"] == link.chamber)
                  & (mv["rollnumber"] == link.rollnumber) & mv["against"]]
        st.markdown(vote_html(link, here), unsafe_allow_html=True)

st.caption("Votes: Voteview (UCLA). Platforms: The American Presidency Project (UC Santa Barbara) and the Democratic "
           "Party's own copy of its 2020 platform. Rules and the full topic list: docs/platform-comparison-design.md "
           "in the site's GitHub repository.")
