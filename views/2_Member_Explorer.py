"""Members: one member's profile (party unity, Position Flips, votes with each president's stated
position, ideology), plus a browsable table of every member. Layout follows the "Members" mockup in
the PartyCohesion Figma design system."""

from html import escape
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from chart_utils import ACCENT, MUTED, PARTY_COLORS, ordinal, show_chart
from flip_utils import add_chamber_control, flip_scores
from platform_utils import platform_record
from ui import (explainer, display_name, fmt_date, html_table, inject_css, intro, last_name, member_header, metric_row,
                pattern_badge, share_bar)
from vote_index import load_votes, member_record, search_votes, voteview_url

DATA_DIR = Path(__file__).parent.parent / "data"
PREFIX = {"House": "H", "Senate": "S"}
CATEGORIES = ["Debt limit", "Stopgap funding", "Full-year funding", "Disaster aid", "War powers limits"]


@st.cache_data
def load_members():
    return pd.read_csv(DATA_DIR / "members_processed.csv")


@st.cache_data
def load_missed():
    """Roll calls held while each member served, and how many they did not vote on (see Methodology)."""
    m = pd.read_csv(DATA_DIR / "missed_votes.csv")
    m["missed_pct"] = (100 * m["missed"] / m["eligible"]).round(1)
    return m


@st.cache_data
def load_details() -> pd.DataFrame:
    """Photo, years served, website, phone and committees (built by scripts/member_details.py)."""
    return pd.read_csv(DATA_DIR / "member_details.csv").fillna("").set_index("bioguide_id")


def member_facts(bioguide: str) -> None:
    details = load_details()
    if bioguide not in details.index:
        return
    d = details.loc[bioguide]
    photo = (f'<img src="{escape(d["photo_url"])}" alt="Official photo of {escape(d["full_name"])}" loading="lazy">'
             if d["photo_url"] else "<div></div>")
    served = f"Served in Congress {d['first_year']} to " + ("now" if d["in_office"] else str(d["last_year"]))
    lines = [f"<b>{escape(served)}</b>"]
    if d["website"]:
        lines.append(f'Official website: <a href="{escape(d["website"])}" target="_blank" rel="noopener">'
                     f'{escape(d["website"].split("//")[-1].rstrip("/"))}</a>')
    contact = []
    if d["contact_form"]:
        contact.append(f'<a href="{escape(d["contact_form"])}" target="_blank" rel="noopener">contact form</a>')
    if d["phone"]:
        contact.append(escape(d["phone"]))
    if d["office"]:
        contact.append(escape(d["office"]))
    if contact:
        lines.append("Contact: " + ", ".join(contact))
    if d["committees"]:
        lines.append("Committees: " + escape(d["committees"]))
    st.markdown(f'<div class="pc-person">{photo}<div class="pc-facts">{"<br>".join(lines)}</div></div>',
                unsafe_allow_html=True)


@st.cache_data
def load_campaign():
    """Campaign website statements and the vote that followed (built by scripts/campaign_statements.py)."""
    return pd.read_csv(DATA_DIR / "campaign_statement_votes.csv")


MISSED_NOTE = ("A missed vote is a roll call held while the member served on which they cast no vote. The record "
               "doesn't say why. Common reasons include illness, a family emergency or new child, running for another "
               "office, and the last months before leaving Congress.")


@st.cache_data
def load_flips():
    return add_chamber_control(pd.read_csv(DATA_DIR / "flip_member_votes.csv"), load_members())


@st.cache_data
def load_matrix(congress: int, chamber: str):
    path = DATA_DIR / "matrices" / f"{PREFIX[chamber]}{congress}.npz"
    if not path.exists():
        return None
    with np.load(path) as f:
        return f["icpsr"], f["rollnumber"], f["votes"]


@st.cache_data
def president_support(congress: int, chamber: str) -> pd.DataFrame:
    """Every member's agreement with the president's stated position on votes with a White House statement."""
    pv = pd.read_csv(DATA_DIR / "president_position_votes.csv")
    pv = pv[(pv["congress"] == congress) & (pv["chamber"] == chamber)]
    mat = load_matrix(congress, chamber)
    if mat is None or pv.empty:
        return pd.DataFrame()
    icpsr, rolls, votes = mat
    col = {r: i for i, r in enumerate(rolls)}
    pv = pv[pv["rollnumber"].isin(col)]
    sub = votes[:, [col[r] for r in pv["rollnumber"]]]
    target = np.where(pv["president_vote"].to_numpy() == "Yea", 1, -1)
    voted = sub != 0
    agree = (sub == target) & voted
    out = []
    for pres in pv["president"].unique():
        m = (pv["president"] == pres).to_numpy()
        out.append(pd.DataFrame({"icpsr": icpsr, "president": pres,
                                 "president_party": pv.loc[pv["president"] == pres, "president_party"].iloc[0],
                                 "votes": voted[:, m].sum(axis=1), "agreed": agree[:, m].sum(axis=1)}))
    return pd.concat(out, ignore_index=True)


inject_css()
df = load_members()
flips = load_flips()
newest = int(df["congress"].max())

st.title("Members")
intro("Look up any member of Congress since 2007: how often they vote with their party, whether their votes change "
      "with the White House, and where they sit ideologically.")
explainer("A member's record shows how often they side with their party, whether their votes shift when the "
          'White House changes hands, and, for many House members, what their campaign website said. High party '
          "unity is normal in today's Congress, so the votes where a member breaks from their party usually "
          'tell you the most.')

# One entry per person, labeled with their most recent party, state and chamber
latest = df.sort_values("congress").groupby("icpsr").tail(1)
latest = latest.assign(label=latest["name"] + " (" + latest["party"].str[0] + "-" + latest["state_abbrev"] + ", "
                       + latest["chamber"] + ")")
dupes = latest["label"].duplicated(keep=False)
latest.loc[dupes, "label"] = latest.loc[dupes, "label"] + " #" + latest.loc[dupes, "icpsr"].astype(str)
options = dict(zip(latest.sort_values("label")["label"], latest.sort_values("label")["icpsr"]))

# A shared link opens a member directly: ?member=<Bioguide ID>
bioguide_of = dict(zip(latest["icpsr"], latest["bioguide_id"]))
label_of = {bioguide_of[i]: lab for lab, i in options.items() if pd.notna(bioguide_of.get(i))}
linked = label_of.get(st.query_params.get("member", ""))
labels = list(options)
pick = st.selectbox("Find a member", labels, index=labels.index(linked) if linked else None,
                    placeholder="Type a name…", key="me_member")

if pick:
    icpsr = options[pick]
    rows = df[df["icpsr"] == icpsr].sort_values("congress")
    member = rows.iloc[-1]
    short = last_name(member["name"])
    bioguide = bioguide_of.get(icpsr, "")
    if bioguide:
        st.query_params["member"] = bioguide
    member_header(member["name"], member["party"], member["state_abbrev"], member["chamber"],
                  rows["congress"].min(), rows["congress"].max(), newest)
    member_facts(bioguide)
    share_bar(f"{display_name(member['name'])} ({member['party'][0]}-{member['state_abbrev']}): voting record on "
              "PartyCohesion", "Member_Explorer", {"member": bioguide} if bioguide else None)
    caucus = member.get("caucus")
    if member["party"] not in ("Democrat", "Republican") and pd.notna(caucus):
        st.caption(f"Caucuses with the {caucus}s, so party unity and Position Flips compare them with {caucus}s.")

    # Headline metrics
    scored = rows.dropna(subset=["party_unity_pct"])
    if scored.empty:
        unity = ("Party unity", "None", "No party-line votes scored")
    else:
        u = scored.iloc[-1]
        unity = (f"Party unity, {ordinal(u['congress'])}", f"{u['party_unity_pct']:.1f}%",
                 f"{int(u['votes_with_party']):,} of {int(u['unity_votes_cast']):,} party-line votes")
    overall = flip_scores(flips[flips["icpsr"] == icpsr])
    if overall.empty:
        flip = ("Position Flips", "No votes", "No votes in these categories")
    else:
        o = overall.iloc[0]
        n = int(o["matched_own"] + o["matched_other"])
        flip = ("Position Flips", o["label"],
                f"{o['shift']:+.0f} point shift, {n} matched votes" if o["label"] != "Not enough votes"
                else f"{int(o['n_own'] + o['n_other'])} votes, too few matched")
    ideo = member["nominate_dim1"]
    chambers = " and ".join(sorted(rows["chamber"].unique()))
    plat_rows, plat_cast, plat_against = platform_record(icpsr)
    platform = (("Against party platform", f"{plat_against} of {plat_cast}", "Platform Votes topics")
                if plat_cast else ("Against party platform", "None", "No counted Platform Votes"))
    metric_row([
        unity, flip, platform,
        ("Ideology score", f"{ideo:.2f}" if pd.notna(ideo) else "None", "−1 liberal to +1 conservative"),
        ("In this data since", str(2 * int(rows["congress"].min()) + 1787),
         f"{rows['congress'].nunique()} Congress{'es' if rows['congress'].nunique() > 1 else ''}, {chambers}"
         + (" (data starts in 2007)" if int(rows["congress"].min()) == int(df["congress"].min()) else "")),
    ])

    # Same question, different president
    st.subheader("Same question, different president")
    st.markdown("How often this member gave the president room on the same kinds of votes, under their own party's "
                "presidents and under the other party's.")
    table_rows = []
    for cat in CATEGORIES:
        s = flip_scores(flips[(flips["icpsr"] == icpsr) & (flips["category"] == cat)])
        if s.empty:
            continue
        r = s.iloc[0]
        own = f"{r['rate_own']:.0f}% of {int(r['n_own'])}" if r["n_own"] else "None"
        other = f"{r['rate_other']:.0f}% of {int(r['n_other'])}" if r["n_other"] else "None"
        shift = f"{r['shift']:+.0f}" if pd.notna(r["shift"]) else "None"
        table_rows.append([cat, own, other, shift, pattern_badge(r["label"])])
    if table_rows:
        html_table(["Type of vote", "Own party's president", "Other party's president", "Shift", "Pattern"], table_rows,
                   raw_cols=(4,), muted_cols=(1, 2))
        st.caption("The first two columns count every vote. The shift compares only matched votes: the same type of "
                   "vote, cast when the member's party was in the same position in the chamber.")
        st.page_link("views/9_How_It_Works.py", label="How this is measured")
    else:
        st.caption("This member cast no Yea or Nay votes on debt limit, funding, disaster aid or war powers bills in this data.")

    # Platform Votes
    st.subheader("Votes on their party's platform")
    if plat_rows.empty:
        st.caption("No votes in this data on topics where the Democratic and Republican platforms take opposite, "
                   "specific positions.")
    else:
        side = plat_rows["side"].iloc[-1]
        st.markdown(f"On topics where the two parties' platforms take opposite positions, {short} voted against the "
                    f"{side} platform on **{plat_against} of {plat_cast}** topics they cast a counted vote on.")
        show_all = st.toggle("Include procedural and related votes (not counted)", key="me_plat_all")
        shown = plat_rows if show_all else plat_rows[plat_rows["counts"]]
        html_table(["Date", "Vote", "Their vote", "Matches their platform"] + (["Counted"] if show_all else []),
                   [[fmt_date(x.date), x.measure, x.vote, "No" if x.against else "Yes"]
                    + (["Yes" if x.counts else "No"] if show_all else [])
                    for x in shown.sort_values("date", ascending=False).itertuples()], muted_cols=(0,))
        st.caption("A platform is the party's official policy document, not a personal promise, and members often give "
                   "reasons a roll call can't show. Procedural and related votes are shown but not counted.")
        st.page_link("views/11_Platform_Votes.py", label="See every topic and the rules")

    # Campaign statements (House members, 2018 to 2022 campaigns)
    camp = load_campaign()
    mine_camp = camp[camp["icpsr"] == icpsr].sort_values(["campaign_year", "topic"], ascending=[False, True])
    if not mine_camp.empty:
        st.subheader("Campaign statements and votes")
        n_diff = int((mine_camp["same_direction"] == "No").sum())
        n_same = int((mine_camp["same_direction"] == "Yes").sum())
        st.markdown(f"What {short}'s own campaign website said, next to their vote on the closest roll call after "
                    f"that election. **{n_same} of {len(mine_camp)}** votes went in the same direction"
                    + (f"; **{n_diff}** went in a different direction." if n_diff else "."))
        html_table(["Campaign", "Topic", "Stance", "Campaign website text", "Vote", "Their vote", "Same direction"],
                   [[str(x.campaign_year), x.topic, x.stance, x.statement, x.vote_label, x.actual_vote,
                     x.same_direction] for x in mine_camp.itertuples()], muted_cols=(0,))
        st.caption("Statements come from CampaignView's collection of House candidates' campaign websites. A roll call "
                   "can't show a member's reasons, and the bill voted on is rarely the campaign promise word for word.")
        st.page_link("views/13_Campaign_Statements.py", label="See every topic and how stances are coded")

    # Missed votes
    missed_all = load_missed()
    mine_missed = missed_all[missed_all["icpsr"] == icpsr].sort_values(["congress", "chamber"], ascending=[False, True])
    if not mine_missed.empty:
        st.subheader("Missed votes")
        medians = missed_all.groupby(["congress", "chamber"])["missed_pct"].median()
        tot_missed, tot_held = int(mine_missed["missed"].sum()), int(mine_missed["eligible"].sum())
        st.markdown(f"{short} missed **{tot_missed:,} of {tot_held:,}** roll calls held while they served "
                    f"({100 * tot_missed / tot_held:.1f}%) since 2007.")
        html_table(["Congress", "Chamber", "Missed", "Roll calls held while serving", "Share", "Chamber median"],
                   [[ordinal(int(x.congress)), x.chamber, f"{int(x.missed):,}", f"{int(x.eligible):,}",
                     f"{x.missed_pct:.1f}%", f"{medians.loc[(x.congress, x.chamber)]:.1f}%"]
                    for x in mine_missed.itertuples()], muted_cols=(3, 5))
        st.caption(MISSED_NOTE)

    # Party unity over time
    if len(scored) > 1:
        st.subheader("Party unity over time")
        compare_party = caucus if pd.notna(caucus) else member["party"]
        avg = (df[df["caucus"] == compare_party].groupby(["congress", "chamber"])["party_unity_pct"].mean()
               .reset_index().rename(columns={"party_unity_pct": "party_avg"}))
        hist = scored.merge(avg, on=["congress", "chamber"], how="left")
        fig_h = px.line(hist, x="congress", y=["party_unity_pct", "party_avg"], markers=True,
                        labels={"congress": "Congress", "value": "Party Unity %", "variable": ""},
                        color_discrete_sequence=[ACCENT, MUTED])
        names = {"party_unity_pct": short, "party_avg": f"{compare_party} average, same chamber"}
        fig_h.for_each_trace(lambda t: t.update(name=names.get(t.name, t.name)))
        fig_h.update_layout(height=360, xaxis=dict(dtick=1), legend=dict(orientation="h", y=-0.25, x=0))
        show_chart(fig_h, f"Party unity across Congresses: {display_name(member['name'])}",
                   f"party_unity_history_{short.lower().replace(' ', '_')}")

    # How often they voted with each president's stated position (White House statements, 2009 on)
    sup_rows = []
    for (cong, cham), _ in rows.groupby(["congress", "chamber"]):
        ps = president_support(int(cong), cham)
        if ps.empty:
            continue
        ps = ps.merge(df[(df["congress"] == cong) & (df["chamber"] == cham)][["icpsr", "caucus"]], on="icpsr", how="left")
        mine = ps[ps["icpsr"] == icpsr]
        peers = ps[(ps["caucus"] == caucus) & (ps["votes"] > 0)]
        for pres, grp in mine.groupby("president", sort=False):
            pp = peers[peers["president"] == pres]
            sup_rows.append({"president": pres, "president_party": grp["president_party"].iloc[0],
                             "votes": int(grp["votes"].sum()), "agreed": int(grp["agreed"].sum()),
                             "peer_votes": int(pp["votes"].sum()), "peer_agreed": int(pp["agreed"].sum())})
    sup = pd.DataFrame(sup_rows)
    if not sup.empty:
        sup = sup.groupby(["president", "president_party"], sort=False).sum().reset_index()
        sup = sup[sup["votes"] > 0]
    if not sup.empty:
        st.subheader("Voted with the president's stated position")
        st.markdown("Bills where the White House published a position before the vote (2009 on). This shows whose "
                    "positions this member sided with. It is **not** a consistency score: agreeing more with one "
                    "party's presidents can simply reflect a member's views.")
        metric_row([(f"{r.president} ({r.president_party[0]})", f"{r.agreed / r.votes * 100:.0f}%",
                     f"{r.agreed} of {r.votes} votes · {caucus or member['party']} average "
                     f"{r.peer_agreed / r.peer_votes * 100:.0f}%" if r.peer_votes else f"{r.agreed} of {r.votes} votes")
                    for r in sup.itertuples()])

    # Where they sit within their party
    peers = df[(df["congress"] == member["congress"]) & (df["chamber"] == member["chamber"])
               & (df["party"] == member["party"])]
    if len(peers) > 5 and pd.notna(ideo):
        st.subheader("Where they sit in their party")
        fig = px.histogram(peers, x="nominate_dim1", nbins=25, labels={"nominate_dim1": "Ideology score (DW-NOMINATE)"},
                           color_discrete_sequence=[PARTY_COLORS.get(member["party"], MUTED)])
        fig.add_vline(x=ideo, line_dash="dash", line_color=ACCENT, annotation_text=short, annotation_position="top")
        fig.update_layout(height=340, yaxis_title="Members")
        show_chart(fig, f"{short} among {member['party']}s in the {member['chamber']}, {ordinal(member['congress'])} Congress",
                   f"ideology_position_{short.lower().replace(' ', '_')}_{int(member['congress'])}")
    # Full voting record
    st.subheader("Voting record")
    side = caucus if pd.notna(caucus) else member["party"]
    st.markdown(f"Every roll call {short} was eligible for while in office, from 2007 on. A vote is flagged when "
                f"{short} voted against the {side} majority.")
    record = member_record(icpsr, rows, load_votes())
    if record.empty:
        st.caption("No roll-call records found for this member.")
    else:
        cast = record["their_vote"].isin(["Yea", "Nay"])
        sided = record["with_party"] | record["against_party"]
        against = int(record["against_party"].sum())
        metric_row([
            ("Votes cast", f"{int(cast.sum()):,}", f"of {len(record):,} roll calls while in office"),
            (f"Against the {side} majority", f"{against:,}",
             f"{against / sided.sum() * 100:.1f}% of {int(sided.sum()):,} votes where the party took a side" if sided.any()
             else "No votes where the party took a side"),
            ("Missed votes", f"{int((~cast).sum()):,}", f"{(~cast).mean() * 100:.1f}% of roll calls"),
        ])
        r1, r2, r3 = st.columns([2, 1, 1])
        with r1:
            rq = st.text_input("Search this record", "", key="me_rec_q", placeholder="Bill number or words in the title")
        with r2:
            served = sorted(record["congress"].unique(), reverse=True)
            rc_pick = st.selectbox("Congress", ["All", *served], key="me_rec_cong",
                                   format_func=lambda c: "All" if c == "All" else ordinal(c))
        with r3:
            only_against = st.toggle("Only votes against party", key="me_rec_against")
        view = search_votes(record, rq, None if rc_pick == "All" else int(rc_pick))
        if only_against:
            view = view[view["against_party"]]
        st.dataframe(pd.DataFrame({
            "Date": view["date"],
            "Chamber": view["chamber"],
            "Bill": view["bill_number"].fillna(""),
            "Vote": view["label"],
            "Their vote": view["their_vote"],
            f"{side} majority": view["party_position"].replace({"Tie": "Split evenly", "None": "None"}),
            "Against party": view["against_party"].map({True: "Yes", False: ""}),
            "Result": view["vote_result"],
            "Voteview": [voteview_url(c, ch, r) for c, ch, r in zip(view["congress"], view["chamber"], view["rollnumber"])],
        }).head(1000), width="stretch", hide_index=True, height=400,
            column_config={"Vote": st.column_config.TextColumn(width="large"),
                           "Voteview": st.column_config.LinkColumn(display_text="Open")})
        if len(view) > 1000:
            st.caption(f"Showing the 1,000 most recent of {len(view):,}. Search or pick a Congress to narrow it.")
        st.page_link("views/10_All_Votes.py", label="Search every vote and see who broke ranks")
else:
    if "member" in st.query_params:
        del st.query_params["member"]
    st.info("Start typing a last name to see a member's profile, or browse everyone below.")
    share_bar("Look up how any member of Congress votes, on PartyCohesion", "Member_Explorer")

# ---------------------------------------------------------------------------
# Browse
# ---------------------------------------------------------------------------
st.write("")
with st.expander("Browse all members in a Congress", expanded=not pick):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        congress = st.selectbox("Congress", sorted(df["congress"].unique(), reverse=True), key="me_cong",
                                format_func=ordinal)
    with c2:
        chamber = st.selectbox("Chamber", ["All", "House", "Senate"], key="me_cham")
    with c3:
        party_filter = st.selectbox("Party", ["All", "Democrat", "Republican", "Independent"], key="me_party")
    with c4:
        search = st.text_input("Name or state", "", key="me_search", placeholder="e.g. Smith or TX")
    only_camp = st.toggle("Only members with campaign statements", key="me_only_camp")
    camp_counts = load_campaign().groupby("icpsr").agg(
        camp_n=("stance", "size"), camp_diff=("same_direction", lambda x: int((x == "No").sum()))).reset_index()
    filtered = (df[df["congress"] == congress]
                .merge(load_missed()[["congress", "chamber", "icpsr", "missed", "missed_pct"]],
                       on=["congress", "chamber", "icpsr"], how="left")
                .merge(camp_counts, on="icpsr", how="left"))
    if chamber != "All":
        filtered = filtered[filtered["chamber"] == chamber]
    if party_filter != "All":
        filtered = filtered[filtered["party"] == party_filter]
    if search:
        filtered = filtered[filtered["name"].str.contains(search, case=False, na=False)
                            | filtered["state_abbrev"].str.contains(search, case=False, na=False)]
    if only_camp:
        filtered = filtered[filtered["camp_n"].notna()]
    st.caption(f"{len(filtered)} members")
    st.dataframe(
        filtered[["name", "chamber", "state_abbrev", "party", "party_unity_pct", "unity_votes_cast", "missed",
                  "missed_pct", "camp_n", "camp_diff", "nominate_dim1", "cohesion_proxy"]].rename(columns={
            "name": "Name", "chamber": "Chamber", "state_abbrev": "State", "party": "Party",
            "party_unity_pct": "Party Unity %", "unity_votes_cast": "Party-Line Votes Cast",
            "missed": "Missed Votes", "missed_pct": "Missed %", "camp_n": "Campaign Statements",
            "camp_diff": "Voted Differently",
            "nominate_dim1": "Ideology Score", "cohesion_proxy": "Cohesion Proxy"}).sort_values("Name"),
        width="stretch", height=420, hide_index=True,
    )

st.markdown("---")
st.caption("Click a column heading to sort. " + MISSED_NOTE)
st.caption("Campaign statements count the clear positions a House member's own 2018, 2020 or 2022 campaign website "
           "took on a topic in Campaign Statements and Votes; voted differently counts the ones where their later vote "
           "went the other direction. Open a member's profile to read them.")
st.caption("Party unity % is the share of party-line votes (a majority of Democrats opposed a majority of Republicans) "
           "on which the member voted with their own party's majority, computed from Voteview roll-call records. "
           "Ideology scores are DW-NOMINATE first-dimension estimates. The cohesion proxy reflects distance from the "
           "party median within the same chamber and Congress.")
