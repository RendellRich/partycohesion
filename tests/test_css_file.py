"""static/pc.css (loaded in the page head through the theme font setting) must match ui.CSS."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_css", ROOT / "scripts" / "build_css.py")
build_css = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_css)


def test_css_file_is_current():
    css = build_css.build()
    assert (ROOT / "static" / "pc.css").read_text() == css, "Run python scripts/build_css.py"
    assert build_css.config_line(css) in (ROOT / ".streamlit" / "config.toml").read_text(), \
        "Run python scripts/build_css.py"


def test_css_file_has_no_imports():
    # An @import holds the whole stylesheet back until the imported file loads
    assert "@import" not in (ROOT / "static" / "pc.css").read_text()
