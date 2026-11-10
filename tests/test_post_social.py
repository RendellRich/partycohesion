"""Tests for scripts/post_social.py. No request ever reaches Meta: a fake opener records each call."""
import importlib.util
import io
import json
import urllib.parse
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("post_social", ROOT / "scripts" / "post_social.py")
ps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ps)


class FakeMeta:
    """Stands in for urllib.request.urlopen and answers like the Graph API."""

    def __init__(self, statuses=("FINISHED",)):
        self.calls, self.statuses = [], list(statuses)

    def __call__(self, req, timeout=None):
        url = req.full_url
        body = dict(urllib.parse.parse_qsl(req.data.decode())) if req.data else {}
        self.calls.append((req.get_method(), url.split("?")[0], body))
        if url.split("?")[0].endswith("/photos"):
            out = {"id": "photo1", "post_id": "page_post1"}
        elif url.split("?")[0].endswith("/media"):
            out = {"id": "container1"}
        elif url.split("?")[0].endswith("/media_publish"):
            out = {"id": "igmedia1"}
        else:
            out = {"status_code": self.statuses.pop(0) if self.statuses else "FINISHED"}
        return io.BytesIO(json.dumps(out).encode())


@pytest.fixture
def meta_env(monkeypatch):
    monkeypatch.setenv("META_PAGE_ID", "111")
    monkeypatch.setenv("META_PAGE_TOKEN", "tok")
    monkeypatch.setenv("META_IG_USER_ID", "222")
    monkeypatch.delenv("META_GRAPH_VERSION", raising=False)


def test_facebook_posts_wide_image_with_caption(meta_env):
    fake = FakeMeta()
    assert ps.post_facebook("senate-unity", "Hello\nhttps://x.test/", opener=fake) == "page_post1"
    method, url, body = fake.calls[0]
    assert (method, url) == ("POST", f"https://graph.facebook.com/{ps.GRAPH_VERSION}/111/photos")
    assert body["url"].endswith("/social/senate-unity-wide.png")
    assert body["message"] == "Hello\nhttps://x.test/"


def test_facebook_looks_up_page_id_from_token(meta_env, monkeypatch):
    monkeypatch.delenv("META_PAGE_ID")

    class WithMe(FakeMeta):
        def __call__(self, req, timeout=None):
            if req.full_url.split("?")[0].endswith(("/me", "/debug_token")):
                self.calls.append(("GET", req.full_url.split("?")[0], {}))
                return io.BytesIO(json.dumps({"id": "999", "name": "PartyCohesion",
                                              "data": {"type": "PAGE", "expires_at": 0}}).encode())
            return super().__call__(req, timeout)

    fake = WithMe()
    assert ps.configured("facebook")
    ps.post_facebook("senate-unity", "Hi", opener=fake)
    assert fake.calls[-1][1].endswith("/999/photos")


def test_instagram_creates_container_waits_then_publishes(meta_env):
    fake = FakeMeta(statuses=("IN_PROGRESS", "FINISHED"))
    waits = []
    assert ps.post_instagram("floor-remarks", "Text\nhttps://x.test/", opener=fake, wait=waits.append) == "igmedia1"
    paths = [c[1].rsplit("/", 1)[-1] for c in fake.calls]
    assert paths == ["media", "container1", "container1", "media_publish"]
    assert fake.calls[0][2]["image_url"].endswith("/social/floor-remarks-tall.jpg")
    assert fake.calls[0][2]["caption"] == "Text\nLink in bio."
    assert fake.calls[-1][2]["creation_id"] == "container1"
    assert waits == [3]


def test_instagram_stops_on_error_status(meta_env):
    with pytest.raises(ps.MetaError):
        ps.post_instagram("floor-remarks", "Text", opener=FakeMeta(statuses=("ERROR",)), wait=lambda s: None)


def test_instagram_caption_swaps_links_for_link_in_bio():
    assert ps.instagram_caption("A\n\nData: Voteview\nhttps://a.test/b/") == "A\n\nData: Voteview\nLink in bio."
    assert ps.instagram_caption("No link here") == "No link here"


def test_caption_rules():
    with pytest.raises(ValueError):
        ps.check_caption("Votes — changed")
    with pytest.raises(ValueError):
        ps.check_caption("x" * 2201)
    ps.check_caption("Fine, plain text.")


def test_due_logic():
    entries = [{"id": "a", "card": "partycohesion", "post_on": date(2026, 11, 12)},
               {"id": "b", "card": "senate-unity", "post_on": "2026-11-20", "networks": ["facebook"]},
               {"id": "c", "card": "senate-unity", "post_on": "2026-11-01"}]
    posted = {("a", "facebook")}
    got = {(e["id"], n): s for e, n, s in ps.due(entries, posted, date(2026, 11, 12))}
    assert got == {("a", "instagram"): "post", ("b", "facebook"): "later",
                   ("c", "facebook"): "expired", ("c", "instagram"): "expired"}


def test_run_due_skips_unconfigured_networks_and_records_posts(tmp_path, monkeypatch, meta_env):
    queue, posted = tmp_path / "posts.yml", tmp_path / "posted.csv"
    queue.write_text("- id: launch\n  card: partycohesion\n  post_on: 2026-11-12\n")
    monkeypatch.setattr(ps, "QUEUE", queue)
    monkeypatch.setattr(ps, "POSTED", posted)
    monkeypatch.delenv("META_IG_USER_ID")
    calls = []
    monkeypatch.setitem(ps.POSTERS, "facebook", lambda card, cap: calls.append((card, cap)) or "fb1")
    assert ps.run_due(dry_run=False, today=date(2026, 11, 12)) == 0
    assert calls and calls[0][0] == "partycohesion"
    assert calls[0][1].endswith("https://rendellrich.github.io/partycohesion/")
    assert ps.load_posted(posted) == {("launch", "facebook")}
    assert ps.run_due(dry_run=False, today=date(2026, 11, 12)) == 0 and len(calls) == 1  # never twice


def test_record_and_load_posted_round_trip(tmp_path):
    path = tmp_path / "posted.csv"
    ps.record("launch", "facebook", "fb1", path)
    ps.record("launch", "instagram", "ig1", path)
    assert ps.load_posted(path) == {("launch", "facebook"), ("launch", "instagram")}


def test_queue_file_is_valid_and_uses_real_cards():
    entries = ps.load_queue()
    caps = json.loads(ps.CAPTIONS.read_text())
    for e in entries:
        if e["card"].startswith("member/"):  # a spotlight: its card and caption must be committed
            b = e["card"].split("/", 1)[1]
            for name in (f"{b}-wide.png", f"{b}-tall.jpg", f"{b}.txt", f"{b}.alt.txt"):
                assert (ps.MEMBERS / name).exists(), name
        else:
            assert e["card"] in caps
        ps.check_caption(e.get("caption") or ps.default_caption(e["card"]))
        ps.scheduled(e)  # date and time parse


def test_queue_rejects_duplicates_and_unknown_networks(tmp_path):
    p = tmp_path / "q.yml"
    p.write_text("- {id: a, card: partycohesion, post_on: 2026-11-12}\n- {id: a, card: partycohesion, post_on: 2026-11-13}\n")
    with pytest.raises(ValueError):
        ps.load_queue(p)
    p.write_text("- {id: a, card: partycohesion, post_on: 2026-11-12, networks: [tiktok]}\n")
    with pytest.raises(ValueError):
        ps.load_queue(p)


def test_every_card_has_its_images_and_caption():
    caps = json.loads(ps.CAPTIONS.read_text())
    for card in caps:
        for name in (f"{card}-wide.png", f"{card}-tall.jpg"):
            assert (ROOT / "docs" / "social" / name).exists(), name
        assert caps[card].rstrip().split("\n")[-1].startswith(ps.PAGES_URL)
        ps.check_caption(caps[card])


def test_dry_run_calls_nothing(capsys, monkeypatch):
    monkeypatch.setitem(ps.POSTERS, "facebook", lambda *a: pytest.fail("posted during a dry run"))
    assert ps.main(["--card", "senate-unity", "--networks", "facebook,instagram", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "senate-unity-wide.png" in out and "senate-unity-tall.jpg" in out and "Link in bio." in out


def test_check_setup_reports_page_without_posting(meta_env, capsys, monkeypatch):
    monkeypatch.setenv("META_PAGE_TOKEN", "SECRETVALUE123")
    calls = []

    def fake(req, timeout=None):
        calls.append((req.get_method(), req.full_url.split("?")[0]))
        return io.BytesIO(json.dumps({"id": "999", "name": "PartyCohesion",
                                      "data": {"type": "PAGE", "expires_at": 0}}).encode())

    assert ps.check_setup(opener=fake) == 0
    assert {c[0] for c in calls} == {"GET"}  # reads only, never a POST
    assert [c[1].rsplit("/", 1)[-1] for c in calls] == ["me", "debug_token"]
    out = capsys.readouterr().out
    assert "never expires" in out and "PartyCohesion" in out and "SECRETVALUE123" not in out



def test_personal_token_is_refused(meta_env, monkeypatch, capsys):
    monkeypatch.delenv("META_PAGE_ID")
    person = lambda req, timeout=None: io.BytesIO(json.dumps({"id": "1", "name": "Some Person", "data": {"type": "USER", "expires_at": 0}}).encode())
    with pytest.raises(ps.MetaError):
        ps.page_id("tok", opener=person)
    assert ps.check_setup(opener=person) == 1
    assert "not a Page token" in capsys.readouterr().out


def test_times_are_eastern_and_one_entry_goes_out_per_run(tmp_path, monkeypatch, meta_env):
    from datetime import datetime
    entries = [{"id": "a", "card": "partycohesion", "post_on": date(2026, 11, 12), "time": "19:35"},
               {"id": "b", "card": "senate-unity", "post_on": date(2026, 11, 12)}]
    at = lambda h, m: datetime(2026, 11, 12, h, m, tzinfo=ps.EASTERN)
    got = {(e["id"], s) for e, n, s in ps.due(entries, set(), at(10, 7)) if n == "facebook"}
    assert got == {("a", "later"), ("b", "post")}  # b has no time, so 09:00
    assert ps.scheduled(entries[0]).utcoffset().total_seconds() == -5 * 3600  # EST in November
    queue, posted = tmp_path / "posts.yml", tmp_path / "posted.csv"
    queue.write_text('- {id: a, card: partycohesion, post_on: 2026-11-12, time: "08:00"}\n'
                     "- {id: b, card: senate-unity, post_on: 2026-11-12}\n")
    monkeypatch.setattr(ps, "QUEUE", queue)
    monkeypatch.setattr(ps, "POSTED", posted)
    monkeypatch.delenv("META_IG_USER_ID")
    calls = []
    monkeypatch.setitem(ps.POSTERS, "facebook", lambda card, cap: calls.append(card) or f"fb-{card}")
    ps.run_due(dry_run=False, today=at(12, 7))
    assert calls == ["partycohesion"]  # the earlier one; the other waits for the next hourly run
    ps.run_due(dry_run=False, today=at(13, 7))
    assert calls == ["partycohesion", "senate-unity"]


def test_spotlight_expires_after_a_day():
    from datetime import datetime
    e = [{"id": "s", "card": "member/C001121", "post_on": date(2026, 11, 12), "time": "19:35", "expires_after_days": 1}]
    assert ps.due(e, set(), datetime(2026, 11, 13, 19, 0, tzinfo=ps.EASTERN))[0][2] == "post"
    assert ps.due(e, set(), datetime(2026, 11, 14, 8, 0, tzinfo=ps.EASTERN))[0][2] == "expired"


def test_queue_rejects_unquoted_or_bad_times(tmp_path):
    p = tmp_path / "q.yml"
    p.write_text("- {id: a, card: partycohesion, post_on: 2026-11-12, time: 19:35}\n")  # YAML reads this as a number
    with pytest.raises(ValueError):
        ps.load_queue(p)
    p.write_text('- {id: a, card: partycohesion, post_on: 2026-11-12, time: "25:00"}\n')
    with pytest.raises(ValueError):
        ps.load_queue(p)


def test_member_cards_use_spotlight_files():
    assert ps.image_url("member/C001121", "facebook").endswith("/social/members/C001121-wide.png")
    assert ps.image_url("member/C001121", "instagram").endswith("/social/members/C001121-tall.jpg")
    cap = ps.default_caption("member/C001121")
    assert cap.startswith("Member spotlight:")
    ig = ps.instagram_caption(cap)
    assert "https://" not in ig and ig.endswith("Link in bio.")


def test_alt_text_is_sent_with_each_photo(meta_env, monkeypatch):
    sent = []

    def fake(req, timeout=None):
        import urllib.parse
        sent.append(dict(urllib.parse.parse_qsl(req.data.decode())) if req.data else {})
        return io.BytesIO(json.dumps({"id": "1", "post_id": "1_2", "status_code": "FINISHED"}).encode())

    monkeypatch.setenv("META_PAGE_ID", "123")
    ps.post_facebook("senate-unity", "cap", opener=fake)
    assert sent[-1]["alt_text_custom"].startswith("Line chart")
    ps.post_facebook("member/C001121", "cap", opener=fake)
    assert sent[-1]["alt_text_custom"].startswith("Member spotlight card for Jason Crow")
    ps.post_instagram("senate-unity", "cap", opener=fake, wait=lambda s: None)
    assert any(p.get("alt_text", "").startswith("Line chart") for p in sent)


def test_every_card_has_alt_text_under_the_limit():
    alts = json.loads((ps.CAPTIONS.parent / "alt.json").read_text())
    assert set(alts) == set(json.loads(ps.CAPTIONS.read_text()))
    for e in ps.load_queue():
        a = ps.alt_text(e["card"])
        assert a and len(a) <= 1000 and "—" not in a, e["id"]


def test_require_text_holds_a_post_until_the_card_catches_up(tmp_path, monkeypatch, meta_env):
    from datetime import datetime
    queue, posted = tmp_path / "posts.yml", tmp_path / "posted.csv"
    queue.write_text('- {id: f, card: congress-final, post_on: 2027-01-12, require_text: "final party unity record"}\n'
                     '- {id: g, card: congress-final, post_on: 2027-01-12, require_text: "999th Congress"}\n'
                     '- {id: s, card: senate-unity, post_on: 2027-01-12, time: "10:00"}\n')
    monkeypatch.setattr(ps, "QUEUE", queue)
    monkeypatch.setattr(ps, "POSTED", posted)
    monkeypatch.delenv("META_IG_USER_ID")
    calls = []
    monkeypatch.setitem(ps.POSTERS, "facebook", lambda card, cap: calls.append(card) or f"fb-{card}")
    at = lambda h: datetime(2027, 1, 12, h, 7, tzinfo=ps.EASTERN)
    ps.run_due(dry_run=False, today=at(9))
    ps.run_due(dry_run=False, today=at(10))
    ps.run_due(dry_run=False, today=at(11))
    assert calls == ["congress-final", "senate-unity"]  # g waits, and doesn't block the others
    assert ("g", "facebook") not in ps.load_posted(posted)
