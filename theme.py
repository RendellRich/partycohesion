"""Light and dark color tokens.

Visitors pick light or dark in the app's Settings menu (it starts on their device's setting). Streamlit styles its own
widgets from .streamlit/config.toml; this module gives the site's own HTML and charts the matching colors.

Every chart and page is written with the dark tokens. In light mode, ui.inject_css() switches the CSS variables and
chart_utils.show_chart() swaps each dark token in a figure for its light partner, so nothing else needs to know the
mode. Party, vote and pattern colors in both modes pass the dataviz palette checks against their own background.
"""

import streamlit as st

DARK = {
    "bg": "#171614", "surface": "#21201D", "border": "#3A3733", "grid": "#3A3733",
    "text": "#FAFAFA", "body": "#E7E5E4", "muted": "#A8A29E", "accent": "#E9C46A",
    "dem": "#5A97D2", "rep": "#E06C6C", "ind": "#A8A29E",
    "yea": "#8ECAE6", "nay": "#577590",
    "consistent": "#E7DFF5", "partly": "#B9A6E3", "changed": "#9576D8", "opposite": "#7A8597",
}
LIGHT = {
    "bg": "#F6F7F9", "surface": "#FFFFFF", "border": "#DADDE3", "grid": "#E3E6EA",
    "text": "#1B1D21", "body": "#2A2E35", "muted": "#555B65", "accent": "#7A5A10",
    "dem": "#2E6CAD", "rep": "#B8403F", "ind": "#6B7280",
    "yea": "#1F6F99", "nay": "#9DB2C8",
    "consistent": "#3F2A88", "partly": "#6B4FBF", "changed": "#9A82D9", "opposite": "#7A8597",
}
FONT = "'Public Sans', 'Segoe UI', system-ui, sans-serif"

# Dark hex -> light hex, for swapping colors inside finished charts
TO_LIGHT = {DARK[k].lower(): LIGHT[k] for k in DARK if DARK[k].lower() != "#a8a29e"}
TO_LIGHT["#a8a29e"] = LIGHT["muted"]  # muted text and the Independent color share a hex in dark mode


# A tiny script that reads the page's real background color and reports "light" or "dark". Streamlit's own
# st.context.theme can be stale on first load and right after a visitor switches themes, so this reruns the page
# whenever the reported mode and the drawn mode differ.
_SYNC_JS = """
export default function(component) {
  const { data, setStateValue } = component;
  const read = () => {
    const el = document.querySelector('.stApp');
    if (!el) return null;
    const m = getComputedStyle(el).backgroundColor.match(/\\d+(\\.\\d+)?/g);
    if (!m) return null;
    const [r, g, b] = m.map(Number);
    return (0.299 * r + 0.587 * g + 0.114 * b) > 140 ? 'light' : 'dark';
  };
  let sent = data;
  const check = () => {
    const now = read();
    if (now && now !== sent) { sent = now; setStateValue('mode', now); }
  };
  check();
  const timer = setInterval(check, 400);
  return () => clearInterval(timer);
}
"""
_sync = None


def sync() -> None:
    """Mount the theme reporter once per run, near the top of app.py."""
    global _sync
    if _sync is None:
        _sync = st.components.v2.component("pc_theme_sync", js=_SYNC_JS, isolate_styles=False)
    result = _sync(key="pc_theme", data=mode(), default={"mode": None}, on_mode_change=lambda: None, height=0)
    reported = getattr(result, "mode", None)
    if reported in ("light", "dark"):
        st.session_state["pc_mode"] = reported


def mode() -> str:
    """'light' or 'dark' for the visitor's current theme (dark if nothing can tell yet)."""
    kind = st.session_state.get("pc_mode") if st.runtime.exists() else None
    if kind is None:
        try:
            kind = st.context.theme.type
        except Exception:  # noqa: BLE001 - outside a session (tests, scripts)
            kind = None
    return "light" if kind == "light" else "dark"


def _lum(hex_color: str) -> float:
    r, g, b = (int(hex_color.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def text_on(fill: str) -> str:
    """Near-black or white, whichever reads better on this fill."""
    lum = _lum(fill)
    return "#171614" if (lum + 0.05) / 0.0517 >= 1.05 / (lum + 0.05) else "#FFFFFF"


def tokens() -> dict:
    return LIGHT if mode() == "light" else DARK


def to_mode(color):
    """A dark-token color as it should look in the current mode; anything else is returned unchanged."""
    if mode() != "light" or not isinstance(color, str):
        return color
    return TO_LIGHT.get(color.lower(), color)
