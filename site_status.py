"""Shows a notice on every page when the automatic data refresh has failed or stopped running,
so visitors know the numbers may not include the newest votes."""

import json
import urllib.request
from datetime import datetime, timezone

import streamlit as st

REPO = "RendellRich/partycohesion"
WORKFLOW = "refresh-data.yml"
OVERDUE_DAYS = 9  # runs twice a week, so more than 9 days means at least two missed runs


@st.cache_data(ttl=3600, show_spinner=False)
def refresh_status():
    """Latest scheduled/manual refresh runs from the public GitHub API. Returns None if unavailable."""
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}/runs?per_page=10&status=completed"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                                   "User-Agent": "partycohesion-app"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            runs = json.load(resp).get("workflow_runs", [])
    except Exception:
        return None
    if not runs:
        return None
    last = runs[0]
    last_success = next((r for r in runs if r.get("conclusion") == "success"), None)
    return {
        "last_conclusion": last.get("conclusion"),
        "last_time": last.get("updated_at"),
        "last_success_time": last_success.get("updated_at") if last_success else None,
    }


def show_refresh_notice() -> None:
    status = refresh_status()
    if not status:
        return
    now = datetime.now(timezone.utc)

    def parse(t):
        return datetime.fromisoformat(t.replace("Z", "+00:00")) if t else None

    last_success = parse(status["last_success_time"])
    if status["last_conclusion"] not in ("success", "cancelled", "skipped"):
        when = f" (last successful update {last_success:%b} {last_success.day}, {last_success.year})" if last_success else ""
        st.warning(f"The latest automatic data refresh didn't complete, so the newest votes may be missing{when}.",
                   icon="⚠️")
    elif last_success and (now - last_success).days > OVERDUE_DAYS:
        st.warning(f"The data hasn't been refreshed since {last_success:%b} {last_success.day}, {last_success.year}. The newest votes may be missing.",
                   icon="⚠️")
