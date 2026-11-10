"""Keeps the Streamlit Community Cloud app from going to sleep.

Community Cloud puts an app to sleep after 12 hours without a visitor, and a visitor then has to click
"Yes, get this app back up!" and wait. Commits don't count as visits. This opens the app in a headless browser like a
real visitor, clicks the wake button if the app is asleep, and waits until the home page has loaded.

Run by .github/workflows/keep-awake.yml every few hours. Needs: pip install playwright && playwright install chromium
"""

import sys
import time

from playwright.sync_api import sync_playwright

SITE = "https://partycohesion.streamlit.app/"
WAKE_TEXT = "get this app back up"
APP_TEXT = "Do members of Congress"  # the home page headline
TIMEOUT_S = 240


def app_loaded(page) -> bool:
    for frame in page.frames:  # Community Cloud serves the app inside an iframe
        try:
            if frame.get_by_text(APP_TEXT).count():
                return True
        except Exception:
            pass
    return False


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(SITE, wait_until="domcontentloaded", timeout=90_000)
        woke = False
        start = time.time()
        while time.time() - start < TIMEOUT_S:
            if app_loaded(page):
                print(f"App is up ({'woke it' if woke else 'already awake'}) after {time.time() - start:.0f}s")
                browser.close()
                return 0
            button = page.get_by_role("button", name=WAKE_TEXT)
            if not woke and button.count():
                print("App was asleep. Clicking the wake button.")
                button.first.click()
                woke = True
            page.wait_for_timeout(5000)
        page.screenshot(path="keep-awake-failure.png")
        browser.close()
    print(f"The app didn't load within {TIMEOUT_S}s", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
