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


# Public Sans from Google Fonts (variable weight, Latin), as Google's own stylesheet declares it
_GSTATIC = "https://fonts.gstatic.com/s/publicsans/v21/"
_LATIN = ("U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, "
          "U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD")
FONT_FACES = "".join(
    f"@font-face {{ font-family: 'Public Sans'; font-style: {style}; font-weight: 400 700; font-display: swap; "
    f"src: url({_GSTATIC}{file}) format('woff2'); unicode-range: {_LATIN}; }}\n"
    for style, file in (("normal", "ijwRs572Xtc6ZYQws9YVwnNGfJ4.woff2"),
                        ("italic", "ijwAs572Xtc6ZYQws9YVwnNDZpDyNjGolS673tpRgDcqd1s.woff2")))


def tokens(t: dict) -> str:
    return " ".join(f"--pc-{css}: {t[key]};" for key, css in NAMES.items())


def build() -> str:
    body = ui.CSS.strip().removeprefix("<style>").removesuffix("</style>").strip()
    # No @import of the web fonts: a stylesheet with an @import isn't applied until the imported file loads too,
    # which made the site styles land after the content. Public Sans is declared here directly instead (Source Serif 4
    # loads from the theme's headingFont setting).
    rules = "\n".join(line for line in body.splitlines() if not line.startswith("@import"))
    return ("/* Built by scripts/build_css.py from ui.CSS. Edit ui.py, then run the script. */\n" + FONT_FACES
            + f":root {{ {tokens(theme.LIGHT)} }}\n"
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
