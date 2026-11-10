# Posting to Facebook and Instagram

PartyCohesion can post its cards in two ways:

- **For the project:** the "Post to Facebook and Instagram" GitHub Action posts queued cards from `social/posts.yml` to the PartyCohesion Facebook Page and Instagram account. It checks the queue every hour from 6 a.m. to 11 p.m. Eastern and posts whatever is due, one post per run. You can also start it by hand to post one card now.
- **For anyone:** the share pages at https://rendellrich.github.io/partycohesion/cards/ let any visitor post a card from their own account.
  - Facebook, LinkedIn and X open each site's share window.
  - Instagram has no share link. On a phone, "Share image" opens the share sheet with the image, so Instagram is one tap away. On a computer, "Download for Instagram" saves the 4:5 image and "Copy caption" copies the text. The app's share bars link there under "Instagram".

The rest of this page covers one-time setup for posting as the project. It is free.

## What Meta requires

- **A Facebook Page.** Meta's API can't post to a personal profile, only to a Page you manage.
- **An Instagram professional account** (Creator or Business, both free) linked to that Page.
- **A Meta developer app** that you own. It can stay in Development mode, because you're only posting to your own Page and account. Development mode needs no App Review.

## One-time setup

1. **Create the Page.** Go to facebook.com/pages/create and name it PartyCohesion. A short description and the app link (https://partycohesion.streamlit.app) are enough.
2. **Set up Instagram.**
   - Create the account, or use an existing one, then switch it to Professional: in the Instagram app, Settings → Account type and tools → Switch to professional account.
   - Link it to the Page from Meta's Accounts Center, or from the Page's settings under Linked accounts → Instagram.
   - Put the app link in the Instagram bio. Posts end with "Link in bio."
3. **Create the developer app.**
   - Go to developers.facebook.com → My Apps → Create app.
   - Pick the use cases for managing a Page's posts and managing content on Instagram.
   - Leave the app in Development mode.
4. **Get a token.**
   - Open the Graph API Explorer (developers.facebook.com/tools/explorer), choose your app, and click "Generate access token".
   - Grant these permissions: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`, `instagram_basic`, `instagram_content_publish`, `business_management`.
   - Open the Access Token Debugger (developers.facebook.com/tools/debug/accesstoken), paste the token, and click "Extend access token". This gives a long-lived user token.
5. **Get the Page token and IDs.** In the Explorer, using the long-lived token, run these two requests:
   - `GET me/accounts`. It returns the Page's `id` and `access_token`. A Page token made from a long-lived user token doesn't expire.
   - `GET <page id>?fields=instagram_business_account`. It returns the Instagram account's `id`.
6. **Add the secrets to GitHub.** In the repo, go to Settings → Secrets and variables → Actions → New repository secret, and add:
   - `META_PAGE_TOKEN`: the Page access token (the only secret Facebook posting needs)
   - `META_PAGE_ID`: optional; the script looks up the Page from the token
   - `META_IG_USER_ID`: the Instagram account id
   - `META_IG_TOKEN`: optional. Add the long-lived user token here only if Instagram refuses the Page token.

   Never paste a token into an issue, a pull request or a chat. Secrets are only visible to the workflow.
7. **Test it.**
   - Go to Actions → "Post to Facebook and Instagram" → Run workflow. Pick a card and leave "Dry run" checked. The log shows exactly what would post.
   - Run it again with "Dry run" unchecked to post for real.

Until the secrets are added, each run skips each network with a message, so it never fails because of missing setup.

## Queuing posts

Add an entry to `social/posts.yml`:

```yaml
- id: same-bill-2026-12
  card: same-bill-different-vote
  post_on: 2026-12-01
  time: "18:40"                     # optional; Eastern, in quotes; 09:00 by default
  networks: [facebook, instagram]   # optional; both by default
  caption: |                        # optional; the card's own caption by default
    Your own words here.
    https://rendellrich.github.io/partycohesion/same-bill-different-vote/
```

- It posts on the first hourly run after `post_on` at `time`, once per network. If two posts are due at once, the second waits an hour.
- `social/posted.csv` records what went out, so an `id` never posts twice. Use a new `id` for each post.
- An entry more than 7 days late is skipped rather than posted stale. Change its date to send it.
- Anyone can propose a post with a pull request. It goes out only after it's merged, so you stay in control of what the project account says.
- Facebook gets the caption as written. On Instagram, a line that is only a link, or a label and a link, is dropped and "Link in bio." goes at the end, because Instagram captions can't link.
- Captions must be under 2,200 characters and use no em dashes. The tests check every queued caption.
- Keep the wording neutral: describe the votes, don't judge them.

## Member spotlights and the weekly schedule

Every Thursday the "Queue member spotlights" workflow runs `scripts/schedule_posts.py`, which tops the queue up to two weeks ahead and opens a pull request:

- A member spotlight every one or two days, each at a different time of day, in the fixed rotation from `scripts/member_spotlights.py` (shuffled with a published seed, parties alternating, every fourth a senator). Each member is featured once per Congress.
- One finding card a week, the one posted least recently, on a day without a spotlight.
- Days that already have a post are left alone, so entries you add by hand keep their place.

Spotlight cards and captions are rendered into `docs/social/members/` (`<Bioguide ID>-wide.png`, `-tall.jpg` and `.txt`). Before merging, look at each one: the votes listed should read fairly, and each "In their own words" link should be the member talking about that bill. To hold one back, delete its entry from `social/posts.yml` in the pull request. A spotlight that can't go out within a day of its slot is skipped rather than posted late.

To plan by hand: `python scripts/schedule_posts.py --dry-run` prints the plan; without `--dry-run` it renders the cards and adds the entries.

## Images

- Facebook gets the wide 1200×627 PNG.
- Instagram gets the 1080×1350 JPEG. Instagram only accepts JPEG, and 4:5 is its tallest feed size.
- Meta fetches both from GitHub Pages, so a card must be merged and live on Pages before it can post.
- `scripts/make_social_cards.py` makes both images and the captions in `docs/social/captions.json`. The weekly "Update social cards" workflow keeps them current.

## When Meta changes something

- **API version.** The scripts call Graph API `v26.0`. Meta supports each version for about two years. To move to a newer one, set the repository variable `META_GRAPH_VERSION` (for example `v27.0`) instead of editing code.
- **Token.** If a token stops working (you changed your Facebook password, removed the app, or lost Page access), repeat steps 4 to 6 and update the secrets.
