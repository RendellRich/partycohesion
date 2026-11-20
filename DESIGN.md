---
name: PartyCohesion
description: Neutral, primary-source congressional voting data for voters on any screen.
colors:
  dark-bg: "#171614"
  dark-surface: "#21201D"
  dark-border: "#3A3733"
  dark-text: "#FAFAFA"
  dark-body: "#E7E5E4"
  dark-muted: "#A8A29E"
  dark-accent: "#E9C46A"
  dark-dem: "#5A97D2"
  dark-rep: "#E06C6C"
  dark-head: "#C9D3EE"
  light-bg: "#F6F7F9"
  light-surface: "#FFFFFF"
  light-border: "#DADDE3"
  light-text: "#1B1D21"
  light-body: "#2A2E35"
  light-muted: "#555B65"
  light-accent: "#7A5A10"
  light-dem: "#2E6CAD"
  light-rep: "#B8403F"
  light-head: "#1C2A4A"
  light-control: "#868C96"
  dark-control: "#7A746C"
  record-navy: "#1C2A4A"
  record-paper: "#F6F1E7"
  tone-amber: "#94590A"
  tone-teal: "#23746A"
  tone-violet: "#5E45A8"
typography:
  display:
    fontFamily: "'Source Serif 4', Georgia, serif"
    fontSize: "2.6rem"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "'Source Serif 4', Georgia, serif"
    fontWeight: 700
    letterSpacing: "-0.01em"
  title:
    fontFamily: "'Public Sans', 'Segoe UI', system-ui, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 700
  subtitle:
    fontFamily: "'Public Sans', 'Segoe UI', system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
  body:
    fontFamily: "'Public Sans', 'Segoe UI', system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  stat:
    fontFamily: "'Public Sans', 'Segoe UI', system-ui, sans-serif"
    fontSize: "2.4rem"
    fontWeight: 700
    lineHeight: 1.2
    fontFeature: "tnum"
  label:
    fontFamily: "'Public Sans', 'Segoe UI', system-ui, sans-serif"
    fontSize: "0.85rem"
    fontWeight: 600
  label-large:
    fontFamily: "'Public Sans', 'Segoe UI', system-ui, sans-serif"
    fontSize: "0.9rem"
    fontWeight: 600
  stat-metric:
    fontFamily: "'Public Sans', 'Segoe UI', system-ui, sans-serif"
    fontSize: "2rem"
    fontWeight: 700
    fontFeature: "tnum"
  stat-long:
    fontFamily: "'Public Sans', 'Segoe UI', system-ui, sans-serif"
    fontSize: "1.35rem"
    fontWeight: 700
rounded:
  chip: "6px"
  card: "10px"
  panel: "16px"
  pill: "999px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "20px"
components:
  card:
    backgroundColor: "{colors.light-surface}"
    rounded: "{rounded.card}"
    padding: "20px"
  metric:
    backgroundColor: "{colors.light-surface}"
    rounded: "{rounded.card}"
    padding: "14px 16px"
  hero-panel:
    backgroundColor: "{colors.record-navy}"
    textColor: "{colors.record-paper}"
    rounded: "{rounded.panel}"
    padding: "34px 36px 0 36px"
  share-pill:
    textColor: "{colors.light-text}"
    rounded: "{rounded.pill}"
    padding: "4px 12px"
  badge:
    rounded: "{rounded.chip}"
    padding: "2px 10px"
---

# Design System: PartyCohesion

## Overview

**Creative North Star: "The Public Record"**

PartyCohesion should feel like a well-kept public document that happens to be friendly: serif titles that read like the record itself, plain Public Sans for everything a visitor scans, and numbers set in tabular figures so columns line up. The data is the hero. Color appears where it carries information (party, vote, pattern) and as a few warm card tones that make long pages easy to move through.

Density is moderate. Pages lead with one plain question or title, a short explanation, then metric cards, a chart, and a table. Light and dark themes are equals; every color is a token with a partner in the other theme, and charts swap tokens automatically. Two signature marks carry the identity: a thin blue and red stripe across the top of every page (with a gap, the aisle) and a short two-color rule under each page title.

The system must never look like cable news or a campaign ad, and it must never favor one party visually.

**Key Characteristics:**
- Serif titles, sans body, tabular numbers.
- Friendly and warm surfaces: lightly tinted cards with a colored top edge, rounded corners, no shadows.
- Party color only identifies a party, always next to a label.
- Equal weight for both parties in every chart, stripe and legend.
- Light and dark themes are first-class and token-driven.

## Colors

A quiet neutral base with two equal party colors, one gold accent for links and focus, and three warm card tones.

### Primary
- **Record Gold** (light {colors.light-accent}, dark {colors.dark-accent}): links, page links, focus rings, the eyebrow on plain cards. The only interactive color.

### Secondary
- **Record Navy** ({colors.record-navy}) with **Record Paper** ({colors.record-paper}) text: the Home hero panel and the heading color in light mode.

### Tertiary
- **Card tones** (amber {colors.tone-amber}, teal {colors.tone-teal}, violet {colors.tone-violet} in light; brighter partners in dark): the top edge and a 7 percent tint on cards, and the left edge on metric cards, rotating amber, teal, violet. Violet also marks "What this means" explainers.

### Neutral
- **Background** (light {colors.light-bg}, dark {colors.dark-bg}), **Surface** (light {colors.light-surface}, dark {colors.dark-surface}), **Border** (light {colors.light-border}, dark {colors.dark-border}).
- **Text** for titles and values, **Body** for paragraphs, **Muted** for labels, notes, captions and table headers.
- **Control outline** (light {colors.light-control}, dark {colors.dark-control}): the 3:1 outline on things people tap or type in: fields, share pills, toggle tracks. Decorative card and table borders stay on the softer border color.

### Data colors
- **Party**: Democrat (light {colors.light-dem}, dark {colors.dark-dem}), Republican (light {colors.light-rep}, dark {colors.dark-rep}), Independent uses the muted gray.
- **Vote and pattern colors** live in `theme.py` (Yea, Nay, Consistent, Partly changed, Changed, Opposite) and pass the dataviz palette checks against their own background.

### Named Rules
**The Equal Aisle Rule.** Democratic and Republican colors get the same size, weight and prominence everywhere: the top stripe splits at 50 percent, legends list both, and neither color is ever brighter or larger to signal favor.

**The Label Beside Color Rule.** A party or vote color never stands alone. It always sits next to the party name, a letter (D, R, I) or a text value.

## Typography

**Display Font:** Source Serif 4 (with Georgia, serif)
**Body Font:** Public Sans (with Segoe UI, system-ui, sans-serif)

**Character:** The serif gives page titles and the big Home question the weight of a public document; Public Sans, the U.S. Web Design System's typeface, keeps data plain and readable.

### Hierarchy
- **Display** (700, 2.6rem, 1.75rem under 640px, 1.15): the Home hero question only, max 22ch.
- **Headline** (700, Streamlit h1 size): page titles, followed by the two-color rule.
- **Title** (700, 1.75rem, heading color): h2 section headings, the level right under each page title.
- **Subtitle** (700, 1.5rem): h3 headings inside a section.
- **Body** (400, 1rem, 1.5 to 1.6): paragraphs and intros, max 72ch.
- **Stat** (700, 2.4rem on cards, 2rem on metrics, tabular figures): headline numbers.
- **Label** (600, 0.85rem to 0.9rem): metric labels, table headers, eyebrows, tags and badges.

## Layout

Single centered column in Streamlit's wide layout, with a sidebar for navigation that collapses on phones. Metric cards use an auto-fit grid (minimum 190px per card, 12px gaps), two to a row below 640px with an odd last card across both. Cards and tables stack full width. Below 640px the hero panel padding drops from 36px to 20px, the hero question drops to 1.75rem, and the member photo beside the name line shrinks from 72px to 56px. On phones, a member page's seat map and ideology chart open from a tap, and long tables show their first rows. Every page must work at 320px wide.

## Elevation & Depth

Flat. Depth comes from tonal layering only: the surface color on the background, a 1px border, and the colored top edge on Home's cards. No shadows anywhere.

**The Flat Record Rule.** If something needs to stand out, give it a border, tone or position, never a shadow.

## Shapes

Gently rounded on one scale (6, 10, 16px and fully round): 6px on badges, photos and chart bars, 10px on cards, metrics, explainers and tables (and the hero panel on phones), 16px on the hero panel, fully round pills for share buttons and chips. No colored side stripes on cards, explainers or notices.

## Components

### Cards
- **Character:** friendly and warm.
- **Corner Style:** 10px.
- **Background:** surface tinted 7 percent with the card's tone.
- **Border:** 1px border plus a 4px top edge in the tone.
- **Internal Padding:** 20px.

### Metric cards
- 10px corners, surface background, 1px border. Label (muted 0.85rem), value (2rem tabular, 1.35rem when longer than 11 characters; on phones 1.5rem, and 1rem for words or long values), note (muted 0.85rem).

### Hero panel (Home)
- Record Navy background, Record Paper text, 16px corners, serif question, intro at 82 percent paper, and a full-width blue and red aisle bar along the bottom edge.

### Tables
- Surface background, 1px border, 10px corners, muted 0.85rem headers, 12px by 16px cells, a top border on each row.

### Tags and badges
- **Party tag:** colored dot plus the party name in 600 weight.
- **Pattern badge:** filled 6px-corner badge with text color chosen for contrast on the fill.

### Share pills and chips
- Round pills with a 1px border, 600 weight 0.9rem text; border turns gold on hover.

### Navigation
- Streamlit sidebar navigation grouped by section, tinted 7 percent toward Record Navy. Page links inside content are gold and 600 weight, underlined on hover.

### Focus
- Every link and button shows a 2px Record Gold outline with a 2px offset on keyboard focus.

## Do's and Don'ts

### Do:
- **Do** take every color from the theme tokens so light and dark stay in step.
- **Do** keep party colors equal in size and weight, and always label them.
- **Do** use tabular figures for every number that can sit in a column.
- **Do** keep tap targets at least 44px and form fields at least 16px on screens under 768px.
- **Do** check each page at 320px, 375px and desktop widths in both themes.

### Don't:
- **Don't** use a cable news look: no breaking-news tickers, alarm red, flashing or dramatic graphics.
- **Don't** let one party's color appear brighter, larger or more prominent than the other's.
- **Don't** add shadows; depth is tonal.
- **Don't** use color as the only way to show meaning.
