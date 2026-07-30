"""Log in ONE X (Twitter) account in a visible browser and save its session —
WITHOUT posting anything.

Opens a real Chromium window to x.com, you log in by hand at your own pace, then
press Enter here and it saves the whole logged-in session (cookies + storage) to
``~/hp-auto/x/x_state_<account>.json``. The poster reuses that saved session so it
looks like your normal signed-in browser (not a fresh bot login every time).

    python x_login_one.py --account HigherPurposeLandscaping

Needs Playwright + its Chromium:
    ~/hp-venv/bin/pip install playwright
    ~/hp-venv/bin/playwright install chromium
"""

from __future__ import annotations

import argparse
import os


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", required=True, help="X handle / label (used for the filename)")
    ap.add_argument("--state-dir", default=os.path.expanduser("~/hp-auto/x"))
    a = ap.parse_args()

    os.makedirs(a.state_dir, exist_ok=True)
    dest = os.path.join(a.state_dir, f"x_state_{a.account}.json")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright isn't installed in this venv. Install it first:")
        print("  ~/hp-venv/bin/pip install playwright")
        print("  ~/hp-venv/bin/playwright install chromium")
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto("https://x.com/login", wait_until="domcontentloaded")
        print(f"\n>>> A browser opened. Log into X as: {a.account}")
        print(">>> Log in FULLY until you see your normal home timeline.")
        print(">>> NOTHING will be posted.\n")
        input("When you're logged in and see your timeline, come back here and press Enter... ")
        ctx.storage_state(path=dest)
        browser.close()

    if os.path.getsize(dest) > 0:
        print(f"X CONNECTED: {a.account} -> {dest}")
        return 0
    print("ERROR: session file is empty — try again.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
