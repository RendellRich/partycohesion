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
from seat_map import seat_map
from theme import narrow
from state_map import DELEGATE_PLACES
from state_splits import MIN_SHARED, load_all, member_summary
from flip_utils import add_chamber_control, flip_scores
from platform_utils import platform_record
from ui import (notice, bill_label, page_title, party_adj, explainer, display_name, fmt_date, html_table, inject_css, intro, last_name, member_header, metric_row,
                party_tag, pattern_badge, share_bar, STATES)
from vote_index import load_votes, member_record, search_votes, voteview_url
import floor_remarks

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


CAMPAIGN_MONEY = "https://campaign-money.streamlit.app/"


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
    if d["in_office"]:
        # A separate site on purpose: campaign money is never shown next to votes here.
        lines.append(f'Campaign money: <a href="{CAMPAIGN_MONEY}?member={escape(bioguide)}" target="_blank" '
                     'rel="noopener">individual donations by industry</a> on Campaign Money by Industry, a separate site')
    st.markdown(f'<div class="pc-person">{photo}<div class="pc-facts">{"<br>".join(lines)}</div></div>',
                unsafe_allow_html=True)


@st.cache_data
def load_campaign():
    """Campaign website statements and the vote that followed (built by scripts/campaign_statements.py)."""
    return pd.read_csv(DATA_DIR / "campaign_statement_votes.csv")


@st.cache_data
def load_floor_remarks():
    return floor_remarks.load_index()


@st.cache_data
def load_vote_changes():
    """Same bill, different vote (built by scripts/vote_changes.py)."""
    path = DATA_DIR / "vote_changes.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame(columns=["icpsr"])


DELEGATE_NOTE = ("Delegates and the Resident Commissioner can vote only on some House roll calls, mostly amendments, "
                 "and only in Congresses whose rules allow it. Their counts here include only those roll calls, and "
                 "they appear in this data only in those Congresses.")
# Roll calls that decide something (passage, a resolution, a nomination, a conference report, a veto override),
# as opposed to amendments and procedural steps like cloture
FINAL_VOTES = (r"On Passage|Suspend the Rules and (?:Pass|Agree)|On the Nomination|On Agreeing to the Resolution|"
               r"On the (?:Joint |Concurrent )?Resolution|Conference Report|Overrid|On the Bill")
SMALL_SAMPLE = 50  # below this many party-line votes, a party unity rate is shown as a small sample

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
def house_summary() -> pd.DataFrame:
    """Every House member's average split with their state's same-party colleagues, each Congress."""
    _, _, _, pairs = load_all()
    return member_summary(pairs[pairs["chamber"] == "House"])


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

# One entry per person, labeled the way people say the name ("Ted Cruz (R-TX, Senate)", the same as the Home lookup,
# so "Ted Cruz" or "Cruz" both find him), listed by last name
latest = df.sort_values("congress").groupby("icpsr").tail(1)
latest = latest.assign(label=[f"{display_name(n)} ({p[0]}-{s}, {c})" for n, p, s, c in
                              zip(latest["name"], latest["party"], latest["state_abbrev"], latest["chamber"])],
                       sort_key=[last_name(n).lower() + " " + display_name(n).lower() for n in latest["name"]])
dupes = latest["label"].duplicated(keep=False)
latest.loc[dupes, "label"] = latest.loc[dupes, "label"] + " #" + latest.loc[dupes, "icpsr"].astype(str)
ordered = latest.sort_values("sort_key")
options = dict(zip(ordered["label"], ordered["icpsr"]))

# A shared link opens a member directly: ?member=<Bioguide ID>
bioguide_of = dict(zip(latest["icpsr"], latest["bioguide_id"]))
label_of = {bioguide_of[i]: lab for lab, i in options.items() if pd.notna(bioguide_of.get(i))}
linked = label_of.get(st.query_params.get("member", ""))
labels = list(options)
if "me_pending" in st.session_state:  # a seat clicked on the map below opens that member
    st.session_state["me_member"] = st.session_state.pop("me_pending")
# Which member is open, worked out before the picker is drawn so a member's page can lead with their name. The picker
# itself sits under the member's numbers; without a member it sits under the page intro as before.
pick = st.session_state["me_member"] if "me_member" in st.session_state else linked
PAGE_INTRO = ("Look up any member of Congress since 2007: how often they vote with their party, whether their votes "
              "change with the White House, and where they sit ideologically.")
PAGE_EXPLAINER = ("A member's record shows how often they side with their party, whether their votes shift when the "
                  "White House changes hands, and, for many House members, what their campaign website said. High party "
                  "unity is normal in today's Congress, so the votes where a member breaks from their party usually "
                  "tell you the most.")


def member_picker(label: str) -> str | None:
    # Same label and key in both places, so switching layouts keeps the widget's state
    return st.selectbox(label, labels, index=labels.index(linked) if linked else None, placeholder="Type a name…",
                        key="me_member")


if not pick:
    st.title("Members")
    intro(PAGE_INTRO, shortcuts=False)
    explainer(PAGE_EXPLAINER)
    pick = member_picker("Find a member")

if pick:
    icpsr = options[pick]
    rows = df[df["icpsr"] == icpsr].sort_values("congress")
    member = rows.iloc[-1]
    short = last_name(member["name"])
    bioguide = bioguide_of.get(icpsr, "")
    if bioguide:
        st.query_params["member"] = bioguide
    page_title(display_name(member["name"]))
    # A member who left office partway through the newest Congress (death, resignation, a new office) is not "now"
    details = load_details()
    left = None
    if int(rows["congress"].max()) == newest and bioguide in details.index:
        d = details.loc[bioguide]
        if not d["in_office"] and str(d["last_year"]).isdigit():
            left = int(d["last_year"])
    # The member's name is the page title, so a shared link opens straight onto them
    member_header(member["name"], member["party"], member["state_abbrev"], member["chamber"],
                  rows["congress"].min(), rows["congress"].max(), newest, as_title=True, left=left)
    # How they voted lately, right under the name: "how did they vote" is why most visitors come. Final votes
    # (passage, resolutions, nominations) answer that; cloture, amendments and procedural roll calls stay in the full
    # record. One row per bill, its latest final vote. Bills come first, since a run of nominations says less about
    # what a member stands for; nominations fill in when there are fewer than five bills.
    caucus = member.get("caucus")
    side = caucus if pd.notna(caucus) else member["party"]
    record = member_record(icpsr, rows, load_votes())
    if not record.empty:
        newest_first = record.sort_values(["date", "rollnumber"], ascending=False)
        final = newest_first[newest_first["vote_question"].fillna("").str.contains(FINAL_VOTES, regex=True)]
        final = final[~final["bill_number"].fillna("").duplicated() | final["bill_number"].isna()]
        nomination = (final["vote_question"].fillna("").str.contains("Nomination")
                      | final["bill_number"].fillna("").str.startswith("PN"))
        bills = final[~nomination].head(5)
        # A delegate may have no final votes (they vote only on amendments); then their latest roll calls
        shown_votes = pd.concat([bills, final[nomination].head(5 - len(bills))]) if len(final) else newest_first.head(5)
        st.header("How they voted last" if left else "How they voted lately", anchor="recent-votes")

        def vote_name(x) -> str:
            text = x.label if len(x.label) <= 120 else x.label[:117].rsplit(" ", 1)[0] + "…"
            bill = x.bill_number if isinstance(x.bill_number, str) else ""
            if bill and not bill.startswith("PN") and not text.startswith(bill):  # nomination numbers mean little
                return f"{bill_label(bill)}: {text}"
            return text

        def vote_meta(x) -> str:
            parts = [fmt_date(x.date), f"{x.vote_result}." if isinstance(x.vote_result, str) else ""]
            if x.their_vote in ("Yea", "Nay") and x.party_position in ("Yea", "Nay"):
                parts.append(f"Voted {'with' if x.their_vote == x.party_position else 'against'} most {side}s.")
            elif x.party_position == "Tie":
                parts.append(f"{side}s split evenly.")
            return f"{parts[0]}. " + " ".join(p for p in parts[1:] if p)

        def chip(v: str) -> str:
            cls = {"Yea": "pc-vote pc-vote-yea", "Nay": "pc-vote"}.get(v, "pc-vote pc-vote-other")
            word = "Didn't vote" if v == "Did not vote" else v
            return f'<span class="{cls}">{escape(word)}</span>'

        items = "".join(f'<li>{chip(x.their_vote)}<div><p class="pc-lately-title">{escape(vote_name(x))}</p>'
                        f'<p class="pc-lately-meta">{escape(vote_meta(x))}</p></div></li>'
                        for x in shown_votes.itertuples())
        which = "last" if left else "most recent"
        st.markdown(f'<ul class="pc-lately" aria-label="{escape(short)}&#39;s {which} votes">{items}</ul>',
                    unsafe_allow_html=True)
        st.markdown(f'<p class="pc-muted">{"Final votes on bills and resolutions, then nominations, newest first. " if len(final) else ""}'
                    '<a class="pc-link-target" href="#voting-record">Search every vote in their record</a></p>',
                    unsafe_allow_html=True)

    # "On this page" links right under the name, filled in at the end once we know which sections this member has.
    # A member page runs to many phone screens, so the parts people look for are one tap away.
    jumps = st.empty()
    toc: list[tuple[str, str]] = []
    caucus = member.get("caucus")
    if member["party"] not in ("Democrat", "Republican") and pd.notna(caucus):
        st.caption(f"Caucuses with the {caucus}s, so party unity and Position Flips compare them with {caucus}s.")

    # Headline metrics
    scored = rows.dropna(subset=["party_unity_pct"])
    if scored.empty:
        unity = ("Party unity", "Not scored", "No party-line votes yet")
    else:
        latest_u = scored.iloc[-1]
        full = scored[scored["unity_votes_cast"] >= SMALL_SAMPLE]
        # A short latest Congress (a new member, or one who left early) doesn't make the headline when an earlier,
        # full Congress exists; it goes in the note instead, so one vote never stands for a whole career
        u = full.iloc[-1] if int(latest_u["unity_votes_cast"]) < SMALL_SAMPLE and len(full) else latest_u
        cast_n = int(u["unity_votes_cast"])
        if cast_n < SMALL_SAMPLE:
            # A handful of votes can't carry a decimal place, and the reader should know the record is short
            so_far = " so far" if int(u["congress"]) == newest and not left else ""
            unity = (f"Party unity, {ordinal(u['congress'])}", f"{u['party_unity_pct']:.0f}%",
                     f"Small sample: {int(u['votes_with_party']):,} of {cast_n:,} party-line vote"
                     f"{'' if cast_n == 1 else 's'}{so_far}")
        else:
            # Next to what's typical for their party in their chamber, so a high number reads as normal or not
            grp = member["caucus"] if pd.notna(member.get("caucus")) else member["party"]
            peers = df[(df["congress"] == u["congress"]) & (df["chamber"] == u["chamber"])
                       & (df["caucus"].fillna(df["party"]) == grp)]["party_unity_pct"]
            who = {"Senate": "senator", "House": "House member"}.get(u["chamber"], "member")
            note = (f"{int(u['votes_with_party']):,} of {cast_n:,} party-line votes; typical {party_adj(grp)} {who} "
                    f"{peers.median():.1f}%")
            if u is not latest_u:
                n_last = int(latest_u["unity_votes_cast"])
                note += (f". {ordinal(latest_u['congress'])}: only {n_last} party-line vote{'' if n_last == 1 else 's'}"
                         + (" so far" if int(latest_u["congress"]) == newest and not left else ""))
            unity = (f"Party unity, {ordinal(u['congress'])}", f"{u['party_unity_pct']:.1f}%", note)
    overall = flip_scores(flips[flips["icpsr"] == icpsr])
    if overall.empty:
        flip = ("Position Flips", "No votes", "No votes in these categories")
    else:
        o = overall.iloc[0]
        n = int(o["matched_own"] + o["matched_other"])
        flip = ("Position Flips", o["label"],
                f"{o['shift']:+.0f} point shift, {n} matched votes" if o["label"] != "Not enough votes"
                else f"{int(o['n_own'] + o['n_other'])} vote{'' if int(o['n_own'] + o['n_other']) == 1 else 's'}, "
                "too few matched")
    ideo = member["nominate_dim1"]
    chambers = " and ".join(sorted(rows["chamber"].unique()))
    plat_rows, plat_cast, plat_against = platform_record(icpsr)
    platform = (("Against party platform", f"{plat_against} of {plat_cast}", "Platform Votes topics")
                if plat_cast else ("Against party platform", "No votes", "No counted Platform Votes"))
    delegate = member["chamber"] == "House" and member["state_abbrev"] in DELEGATE_PLACES
    first_cong = int(rows["congress"].min())
    since = 2 * first_cong + 1787
    joined = details.loc[bioguide, "first_year"] if bioguide in details.index else ""
    if str(joined).isdigit() and since < int(joined) <= since + 1:  # joined in the second year of that Congress
        since = int(joined)
    n_cong = rows["congress"].nunique()
    metric_row([
        unity, flip, platform,
        ("Ideology score", f"{ideo:.2f}" if pd.notna(ideo) else "Not scored", "−1 liberal to +1 conservative"),
        ("In this data since", str(since),
         f"{n_cong} Congress{'es' if n_cong > 1 else ''}, {chambers}"
         + (" (data starts in 2007)" if first_cong == int(df["congress"].min()) else "")
         + ("; delegates appear only in Congresses where they could vote" if delegate else "")),
    ])
    member_facts(bioguide)

    def section(title: str, anchor: str, jump: str | None = None) -> None:
        st.header(title, anchor=anchor)
        if jump:
            toc.append((jump, anchor))

    # Their seat in the chamber, in their most recent Congress
    room = (df[(df["congress"] == member["congress"]) & (df["chamber"] == member["chamber"])]
            .drop_duplicates("icpsr", keep="last").copy())
    room["label"] = [f"{display_name(r.name)} ({r.party[0]}-{r.state_abbrev})" for r in room.itertuples()]
    if pd.notna(ideo) and room["nominate_dim1"].notna().all():
        when = "this Congress" if int(member["congress"]) == newest else f"the {ordinal(member['congress'])} Congress"
        seat_event = show_chart(seat_map(room, member["chamber"], highlight=icpsr, highlight_name=short),
                                f"{display_name(member['name'])} in the {member['chamber']}, {ordinal(member['congress'])} Congress",
                                f"seat_map_{short.lower().replace(' ', '_')}",
                                key=f"me_seat_{icpsr}_{st.session_state.get('me_seat_clicks', 0)}",
                                on_select=None if narrow() else "rerun")  # phones: a tap shows who, it doesn't navigate
        st.caption(f"Every member who served in the {member['chamber']} in {when}, one dot each, placed left to right "
                   f"by Voteview ideology score. {short}'s seat is ringed. "
                   + ("Tap any other dot to see who it is." if narrow() else "Click any other dot to open that member."))
        clicked = seat_event.get("selection", {}).get("points", []) if seat_event and not narrow() else []
        target = clicked[0].get("customdata", [None, None, ""])[2] if clicked else ""
        if target and target != bioguide and target in label_of:
            st.session_state["me_pending"] = label_of[target]
            st.session_state["me_seat_clicks"] = st.session_state.get("me_seat_clicks", 0) + 1
            st.rerun()

    # Same question, different president
    section("Same question, different president", "position-flips", "Position Flips")
    st.markdown("How often this member gave the president room on the same kinds of votes, under their own party's "
                "presidents and under the other party's.")
    def flip_row(name: str, r: pd.Series, alone: bool) -> list[str]:
        own = f"{r['rate_own']:.0f}% of {int(r['n_own'])}" if r["n_own"] else "No votes"
        other = f"{r['rate_other']:.0f}% of {int(r['n_other'])}" if r["n_other"] else "No votes"
        shift = f"{r['shift']:+.0f}" if pd.notna(r["shift"]) else "Too few to compare"
        # One type of vote on its own often has too few matched votes even when all four together have enough
        pattern = ('<span style="color:var(--pc-muted)">Too few to tell on its own</span>'
                   if alone and r["label"] == "Not enough votes" else pattern_badge(r["label"]))
        return [name, own, other, shift, pattern]

    table_rows = []
    for cat in CATEGORIES:
        s = flip_scores(flips[(flips["icpsr"] == icpsr) & (flips["category"] == cat)])
        if not s.empty:
            table_rows.append(flip_row(cat, s.iloc[0], alone=True))
    if len(table_rows) > 1 and not overall.empty:
        table_rows.insert(0, flip_row("All types together", overall.iloc[0], alone=False))
    if table_rows:
        html_table(["Type of vote", "Own party's president", "Other party's president", "Shift", "Pattern"], table_rows,
                   raw_cols=(4,), muted_cols=(1, 2), label="Same question, different president", stack=True)
        st.caption("The own-party and other-party shares count every vote. The shift compares only matched votes: the "
                   "same type of vote, cast when the member's party was in the same position in the chamber. The "
                   "Position Flips result at the top of the page pools all the types together, so it can show a "
                   "pattern even when each type alone has too few matched votes.")
        st.page_link("views/9_How_It_Works.py", label="How this is measured")
    else:
        st.caption("This member cast no Yea or Nay votes on debt limit, funding, disaster aid or war powers bills in this data.")

    # Platform Votes
    section("Votes on their party's platform", "platform", "Platform")
    if plat_rows.empty:
        st.caption("No votes in this data on topics where the Democratic and Republican platforms take opposite, "
                   "specific positions.")
    else:
        side = plat_rows["side"].iloc[-1]
        st.markdown(f"On topics where the two parties' platforms take opposite positions, {short} voted against the "
                    f"{party_adj(side)} platform on **{plat_against} of {plat_cast}** topics they cast a counted vote on.")
        show_all = st.toggle("Include procedural and related votes (not counted)", key="me_plat_all")
        shown = plat_rows if show_all else plat_rows[plat_rows["counts"]]
        html_table(["Vote", "Date", "Their vote", "Matches their platform"] + (["Counted"] if show_all else []),
                   [[x.measure, fmt_date(x.date), x.vote, "No" if x.against else "Yes"]
                    + (["Yes" if x.counts else "No"] if show_all else [])
                    for x in shown.sort_values("date", ascending=False).itertuples()], muted_cols=(1,),
                   label="Votes on their party's platform", stack=True, limit=5)
        st.caption("A platform is the party's official policy document, not a personal promise, and members often give "
                   "reasons a roll call can't show. Procedural and related votes are shown but not counted.")
        st.page_link("views/11_Platform_Votes.py", label="See every topic and the rules")

    # Campaign statements (House members, 2018 to 2022 campaigns)
    camp = load_campaign()
    mine_camp = camp[camp["icpsr"] == icpsr].sort_values(["campaign_year", "topic"], ascending=[False, True])
    if not mine_camp.empty:
        section("Campaign statements and votes", "campaign")
        n_diff = int((mine_camp["same_direction"] == "No").sum())
        n_same = int((mine_camp["same_direction"] == "Yes").sum())
        st.markdown(f"What {short}'s own campaign website said, next to their vote on the closest roll call after "
                    f"that election. **{n_same} of {len(mine_camp)}** votes went in the same direction"
                    + (f"; **{n_diff}** went in a different direction." if n_diff else "."))
        html_table(["Topic", "Campaign", "Stance", "Campaign website text", "Vote", "Their vote", "Same direction"],
                   [[x.topic, str(x.campaign_year), x.stance, x.statement, x.vote_label, x.actual_vote,
                     x.same_direction] for x in mine_camp.itertuples()], muted_cols=(1,),
                   label="Campaign statements and votes", stack=True, wide_cols=(3, 4), limit=5)
        st.caption("Statements come from CampaignView's collection of House candidates' campaign websites. A roll call "
                   "can't show a member's reasons, and the bill voted on is rarely the campaign promise word for word.")
        st.page_link("views/13_Campaign_Statements.py", label="See every topic and how stances are coded")

    # Same bill, different vote
    vch = load_vote_changes()
    mine_vch = vch[vch["icpsr"] == icpsr].sort_values("final_date", ascending=False)
    if not mine_vch.empty:
        section("Same bill, different vote", "same-bill")
        n_apart = int(mine_vch["apart"].sum())
        st.markdown(f"Bills where {short} voted Yea at one stage and Nay at another, in the same chamber and Congress: "
                    f"**{len(mine_vch)}**." + (f" On **{n_apart}** of them, most of their party voted the same way both "
                                               "times." if n_apart else ""))
        html_table(["Bill", "Title now", "First vote", "Final vote", "Their party"],
                   [[bill_label(x.bill_number), x.title if isinstance(x.title, str) and x.title else x.first_vote_desc,
                     f"{x.first_vote} · {x.first_stage} · {fmt_date(x.first_date)}",
                     f"{x.final_vote} · {x.final_stage} · {fmt_date(x.final_date)}",
                     f"{x.party_first} then {x.party_final}"] for x in mine_vch.itertuples()], muted_cols=(0,),
                   label="Same bill, different vote", stack=True, wide_cols=(1, 2, 3), limit=5)
        st.caption("The bill's text often changes between votes, and a roll call can't show a member's reasons.")
        st.page_link("views/14_Same_Bill_Different_Vote.py", label="See every bill and how changes are counted")

    # Same state, different vote
    _, _, _, state_pairs = load_all()
    mine_sp = state_pairs[(state_pairs["icpsr_a"] == icpsr) | (state_pairs["icpsr_b"] == icpsr)]
    sen_pairs = mine_sp[(mine_sp["chamber"] == "Senate") & (mine_sp["both_voted"] >= MIN_SHARED["Senate"])]
    # Ranks need every pair in the delegation, not only this member's, so summarize the whole House once
    all_house = house_summary() if (mine_sp["chamber"] == "House").any() else None
    house_rows = all_house[all_house["icpsr"] == icpsr] if all_house is not None else mine_sp.iloc[0:0]
    if len(sen_pairs) or len(house_rows):
        section("Same state, different vote", "same-state")
        st.markdown(f"How often {short} cast the opposite vote from members of Congress from the same state, on roll "
                    "calls both voted on.")
        if len(sen_pairs):
            sen_all = state_pairs[(state_pairs["chamber"] == "Senate") & state_pairs["same_side"]]
            typical = sen_all.groupby("congress")["split_pct"].median()
            rows_sp = []
            for r in sen_pairs.sort_values("congress", ascending=False).itertuples():
                mine_a = r.icpsr_a == icpsr
                other, other_party = (r.name_b, r.party_b) if mine_a else (r.name_a, r.party_a)
                rows_sp.append([ordinal(int(r.congress)), display_name(other), party_tag(other_party),
                                f"{r.splits:,} of {r.both_voted:,}", f"{r.split_pct:.1f}%",
                                f"{typical.get(r.congress, float('nan')):.1f}%"])
            html_table(["Congress", "Other senator", "Party", "Split on", "Share", "Typical same-party pair"],
                       rows_sp, raw_cols=(2,), muted_cols=(5,), label="Splits with the other senator", stack=True, limit=1,
                       more=f"Show {len(rows_sp) - 1} earlier Congress{'es' if len(rows_sp) > 2 else ''}")
        if len(house_rows):
            typical_h = all_house[all_house["colleagues"] >= 2].groupby("congress")["avg_split"].median()
            html_table(["Congress", "Average split with their state's party", "Colleagues compared",
                        "Rank in that delegation", "Splits most with", "Typical member"],
                       [[ordinal(int(r.congress)), f"{r.avg_split:.1f}%", str(r.colleagues),
                         f"{r.rank} of {r.delegation}" + (" (splits most)" if r.rank == 1 and r.delegation > 1 else ""),
                         f"{display_name(r.most_split_with)} ({r.most_split_pct:.1f}%)",
                         f"{typical_h.get(r.congress, float('nan')):.1f}%"]
                        for r in house_rows.sort_values("congress", ascending=False).itertuples()],
                       muted_cols=(5,), label="Splits with House members of the same party", stack=True, limit=1,
                       more=f"Show {len(house_rows) - 1} earlier Congress{'es' if len(house_rows) > 2 else ''}")
        st.caption("Only Yea and Nay count. House comparisons are with members of the same party from the same "
                   f"state who shared at least {MIN_SHARED['House']} votes; senators are compared with their state's "
                   f"other senator when they shared at least {MIN_SHARED['Senate']} votes. A split is a fact about "
                   "the record, not a judgment.")
        state_now = member["state_abbrev"]
        st.markdown(f'<a class="pc-link-target" href="Same_State_Different_Vote?state={state_now}&chamber={member["chamber"].lower()}" '
                    f'target="_self">See every split vote for {STATES.get(state_now, state_now)}</a>',
                    unsafe_allow_html=True)

    # Missed votes
    missed_all = load_missed()
    mine_missed = missed_all[missed_all["icpsr"] == icpsr].sort_values(["congress", "chamber"], ascending=[False, True])
    if not mine_missed.empty:
        section("Missed votes", "missed-votes", "Missed votes")
        tot_missed, tot_held = int(mine_missed["missed"].sum()), int(mine_missed["eligible"].sum())
        if delegate:
            # Compared with the other delegates, who could vote on the same roll calls, not with the whole House
            places = df.loc[(df["chamber"] == "House") & df["state_abbrev"].isin(DELEGATE_PLACES), ["congress", "icpsr"]]
            peers_m = missed_all[missed_all["chamber"] == "House"].merge(places.drop_duplicates(), on=["congress", "icpsr"])
            medians = peers_m.groupby(["congress", "chamber"])["missed_pct"].median()
            held, typical = "Roll calls open to delegates", "Delegate median"
            st.markdown(f"{short} missed **{tot_missed:,} of {tot_held:,}** roll calls open to delegates while they "
                        f"served ({100 * tot_missed / tot_held:.1f}%) since {since}.")
        else:
            medians = missed_all.groupby(["congress", "chamber"])["missed_pct"].median()
            held, typical = "Roll calls held while serving", "Chamber median"
            st.markdown(f"{short} missed **{tot_missed:,} of {tot_held:,}** roll calls held while they served "
                        f"({100 * tot_missed / tot_held:.1f}%) since {since}.")
        html_table(["Congress", "Chamber", "Missed", held, "Share", typical],
                   [[ordinal(int(x.congress)), x.chamber, f"{int(x.missed):,}", f"{int(x.eligible):,}",
                     f"{x.missed_pct:.1f}%", f"{medians.loc[(x.congress, x.chamber)]:.1f}%"]
                    for x in mine_missed.itertuples()], muted_cols=(3, 5), label="Missed votes by Congress",
                   stack=True, limit=1,
                   more=f"Show {len(mine_missed) - 1} earlier Congress{'es' if len(mine_missed) > 2 else ''}")
        st.caption((DELEGATE_NOTE + " " if delegate else "") + MISSED_NOTE)

    # Party unity over time
    if len(scored) > 1:
        section("Party unity over time", "party-unity")
        compare_party = caucus if pd.notna(caucus) else member["party"]
        avg = (df[df["caucus"] == compare_party].groupby(["congress", "chamber"])["party_unity_pct"].mean()
               .reset_index().rename(columns={"party_unity_pct": "party_avg"}))
        hist = scored.merge(avg, on=["congress", "chamber"], how="left")
        fig_h = px.line(hist, x="congress", y=["party_unity_pct", "party_avg"], markers=True,
                        labels={"congress": "Congress", "value": "Party Unity %", "variable": ""},
                        color_discrete_sequence=[ACCENT, MUTED])
        names = {"party_unity_pct": short, "party_avg": f"{party_adj(compare_party)} average, same chamber"}
        fig_h.for_each_trace(lambda t: t.update(name=names.get(t.name, t.name)))
        fig_h.update_layout(height=380, xaxis=dict(dtick=1), margin=dict(l=10, r=10, b=10))
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
        section("Voted with the president's stated position", "president-position")
        st.markdown("Bills where the White House published a position before the vote (2009 on). This shows whose "
                    "positions this member sided with. It is **not** a consistency score: agreeing more with one "
                    "party's presidents can simply reflect a member's views.")
        metric_row([(f"{r.president} ({r.president_party[0]})", f"{r.agreed / r.votes * 100:.0f}%",
                     f"{r.agreed} of {r.votes} votes · {party_adj(caucus or member['party'])} average "
                     f"{r.peer_agreed / r.peer_votes * 100:.0f}%" if r.peer_votes else f"{r.agreed} of {r.votes} votes")
                    for r in sup.itertuples()])

    # Where they sit within their party
    peers = df[(df["congress"] == member["congress"]) & (df["chamber"] == member["chamber"])
               & (df["party"] == member["party"])]
    if len(peers) > 5 and pd.notna(ideo):
        section("Where they sit in their party", "ideology")
        fig = px.histogram(peers, x="nominate_dim1", nbins=25, labels={"nominate_dim1": "Ideology score (DW-NOMINATE)"},
                           color_discrete_sequence=[PARTY_COLORS.get(member["party"], MUTED)])
        fig.add_vline(x=ideo, line_dash="dash", line_color=ACCENT, annotation_text=short, annotation_position="top")
        fig.update_layout(height=340, yaxis_title="Members")
        show_chart(fig, f"{short} among {member['party']}s in the {member['chamber']}, {ordinal(member['congress'])} Congress",
                   f"ideology_position_{short.lower().replace(' ', '_')}_{int(member['congress'])}")
    # Full voting record
    section("Voting record", "voting-record", "Every vote")
    st.markdown(f"Every roll call {short} was eligible for while in office, from {since} on. A vote is flagged when "
                f"{short} voted against the {party_adj(side)} majority.")
    if record.empty:
        st.caption("No roll-call records found for this member.")
    else:
        cast = record["their_vote"].isin(["Yea", "Nay"])
        sided = record["with_party"] | record["against_party"]
        against = int(record["against_party"].sum())
        metric_row([
            ("Votes cast", f"{int(cast.sum()):,}", f"of {len(record):,} roll calls while in office"),
            (f"Against the {party_adj(side)} majority", f"{against:,}",
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
        view = view.head(1000)
        remarks = floor_remarks.attach(view, bioguide, load_floor_remarks()) if bioguide else None
        majority = view["party_position"].replace({"Tie": "Split evenly", "None": "No majority"})
        names = [(f"{bill_label(b)}: " if isinstance(b, str) and b and not b.startswith("PN")
                  and not str(lab).startswith(b) else "") + str(lab) for b, lab in zip(view["bill_number"], view["label"])]
        if narrow():
            # Phones: cards with their own vote beside each roll call, a few at a time, instead of a grid whose
            # "Their vote" column sits off screen
            more_key = f"me_rec_more_{icpsr}"
            n_show = st.session_state.get(more_key, 5)
            rows_html = []
            for i, x in enumerate(view.head(n_show).itertuples()):
                link = remarks.iloc[i] if remarks is not None and isinstance(remarks.iloc[i], str) else ""
                rows_html.append([escape(names[i]), fmt_date(x.date), escape(str(x.their_vote)),
                                  escape(str(majority.iloc[i])), escape(str(x.vote_result)),
                                  f'<a href="{escape(link)}" target="_blank" rel="noopener">Read</a>' if link
                                  else '<span class="pc-muted">None found</span>'])
            html_table(["Vote", "Date", "Their vote", f"{party_adj(side)} majority", "Result", "Their remarks"], rows_html,
                       raw_cols=(0, 2, 3, 4, 5), muted_cols=(1,), label=f"{short}'s voting record", stack=True,
                       wide_cols=(0,))
            if len(view) > n_show:
                if st.button(f"Show 10 more (of {len(view):,})", key=f"{more_key}_btn"):
                    st.session_state[more_key] = n_show + 10
                    st.rerun()
        else:
            one_chamber = view["chamber"].nunique() <= 1
            st.dataframe(pd.DataFrame({
                "Date": pd.to_datetime(view["date"]),
                **({} if one_chamber else {"Chamber": view["chamber"]}),
                "Vote": names,
                "Their vote": view["their_vote"],
                f"{party_adj(side)} majority": majority,
                "Against party": view["against_party"].map({True: "Yes", False: ""}),
                "Result": view["vote_result"],
                "Their remarks": remarks if remarks is not None else None,
                "Voteview": [voteview_url(c, ch, r) for c, ch, r in zip(view["congress"], view["chamber"], view["rollnumber"])],
            }), width="stretch", hide_index=True, height=400,
                column_config={"Date": st.column_config.DateColumn(format="MMM D, YYYY"),
                               "Vote": st.column_config.TextColumn(width="large"),
                               "Their remarks": st.column_config.LinkColumn(display_text="Read"),
                               "Voteview": st.column_config.LinkColumn(display_text="Open")})
        st.caption("Their remarks: where they spoke about that bill in the Congressional Record, within 30 days before "
                   "the vote or a week after. Available from 2007 on. Each link was checked against the Record's text: "
                   "a line explaining a missed vote or running the floor doesn't count. It shows where they spoke, not "
                   "what they said, so read it to see their reasons in their own words.")
        total_view = len(search_votes(record, rq, None if rc_pick == "All" else int(rc_pick)))
        if not only_against and total_view > 1000:
            st.caption(f"Showing the 1,000 most recent of {total_view:,}. Search or pick a Congress to narrow it.")
        st.page_link("views/10_All_Votes.py", label="Search every vote and see who broke ranks")

    if len(toc) >= 3:
        jumps.markdown('<nav class="pc-jumps" aria-label="On this page"><span>On this page</span>' + "".join(
            f'<a href="#{a}">{escape(t)}</a>' for t, a in toc) + "</nav>", unsafe_allow_html=True)
    # Sharing and looking up someone else come after the record, so they don't split the member's page in two
    share_bar(f"{display_name(member['name'])} ({member['party'][0]}-{member['state_abbrev']}): voting record on "
              "PartyCohesion", "Member_Explorer", {"member": bioguide} if bioguide else None)
    member_picker("Find a member")
    with st.expander("About this page"):
        st.markdown(PAGE_INTRO + "\n\n" + PAGE_EXPLAINER)
else:
    if "member" in st.query_params:
        del st.query_params["member"]
    notice("Start typing a last name to see a member's profile, or browse everyone below.")
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
        # Sorted by last name, shown first name first like the rest of the site
        filtered.sort_values("name").assign(name=lambda f: f["name"].map(display_name))[
                 ["name", "chamber", "state_abbrev", "party", "party_unity_pct", "unity_votes_cast", "missed",
                  "missed_pct", "camp_n", "camp_diff", "nominate_dim1", "cohesion_proxy"]].rename(columns={
            "name": "Name", "chamber": "Chamber", "state_abbrev": "State", "party": "Party",
            "party_unity_pct": "Party Unity %", "unity_votes_cast": "Party-Line Votes Cast",
            "missed": "Missed Votes", "missed_pct": "Missed %", "camp_n": "Campaign Statements",
            "camp_diff": "Voted Differently",
            "nominate_dim1": "Ideology Score", "cohesion_proxy": "Cohesion Proxy"}),
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
