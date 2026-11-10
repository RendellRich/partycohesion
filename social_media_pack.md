# PartyCohesion Social Post Pack

Neutral, data-first posts ready to pair with charts from the app.
Live app: https://partycohesion.streamlit.app

Numbers below come from the app's data files (Voteview roll calls through Sept. 30, 2026). They change as new votes are recorded, so re-check each number against the app before posting.

**Ready-made cards:** posts 11 to 14 come with finished images in `docs/social/` (wide 1200×627 for LinkedIn and X, tall 1080×1350 for Instagram and Facebook). Rebuild them after a data refresh with `python scripts/make_social_cards.py`. Each post can link to its share page instead of the app, so the link preview shows the card.

**How to get the chart:** open the page listed under each post, pick the download size in the sidebar (X or Instagram), then click the camera icon on the chart. Every chart already carries its title and the source line.

**Style rules:** describe, don't judge. Say "voted with their party's majority X% of the time," not "loyal" or "broke ranks to…". Name the source. Never imply motive.

---

## Post 1: Launch
**Chart:** Overview → Average Party Unity by Congress

PartyCohesion is live.

It shows how often each member of Congress votes with their own party, using the official roll-call record from Voteview. Every member, every Congress since 2007.

No scorecards. No commentary. Just the votes and the method.

https://partycohesion.streamlit.app

---

## Post 2: 119th Congress snapshot
**Chart:** Key Votes → Party Unity Rates (119th, House and Senate)

How often members of the 119th Congress voted with their own party on party-line votes:

Democrats: 96.2% on average
Republicans: 97.4% on average

Based on 1,313 roll calls where most Democrats and most Republicans voted on opposite sides.

Data: Voteview

---

## Post 3: The Senate over time
**Chart:** Overview → Average Party Unity by Congress (Senate panel)

Average party unity among Senate Republicans:

110th Congress (2007–08): 85.3%
119th Congress (2025–26): 98.6%

Senate Democrats over the same span: 91.6% and 95.3%.

Each member's rate is computed separately for each Congress.

Data: Voteview

---

## Post 4: Who votes against their party?
**Chart:** Key Votes → Members with the lowest party-unity rates (expand the table)

In the 119th Congress, members who voted with their own party less than 90% of the time on party-line votes:

House: 19 Democrats, 5 Republicans
Senate: 4 Democrats, 3 Republicans

Every member's rate, and the votes behind it, is searchable.

Data: Voteview

---

## Post 5: Hegseth confirmation
**Chart:** Key Votes → 119th → Senate → Cabinet Confirmations → Hegseth vote

Senate vote to confirm Pete Hegseth as Secretary of Defense, Jan. 24, 2025:

Total: 50 Yea, 50 Nay (tie broken by the Vice President)
Democrats: 0 Yea, 45 Nay
Republicans: 50 Yea, 3 Nay
Independents: 0 Yea, 2 Nay

Republicans voting Nay: Collins, McConnell, Murkowski.

Data: Voteview

---

## Post 6: Ending the 2025 shutdown
**Chart:** Key Votes → 119th → Senate → Funding & Appropriations → Nov. 10, 2025 vote

Senate passage of the funding bill that ended the fall 2025 shutdown, Nov. 10, 2025: 60 Yea, 40 Nay.

Democrats: 7 Yea, 38 Nay
Republicans: 52 Yea, 1 Nay
Independents: 1 Yea, 1 Nay

Members who voted against their party's majority: Cortez Masto, Durbin, Fetterman, Hassan, Kaine, Rosen, Shaheen (D) and Paul (R).

Data: Voteview

---

## Post 7: One Big Beautiful Bill Act
**Chart:** Key Votes → 119th → Major Legislation

Roll-call votes on the One Big Beautiful Bill Act (H.R. 1):

House passage, May 22, 2025: 215–214
Senate passage, July 1, 2025: 50–50
House vote to accept Senate changes, July 3, 2025: 218–214

No Democrat voted Yea on any of the three. Republicans voting Nay: 2 in the House (May), 3 in the Senate, 2 in the House (July).

Data: Voteview

---

## Post 8: GENIUS Act
**Chart:** Key Votes → 119th → House → Biggest Party Breaks → GENIUS Act

The stablecoin bill (GENIUS Act) is one of the 10 biggest party breaks of the 119th House on a final vote.

House passage, July 17, 2025: 308 Yea, 122 Nay
Democrats: 102 Yea, 110 Nay
Republicans: 206 Yea, 12 Nay

Senate passage, June 17, 2025: 68 Yea, 30 Nay

Data: Voteview

---

## Post 9: Cabinet confirmations across administrations
**Chart:** Key Votes → Cabinet Confirmations (switch the Congress filter: 111th, 115th, 117th, 119th)

Average share of opposing-party senators voting Yea on Cabinet confirmations (roll-call votes only):

2009 (111th, 5 votes): 50%
2017 (115th, 19 votes): 38%
2021 (117th, 15 votes): 49%
2025 (119th, 18 votes): 23%

In the 119th, 6 of 18 Cabinet confirmation votes got no Yea votes from the opposing party.

Cabinet nominees confirmed by voice vote have no roll call and are not counted.

Data: Voteview

---

## Post 10: How the numbers work (thread)
**Chart:** none, or a screenshot of the Methodology page

1/ How PartyCohesion measures party unity, in plain terms:

2/ A party-unity vote is a roll call where most Democrats voted one way and most Republicans voted the other. The 119th Congress has had 1,313 of them so far.

3/ A member's party unity % is the share of those votes on which they sided with their own party's majority. Only real Yea and Nay votes count. Absences don't.

4/ Each Congress is scored separately, so a member's rate can change from one Congress to the next. Member Explorer charts that change for anyone who served more than one term.

5/ Key votes are grouped by fixed rules (funding bills, Cabinet confirmations, the biggest party breaks), so the selection isn't anyone's opinion. Hand-picked votes are labeled as hand-picked.

6/ All data comes from Voteview's official roll-call records. Methodology: https://partycohesion.streamlit.app
Code: https://github.com/RendellRich/partycohesion

---

## Post 11: Same bill, different vote
**Card:** `docs/social/same-bill-different-vote-wide.png` (tall version for Instagram)
**Link:** https://rendellrich.github.io/partycohesion/same-bill-different-vote/

Most bills get more than one floor vote: passage, then the final version after the other chamber changes it.

Since 2007, members of Congress voted for a bill at one stage and against it at another 3,718 times while most of their own party voted the same way both times.

The count peaked in 2009 to 2010 (903) and has been under 200 per Congress since 2021.

Bills change between votes, so a different vote is not a contradiction. The new page shows both votes side by side with the bill title, so you can see what changed.

Data: Voteview

---

## Post 12: Respect for Marriage Act
**Card:** `docs/social/respect-for-marriage-act-wide.png`
**Link:** https://rendellrich.github.io/partycohesion/respect-for-marriage-act/

The Respect for Marriage Act had two House votes in 2022.

July (passage): 47 Republicans voted Yea.
December (final version, after the Senate added religious-liberty language): 39 Republicans voted Yea.

Seven Republicans voted Yea in July and Nay in December. Two voted Nay in July and Yea in December. Three others who voted Yea in July did not vote in December.

Every House Democrat who voted both times voted Yea both times.

Data: Voteview, House roll calls 373 and 513

---

## Post 13: Floor remarks and votes
**Card:** `docs/social/floor-remarks-wide.png`
**Link:** https://rendellrich.github.io/partycohesion/floor-remarks/

Do members vote the way they talk in floor debate?

I read the Congressional Record remarks of every member who took a clear position on Ukraine aid (2023 to 2024) or the Respect for Marriage Act (2022), then checked their vote on the final bill.

House: 101 of 101 voted the way they spoke.
Senate: 44 of 47.

The three senators who didn't (Merkley, Sanders, Welch) spoke in favor of Ukraine aid and voted against a final package that also carried aid for Israel and Taiwan.

Data: Congressional Record (GovInfo), Voteview

---

## Post 14: What I built (LinkedIn, portfolio framing)
**Card:** `docs/social/partycohesion-wide.png`
**Link:** https://rendellrich.github.io/partycohesion/

I built PartyCohesion, a free tool that answers one question with the official record: do members of Congress vote the same way no matter who is president?

What's under the hood:
- Every House and Senate roll call since 2007 from Voteview, refreshed automatically by a GitHub Actions pipeline
- Party unity rates per member per Congress, with data validation checks before each update
- A new view that matches a member's votes on the same bill at different stages, with bill titles from GovInfo
- Floor remarks from the Congressional Record, read and coded by hand, next to the votes

Python, pandas, Streamlit, GitHub Actions. Code and method are public.

https://partycohesion.streamlit.app

