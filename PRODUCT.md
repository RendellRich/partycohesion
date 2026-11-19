# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: everyday voters checking how their own members of Congress vote. Many arrive on a phone from a Facebook post (the PartyCohesion Page, #StopTheDivide), often looking up one state or one member.

Secondary: recruiters and data people reviewing the project as a data science portfolio piece, usually on a desktop, often arriving from LinkedIn or GitHub.

## Product Purpose

Put the official congressional roll-call record in front of the public with as little editorial framing as possible, so a visitor can see whether a member's votes follow their party, change when the White House changes hands, and line up with what they said on the campaign trail and on the floor. Success is a visitor finding their own members and understanding their record without needing to trust anyone's opinion.

## Positioning

Neutral, primary-source roll-call data. No scorecards and no opinions. The same votes, cutoffs and rules apply to every member of both parties, and the method behind every number is always visible and inspectable.

## Operating Context

- Streamlit multipage app (Plotly charts) at partycohesion.streamlit.app; repo RendellRich/partycohesion.
- Data refreshes twice a week by GitHub Action, validated against official Yea and Nay totals before commit.
- Visitors land on Home (hero question, clickable state map, chamber at a glance), States, Members, and finding pages linked from social posts. Every state and member page has its own shareable link.
- Light and dark themes follow the visitor's device and switch from Settings.

## Capabilities and Constraints

- Covers House and Senate roll calls since the 110th Congress (2007): party unity, Position Flips, ideology (DW-NOMINATE), missed votes, platform votes, cosponsored-then-voted-no, same state different vote, campaign and floor statements, key votes, lobbying.
- Free sources and free hosting only; no paid APIs or services.
- Terminology on the site: "party unity", "Position Flips", "missed votes", "roll call", "party-line vote", "delegation".
- Stance labels for campaign and floor statements were made with an AI assistant and are disclosed as such; every floor quote links to the full remarks.

## Brand Commitments

- Name: PartyCohesion. Social campaign: Stop the Divide.
- Voice: plain, descriptive, neutral. Captions describe; they do not judge. No em dashes.
- Party colors identify parties only; they are never used to rank or praise.

## Evidence on Hand

- Real data in `data/` (Voteview, GovInfo, CampaignView, Statements of Administration Policy, American Presidency Project, congress-legislators).
- Screenshots in `docs/images/`.
- No testimonials, user counts, press or endorsements exist; never invent them.

## Product Principles

1. Primary sources first: official roll calls before interpretation.
2. Minimal spin: numbers and charts before commentary.
3. Transparency: every definition, cutoff and source is public, and every score traces to its votes.
4. Same rules for everyone: no party gets a different method or framing.
5. Phone first for voters: a visitor from a social post must find their state or member in a tap or two.

## Accessibility & Inclusion

WCAG 2.2 AA, plus these project rules:
- Body text contrast 4.5:1; large text, outlines and meaningful graphics 3:1, in light and dark themes.
- Tap targets at least 44px.
- Works at 320px wide.
- Visible focus rings on every interactive element.
- No meaning carried by color alone (party and vote colors always come with a label or letter).
- Form fields at least 16px below 768px wide so iPhones do not zoom on tap.
