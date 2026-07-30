"""Post ONE video to X (Twitter) using a saved session — via Playwright.

Loads the storage_state saved by x_cookie_save.py / x_login_one.py
(~/hp-auto/x/x_state_<account>.json), opens the composer, attaches the video,
types the caption, waits for the upload to finish, and clicks Post.

    python x_post_one.py --account HigherPurposeLandscaping --video clip.mp4 \
        --caption "..." [--headless]

⚠️ X is aggressive about automation and its web UI changes often. Test each
account once with a throwaway/deletable post before trusting it on the schedule.
"""

from __future__ import annotations

import argparse
import os
import time


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--caption", default="")
    ap.add_argument("--state-dir", default=os.path.expanduser("~/hp-auto/x"))
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--upload-timeout", type=int, default=180)
    a = ap.parse_args()

    state = os.path.join(a.state_dir, f"x_state_{a.account}.json")
    if not os.path.exists(state):
        print(f"No X session for {a.account} at {state}. Connect it first.")
        return 2

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed: ~/hp-venv/bin/pip install playwright && "
              "~/hp-venv/bin/playwright install chromium")
        return 2

    caption = a.caption[:280]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=a.headless)
        ctx = browser.new_context(storage_state=state)
        page = ctx.new_page()
        try:
            page.goto("https://x.com/compose/post", wait_until="domcontentloaded")

            editor = page.locator('[data-testid="tweetTextarea_0"]')
            editor.wait_for(timeout=30000)
            if caption:
                editor.click()
                editor.type(caption, delay=15)

            # Attach the video via the hidden file input.
            page.locator('input[type="file"]').first.set_input_files(a.video)

            # Wait for the upload to finish: X shows a progress bar while encoding,
            # and the Post button stays disabled until it's done.
            post_btn = page.locator('[data-testid="tweetButton"]').first
            deadline = time.time() + a.upload_timeout
            while time.time() < deadline:
                progress = page.locator('[role="progressbar"]').count()
                enabled = post_btn.is_enabled()
                if enabled and progress == 0:
                    break
                time.sleep(2)
            else:
                print("Upload didn't finish before timeout.")
                return 1

            post_btn.click()
            time.sleep(5)  # let the post request go out
            print(f"x ok: {a.account}")
            return 0
        finally:
            ctx.close()
            browser.close()


if __name__ == "__main__":
    raise SystemExit(main())
