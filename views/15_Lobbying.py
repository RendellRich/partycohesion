"""Lobbying Reports: which bills lobbying reports name, by whom and when, next to the votes on those bills.
Built by scripts/lobbying_pull.py and scripts/lobbying_index.py from Lobbying Disclosure Act filings on lda.gov."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chart_utils import ordinal, show_chart
from lobbying import CANT_SAY, bill_counts, bill_titles, load, period_label, summary_line
from theme import tokens
from ui import bill_label, explainer, inject_css, intro, metric_row
from vote_index import load_votes, voteview_url

inject_css()
links = load()
votes = load_votes()

st.title("Lobbying Reports")
intro("Every quarter, lobbyists file a public report with Congress listing the issues and bills they worked on for "
      "each client. This page counts the reports that name each bill and shows when they were filed, next to the "
      "votes on that bill.")
explainer(CANT_SAY)

if links.empty:
    st.info("The lobbying reports are still being downloaded and matched to bills. This page fills in once that's "
            "done.")
    st.stop()

voted = votes.dropna(subset=["bill_number"])[["congress", "bill_number"]].drop_duplicates()
congresses = sorted(links["congress"].unique(), reverse=True)
want = st.query_params.get("congress")
c1, c2, c3 = st.columns([1.1, 1.3, 1.4])
with c1:
    congress = st.selectbox("Congress", congresses, key="lb_cong",
                            index=congresses.index(int(want)) if want and want.isdigit() and int(want) in congresses else 0,
                            format_func=lambda c: f"{ordinal(c)} ({2 * c + 1787} to {2 * c + 1788})")
with c2:
    only_voted = st.toggle("Only bills with a vote on this site", value=True, key="lb_voted")
with c3:
    query = st.text_input("Bill or client", "", key="lb_q", placeholder="e.g. H.R. 8070 or a company name")

here = links[links["congress"] == congress]
counts = bill_counts(here).merge(voted.assign(has_vote=True), on=["congress", "bill_number"], how="left")
counts["has_vote"] = counts["has_vote"].fillna(False).astype(bool)
if only_voted:
    counts = counts[counts["has_vote"]]
if query:
    key = query.replace(".", "").replace(" ", "").upper()
    by_client = here[here["client"].str.contains(query, case=False, na=False)]["bill_number"].unique()
    counts = counts[(counts["bill_number"] == key) | counts["bill_number"].isin(by_client)]

counts = counts.merge(bill_titles(votes), on=["congress", "bill_number"], how="left")

metric_row([
    ("Reports naming a bill", f"{here['filing_uuid'].nunique():,}", f"{ordinal(congress)} Congress"),
    ("Bills named", f"{here[['bill_number']].drop_duplicates().shape[0]:,}", "in at least one report"),
    ("With a vote on this site", f"{int(bill_counts(here).merge(voted, on=['congress', 'bill_number']).shape[0]):,}",
     "bills named in reports"),
    ("Clients", f"{here['client_id'].nunique():,}", "that named at least one bill"),
])

if counts.empty:
    st.info("No bills match. Clear the search or turn off \"Only bills with a vote on this site\".")
    st.stop()

st.dataframe(pd.DataFrame({
    "Bill": [bill_label(b) for b in counts["bill_number"]],
    "Title": counts["title"].fillna(""),
    "Reports": counts["reports"],
    "Clients": counts["clients"],
    "Quarters": [f"{period_label(a)} to {period_label(b)}" if a != b else period_label(a)
                 for a, b in zip(counts["first"], counts["last"])],
    "Top issue areas": counts["issues"].fillna(""),
}), hide_index=True, width="stretch", height=380,
    column_config={"Title": st.column_config.TextColumn(width="large"),
                   "Top issue areas": st.column_config.TextColumn(width="medium")})
st.caption("Reports counts each lobbying report once, however many times it names the bill. A report covers one "
           "client for one quarter. Issue areas are the categories filers choose for each item on a report.")

st.subheader("Look at one bill")
options = list(counts["bill_number"])
want_bill = st.query_params.get("bill")
bill = st.selectbox("Bill", options, key="lb_bill", label_visibility="collapsed",
                    index=options.index(want_bill) if want_bill in options else 0,
                    format_func=lambda b: f"{bill_label(b)} · {str(counts.set_index('bill_number').at[b, 'title'] or '')[:90]}")
one = here[here["bill_number"] == bill]
st.markdown(summary_line(links, congress, bill))

per_q = one.drop_duplicates("filing_uuid").groupby("period").size().rename("reports").reset_index()
per_q["start"] = pd.to_datetime([f"{p // 10}-{3 * (p % 10) - 2:02d}-01" for p in per_q["period"]])
on_bill = votes[(votes["congress"] == congress) & (votes["bill_number"] == bill)].sort_values("date")
t = tokens()
fig = go.Figure(go.Bar(x=per_q["start"] + pd.Timedelta(days=45), y=per_q["reports"], marker_color=t["muted"],
                       name="Lobbying reports", width=1000 * 60 * 60 * 24 * 80,
                       hovertext=[period_label(p) for p in per_q["period"]],
                       hovertemplate="%{hovertext}: %{y} reports<extra></extra>"))
for d in on_bill["date"].unique():
    fig.add_vline(x=pd.Timestamp(d), line_width=1.5, line_dash="dot", line_color=t["accent"])
if len(on_bill):
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", line=dict(color=t["accent"], dash="dot"),
                             name="Roll call on this bill"))
fig.update_layout(height=360, yaxis_title="Reports naming the bill", xaxis_title=None, showlegend=bool(len(on_bill)))
show_chart(fig, f"Lobbying reports naming {bill_label(bill)}, by quarter", f"lobbying_{congress}_{bill.lower()}",
           source="partycohesion.streamlit.app · Data: lda.gov, Voteview")
st.caption("Each bar is one quarter. Dotted lines are roll calls on this bill in either chamber. Reports for a "
           "quarter are filed after it ends, so a bar shows lobbying during that quarter, not the day it was filed.")

if len(on_bill):
    with st.expander(f"Roll calls on {bill_label(bill)} ({len(on_bill)})"):
        st.dataframe(pd.DataFrame({
            "Date": on_bill["date"], "Chamber": on_bill["chamber"], "Vote": on_bill["label"],
            "Question": on_bill["vote_question"], "Result": on_bill["vote_result"],
            "Roll call": [voteview_url(c, ch, r) for c, ch, r in zip(on_bill["congress"], on_bill["chamber"],
                                                                     on_bill["rollnumber"])],
        }), hide_index=True, width="stretch",
            column_config={"Roll call": st.column_config.LinkColumn(display_text="Voteview")})

clients = (one.groupby(["client_id", "client"]).agg(
    reports=("filing_uuid", "nunique"), firms=("registrant", lambda s: ", ".join(sorted(set(s.dropna()))[:3])),
    first=("period", "min"), last=("period", "max"), issues=("issue", lambda s: ", ".join(s.value_counts().index[:2])),
    url=("url", "last")).reset_index().sort_values(["reports", "client"], ascending=[False, True]))
st.markdown(f"**Clients whose reports named {bill_label(bill)}**")
st.dataframe(pd.DataFrame({
    "Client": clients["client"], "Reports": clients["reports"], "Filed by": clients["firms"],
    "Quarters": [f"{period_label(a)} to {period_label(b)}" if a != b else period_label(a)
                 for a, b in zip(clients["first"], clients["last"])],
    "Issue areas": clients["issues"], "Latest report": clients["url"],
}), hide_index=True, width="stretch", height=380,
    column_config={"Client": st.column_config.TextColumn(width="medium"),
                   "Filed by": st.column_config.TextColumn(width="medium"),
                   "Latest report": st.column_config.LinkColumn(display_text="lda.gov")})
st.caption("\"Filed by\" is the lobbying firm, or the client itself when it lobbies with its own staff. The list is in "
           "order of how many reports named the bill, not a ranking of influence. Each link opens the filing as "
           "submitted.")

st.markdown("---")
st.caption("Source: Lobbying Disclosure Act reports from the U.S. Senate Office of Public Records and the Clerk of the "
           "House (lda.gov), matched to bills by number. How the matching works and how often it's right are on the "
           "Methodology page.")
