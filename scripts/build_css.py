"""Write static/pc.css, the site's styles as a file, and stamp its version into .streamlit/config.toml.

Streamlit loads the CSS file named in the theme's font setting as a stylesheet in the page head, before the app
sends any content. Pointing that setting at this file means the site's styles are in place from the first paint,
instead of arriving a moment after the content (styles sent by the app itself render late, so phones briefly saw
14px inputs and unstacked tables). ui.inject_css still sends the same styles with the visitor's light or dark colors,
which take over once they load; until then the colors follow the device setting.

Run after changing ui.CSS or the theme colors:  python scripts/build_css.py
"""

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import theme  # noqa: E402
import ui  # noqa: E402

CSS_FILE = ROOT / "static" / "pc.css"
CONFIG = ROOT / ".streamlit" / "config.toml"
URL = "https://partycohesion.streamlit.app/~/+/app/static/pc.css"
NAMES = {"bg": "bg", "surface": "surface", "border": "border", "text": "text", "body": "body", "muted": "muted",
         "accent": "accent", "dem": "dem", "rep": "rep", "ind": "ind", "yea": "yea", "nay": "nay", "hero": "hero",
         "hero_text": "hero-text", "head": "head", "tone1": "tone1", "tone2": "tone2", "tone3": "tone3",
         "control": "control"}


def tokens(t: dict) -> str:
    return " ".join(f"--pc-{css}: {t[key]};" for key, css in NAMES.items())


def build() -> str:
    body = ui.CSS.strip().removeprefix("<style>").removesuffix("</style>").strip()
    # @import has to come first in a stylesheet
    imports = "\n".join(line for line in body.splitlines() if line.startswith("@import"))
    rules = "\n".join(line for line in body.splitlines() if not line.startswith("@import"))
    return (f"/* Built by scripts/build_css.py from ui.CSS. Edit ui.py, then run the script. */\n{imports}\n"
            f":root {{ {tokens(theme.LIGHT)} }}\n"
            f"@media (prefers-color-scheme: dark) {{ :root {{ {tokens(theme.DARK)} }} }}\n{rules}\n")


def version(css: str) -> str:
    return hashlib.sha256(css.encode()).hexdigest()[:10]


def config_line(css: str) -> str:
    return f"font = \"'Public Sans':{URL}?v={version(css)}\""


def main() -> None:
    css = build()
    CSS_FILE.write_text(css)
    text = CONFIG.read_text()
    text = re.sub(r"^font = .*$", lambda _: config_line(css), text, count=1, flags=re.M)
    CONFIG.write_text(text)
    print(f"Wrote {CSS_FILE.relative_to(ROOT)} ({len(css):,} bytes) and stamped version {version(css)}")


if __name__ == "__main__":
    main()
