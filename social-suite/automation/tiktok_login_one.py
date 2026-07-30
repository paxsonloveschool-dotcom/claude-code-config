"""Log in ONE TikTok account and save its cookies — WITHOUT posting anything.

tiktokautouploader bundles login into ``upload_tiktok()``, but the login step is a
separate internal function (``_load_or_create_cookies``) that opens a *visible*
browser, waits for you to finish logging in, saves ``TK_cookies_<account>.json``
in the current directory, and returns — never reaching the upload code. We call
exactly that, so an account gets connected with zero posts.

Runs from a fixed cookie directory (default ``~/hp-auto/tiktok``) so every
account's cookie file lives in one place that the poster (post_multi.py) also
reads from.

    python tiktok_login_one.py --account HpPools

⚠️ The browser that opens is a FRESH session — log into the exact account you
named (the filename is just a label; whatever account you log into is what gets
saved). Log in fully until you see the For You feed, then it saves and closes.
"""

from __future__ import annotations

import argparse
import os
from shutil import which


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", required=True, help="TikTok account label (cookie filename)")
    ap.add_argument("--cookie-dir", default=os.path.expanduser("~/hp-auto/tiktok"))
    a = ap.parse_args()

    # Node runs the login browser (login.js). Fail early with a clear message.
    if not which("node") or not which("npm"):
        print("Node.js is required for TikTok login but wasn't found on PATH.")
        print("Install it (either one), then re-run:")
        print("  • https://nodejs.org  (download the LTS installer), or")
        print("  • brew install node")
        return 2

    os.makedirs(a.cookie_dir, exist_ok=True)
    os.chdir(a.cookie_dir)  # cookies are saved relative to the working directory

    from tiktokautouploader import function as f  # heavy import, lazy

    dest = os.path.join(a.cookie_dir, f"TK_cookies_{a.account}.json")
    if os.path.exists(dest):
        try:
            expired = f.check_expiry(a.account)
        except Exception:  # noqa: BLE001 — unreadable/odd file, just re-login
            expired = True
        if not expired:
            print(f"ALREADY CONNECTED: {a.account} -> {dest} (still valid, nothing to do)")
            return 0
        print(f"Cookies for {a.account} expired — logging in again...")

    print(f"Opening a browser to log in as TikTok account: {a.account}")
    print("Log in fully until you see the For You feed. NOTHING will be posted.")
    f._load_or_create_cookies(a.account, None)  # login-only; no upload

    if os.path.exists(dest):
        print(f"TIKTOK CONNECTED: {a.account} -> {dest}")
        return 0
    print("ERROR: login finished but no cookie file was saved. Try again.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
