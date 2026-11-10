"""Post PartyCohesion cards to a Facebook Page and an Instagram professional account through Meta's Graph API.

Two ways to use it, both run by .github/workflows/post-social.yml:

  python scripts/post_social.py --due
      Posts the next entry in social/posts.yml whose post_on date and time (Eastern) have come and that hasn't gone
      out yet, then records it in social/posted.csv so it never posts twice. One entry per run, so a backlog goes
      out an hour apart instead of all at once. Anyone can propose a post by adding an entry in a pull request; it
      goes out after the PR is merged.

  python scripts/post_social.py --card senate-unity --networks facebook,instagram [--caption "..."]
      Posts one card now. Without --caption it uses the card's caption from docs/social/captions.json.

Add --dry-run to either to print what would be posted without calling Meta.

Settings come from environment variables (GitHub repository secrets in the workflow):
  META_PAGE_ID        optional, the Facebook Page's ID (looked up from the Page token when not set)
  META_PAGE_TOKEN     a Page access token with pages_manage_posts (and instagram_content_publish for Instagram)
  META_IG_USER_ID     the Instagram professional account's ID (linked to that Page)
  META_IG_TOKEN       optional, a separate token for Instagram if the Page token is refused there
  META_GRAPH_VERSION  optional, defaults to GRAPH_VERSION below
A network whose settings are missing is skipped with a message, so the workflow can run before both are set up.

Images come from the GitHub Pages site, because Meta fetches them by URL: the wide PNG for Facebook and the
4:5 JPEG for Instagram (Instagram only accepts JPEG). A card named member/<Bioguide ID> is a member spotlight from
scripts/member_spotlights.py, with its image and caption in docs/social/members/.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, time as clock, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "social" / "posts.yml"
POSTED = ROOT / "social" / "posted.csv"
CAPTIONS = ROOT / "docs" / "social" / "captions.json"
MEMBERS = ROOT / "docs" / "social" / "members"
PAGES_URL = "https://rendellrich.github.io/partycohesion"
GRAPH_VERSION = "v26.0"
NETWORKS = ("facebook", "instagram")
EXPIRE_DAYS = 7  # a queued post more than this many days late is skipped instead of going out stale
EASTERN = ZoneInfo("America/New_York")
DEFAULT_TIME = "09:00"  # Eastern, for entries without a time
POSTED_FIELDS = ["id", "network", "posted_at", "post_id"]


class MetaError(RuntimeError):
    pass


# ---------------------------------------------------------------- captions and images

def image_url(card: str, network: str) -> str:
    ext = "wide.png" if network == "facebook" else "tall.jpg"
    if card.startswith("member/"):
        return f"{PAGES_URL}/social/members/{card.split('/', 1)[1]}-{ext}"
    return f"{PAGES_URL}/social/{card}-{ext}"


URL = re.compile(r"https?://\S+")


def instagram_caption(caption: str) -> str:
    """Instagram captions can't hold links. A line that is only a link, or a label and a link ("Floor remarks:
    https://..."), is dropped, and "Link in bio." goes at the end."""
    lines = caption.rstrip().split("\n")
    kept = [ln for ln in lines if not re.fullmatch(r"[^\n]{0,40}:?\s*https?://\S+\s*", ln)]
    kept = [URL.sub("(link in bio)", ln) for ln in kept]
    if kept != lines:
        kept.append("Link in bio.")
    return "\n".join(kept)


def check_caption(caption: str) -> None:
    if "\u2014" in caption:
        raise ValueError("Caption has an em dash; use a comma, period or separate sentence.")
    if len(caption) > 2200:
        raise ValueError(f"Caption is {len(caption)} characters; Instagram allows 2,200.")


def default_caption(card: str) -> str:
    if card.startswith("member/"):
        path = MEMBERS / f"{card.split('/', 1)[1]}.txt"
        if not path.exists():
            raise ValueError(f"No spotlight caption at {path.relative_to(ROOT)}; run scripts/member_spotlights.py.")
        return path.read_text().strip()
    caps = json.loads(CAPTIONS.read_text())
    if card not in caps:
        raise ValueError(f"Unknown card '{card}'. Cards: {', '.join(caps)}")
    return caps[card]


# ---------------------------------------------------------------- Graph API

def graph_post(path: str, params: dict, opener=urllib.request.urlopen) -> dict:
    version = os.environ.get("META_GRAPH_VERSION") or GRAPH_VERSION
    url = f"https://graph.facebook.com/{version}/{path}"
    data = urllib.parse.urlencode(params).encode()
    try:
        with opener(urllib.request.Request(url, data=data, method="POST"), timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode()).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        raise MetaError(f"Meta returned {e.code} for {path.split('?')[0]}: {msg or e.reason}") from None


def graph_get(path: str, params: dict, opener=urllib.request.urlopen) -> dict:
    version = os.environ.get("META_GRAPH_VERSION") or GRAPH_VERSION
    url = f"https://graph.facebook.com/{version}/{path}?{urllib.parse.urlencode(params)}"
    with opener(urllib.request.Request(url), timeout=60) as r:
        return json.loads(r.read().decode())


def whoami(token: str, opener=urllib.request.urlopen) -> dict:
    """id, name and type ('page' or 'user') of whoever the token belongs to."""
    me = graph_get("me", {"fields": "id,name", "access_token": token}, opener)
    info = graph_get("debug_token", {"input_token": token, "access_token": token}, opener).get("data", {})
    return {"id": me.get("id"), "name": me.get("name"), "type": str(info.get("type", "")).lower(),
            "expires_at": info.get("expires_at")}


def page_id(token: str, opener=urllib.request.urlopen) -> str:
    """META_PAGE_ID if set; otherwise the Page the token belongs to (a Page token's /me is the Page)."""
    if os.environ.get("META_PAGE_ID"):
        return os.environ["META_PAGE_ID"]
    me = whoami(token, opener)
    if me.get("type") != "page":  # a personal token would post as the person
        raise MetaError(f"META_PAGE_TOKEN belongs to the person \"{me.get('name')}\", not a Page. Use the "
                        "Page's access_token from me/accounts (see SOCIAL_POSTING.md).")
    return me["id"]


def post_facebook(card: str, caption: str, opener=urllib.request.urlopen) -> str:
    token = os.environ["META_PAGE_TOKEN"]
    page = page_id(token, opener)
    out = graph_post(f"{page}/photos", {"url": image_url(card, "facebook"), "message": caption,
                                        "access_token": token}, opener)
    return out.get("post_id") or out["id"]


def post_instagram(card: str, caption: str, opener=urllib.request.urlopen, wait=time.sleep) -> str:
    ig, token = os.environ["META_IG_USER_ID"], os.environ.get("META_IG_TOKEN") or os.environ["META_PAGE_TOKEN"]
    container = graph_post(f"{ig}/media", {"image_url": image_url(card, "instagram"),
                                           "caption": instagram_caption(caption), "access_token": token}, opener)["id"]
    for _ in range(10):  # images are usually ready at once; wait up to about 30 seconds
        status = graph_get(container, {"fields": "status_code", "access_token": token}, opener).get("status_code")
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            raise MetaError(f"Instagram could not process the image ({status}).")
        wait(3)
    return graph_post(f"{ig}/media_publish", {"creation_id": container, "access_token": token}, opener)["id"]


def configured(network: str) -> bool:
    need = ["META_PAGE_TOKEN"] if network == "facebook" else ["META_IG_USER_ID", "META_PAGE_TOKEN"]
    return all(os.environ.get(k) for k in need)


POSTERS = {"facebook": post_facebook, "instagram": post_instagram}


# ---------------------------------------------------------------- queue

def load_queue(path: Path = QUEUE) -> list[dict]:
    entries = (yaml.safe_load(path.read_text()) or []) if path.exists() else []
    ids = [e.get("id") for e in entries]
    for e in entries:
        missing = [k for k in ("id", "card", "post_on") if not e.get(k)]
        if missing:
            raise ValueError(f"Queue entry {e} is missing {', '.join(missing)}.")
        if e.get("time") is not None and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(e["time"])):
            raise ValueError(f"Queue entry {e['id']} has time {e['time']!r}; use 24-hour Eastern time like \"19:30\".")
        bad = set(e.get("networks", NETWORKS)) - set(NETWORKS)
        if bad:
            raise ValueError(f"Queue entry {e['id']} has unknown networks: {', '.join(sorted(bad))}.")
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"Queue ids must be unique: {', '.join(sorted(dupes))}.")
    return entries


def load_posted(path: Path = POSTED) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    with path.open() as fh:
        return {(r["id"], r["network"]) for r in csv.DictReader(fh)}


def record(entry_id: str, network: str, post_id: str, path: Path = POSTED) -> None:
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=POSTED_FIELDS)
        if new:
            w.writeheader()
        w.writerow({"id": entry_id, "network": network, "post_id": post_id,
                    "posted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})


def scheduled(entry: dict) -> datetime:
    """When an entry goes out: its post_on date at its time (Eastern), or DEFAULT_TIME when it has none."""
    day = entry["post_on"] if isinstance(entry["post_on"], date) else date.fromisoformat(str(entry["post_on"]))
    hh, mm = (int(x) for x in str(entry.get("time") or DEFAULT_TIME).split(":"))
    return datetime.combine(day, clock(hh, mm), EASTERN)


def as_now(when: date | datetime | None) -> datetime:
    """A datetime in Eastern time. A bare date means the end of that day, so everything due that day counts."""
    if when is None:
        return datetime.now(EASTERN)
    if isinstance(when, datetime):
        return when.astimezone(EASTERN) if when.tzinfo else when.replace(tzinfo=EASTERN)
    return datetime.combine(when, clock(23, 59), EASTERN)


def due(entries: list[dict], posted: set, now: date | datetime) -> list[tuple[dict, str, str]]:
    """(entry, network, status) for each queued network, soonest first: 'post', 'expired' or 'later'. Already posted
    ones are left out. An entry expires after its expires_after_days (EXPIRE_DAYS by default)."""
    now = as_now(now)
    out = []
    for e in sorted(entries, key=scheduled):
        when = scheduled(e)
        limit = timedelta(days=float(e.get("expires_after_days", EXPIRE_DAYS)))
        for net in e.get("networks", NETWORKS):
            if (e["id"], net) in posted:
                continue
            out.append((e, net, "later" if now < when else "expired" if now - when > limit else "post"))
    return out


# ---------------------------------------------------------------- main

def publish(card: str, network: str, caption: str, dry_run: bool) -> str | None:
    check_caption(caption)
    if dry_run:
        text = caption if network == "facebook" else instagram_caption(caption)
        print(f"[dry run] {network}: {image_url(card, network)}\n{text}\n")
        return None
    if not configured(network):
        print(f"Skipping {network}: its settings aren't in the repository secrets yet (see SOCIAL_POSTING.md).")
        return None
    post_id = POSTERS[network](card, caption)
    print(f"Posted {card} to {network}: {post_id}")
    return post_id


def run_due(dry_run: bool, today: date | datetime | None = None) -> int:
    """Posts the soonest due entry (to each of its networks) and stops, so two entries never go out in one run."""
    failures, sent, skipped = 0, None, set()
    for entry, net, status in due(load_queue(QUEUE), load_posted(POSTED), as_now(today)):
        if status == "later" or (sent and entry["id"] != sent):
            continue
        if not dry_run and not configured(net):  # never let a network that isn't set up hold up the queue
            if net not in skipped:
                print(f"Skipping {net}: its settings aren't in the repository secrets yet (see SOCIAL_POSTING.md).")
                skipped.add(net)
            continue
        if status == "expired":
            print(f"Skipping {entry['id']} on {net}: it was due {scheduled(entry):%Y-%m-%d %H:%M} Eastern and is "
                  "too late now. Change its post_on date to send it.")
            continue
        sent = entry["id"]
        try:
            caption = entry.get("caption") or default_caption(entry["card"])
            post_id = publish(entry["card"], net, caption.strip(), dry_run)
        except (MetaError, ValueError) as e:
            print(f"Could not post {entry['id']} to {net}: {e}", file=sys.stderr)
            failures += 1
            continue
        if post_id:
            record(entry["id"], net, post_id, POSTED)
    return failures


def check_setup(opener=urllib.request.urlopen) -> int:
    """Confirm the token works and say which Page it posts to. Posts nothing and never prints the token."""
    token = os.environ.get("META_PAGE_TOKEN")
    if not token:
        print("META_PAGE_TOKEN is not set.")
        return 1
    try:
        me = whoami(token, opener)
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode()).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        print(f"Meta refused the token ({e.code}): {msg or e.reason}")
        return 1
    if me.get("type") != "page":
        print(f"Facebook: this is a {me.get('type') or 'non-Page'} token for \"{me.get('name')}\", not a Page token. Nothing would post. "
              "Replace META_PAGE_TOKEN with the PartyCohesion access_token from me/accounts.")
        return 1
    print(f"Facebook: the token posts as the Page \"{me.get('name')}\" (Page id {me.get('id')}).")
    try:
        exp = me.get("expires_at")
        if exp == 0:
            print("Facebook: the token never expires.")
        elif exp:
            when = datetime.fromtimestamp(exp, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            print(f"Facebook: the token expires {when}. Make it long-lived (see SOCIAL_POSTING.md) or posts will stop.")
    except Exception:
        print("Facebook: couldn't read the token's expiry.")
    print("Instagram: " + ("set up." if configured("instagram") else "not set up (skipped)."))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--due", action="store_true", help="post queued entries that are due")
    ap.add_argument("--card", help="post this card now")
    ap.add_argument("--networks", default="facebook,instagram")
    ap.add_argument("--caption", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true", help="check the secrets reach the Page, without posting")
    a = ap.parse_args(argv)
    if a.check:
        return check_setup()
    if a.due:
        return 1 if run_due(a.dry_run) else 0
    if not a.card:
        ap.error("give --due or --card")
    caption = (a.caption or default_caption(a.card)).replace("\\n", "\n").strip()
    failures = 0
    for net in [n.strip() for n in a.networks.split(",") if n.strip()]:
        if net not in NETWORKS:
            ap.error(f"unknown network {net}")
        try:
            publish(a.card, net, caption, a.dry_run)
        except (MetaError, ValueError) as e:
            print(f"Could not post to {net}: {e}", file=sys.stderr)
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
