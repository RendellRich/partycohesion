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
            if req.full_url.split("?")[0].endswith("/me"):
                self.calls.append(("GET", req.full_url.split("?")[0], {}))
                return io.BytesIO(json.dumps({"id": "999"}).encode())
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
        assert e["card"] in caps
        ps.check_caption(e.get("caption") or caps[e["card"]])


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
        return io.BytesIO(json.dumps({"id": "999", "name": "PartyCohesion"}).encode())

    assert ps.check_setup(opener=fake) == 0
    assert calls == [("GET", f"https://graph.facebook.com/{ps.GRAPH_VERSION}/me")]
    out = capsys.readouterr().out
    assert "PartyCohesion" in out and "SECRETVALUE123" not in out
