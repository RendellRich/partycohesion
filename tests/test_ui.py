"""Name, date and table formatting used across pages."""
from ui import congress_years, display_name, fmt_date, last_name, pattern_badge


def test_display_name():
    assert display_name("Schumer, Charles Ellis (Chuck)") == "Chuck Schumer"
    assert display_name("Murkowski, Lisa") == "Lisa Murkowski"
    assert display_name("King, Angus Stanley, Jr.") == "Angus King Jr."
    assert display_name("Cher") == "Cher"
    assert last_name("McConnell, Addison Mitchell (Mitch)") == "McConnell"


def test_congress_years():
    assert congress_years(110, 119, 119) == "2007 to now"
    assert congress_years(110, 112, 119) == "2007 to 2012"


def test_fmt_date_has_no_leading_zero():
    assert fmt_date("2026-09-03") == "Sep 3, 2026"


def test_badge_escapes_unknown_labels():
    assert "&lt;b&gt;" in pattern_badge("<b>")


def test_cache_clears_only_when_data_files_change(tmp_path, monkeypatch):
    import os
    import chart_utils
    cleared = []
    monkeypatch.setattr(chart_utils.st.cache_data, "clear", lambda: cleared.append(1))
    monkeypatch.setattr(chart_utils, "_seen_data_version", None)
    f = tmp_path / "members.csv"
    f.write_text("a\n1\n")
    os.utime(f, (1_000_000, 1_000_000))
    assert chart_utils.clear_cache_if_data_changed(tmp_path) is False  # first run only records the version
    assert chart_utils.clear_cache_if_data_changed(tmp_path) is False  # nothing changed
    os.utime(f, (2_000_000, 2_000_000))  # a refresh rewrote the file
    assert chart_utils.clear_cache_if_data_changed(tmp_path) is True
    assert cleared == [1]
