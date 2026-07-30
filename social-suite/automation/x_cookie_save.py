"""Save an X (Twitter) session from cookies you copy out of your NORMAL browser.

X blocks logging in inside an automation browser, so instead we do the same trick
that worked for Instagram: you copy two cookie values from a logged-in x.com tab
(``auth_token`` and ``ct0``) and this writes a Playwright storage_state file that
the poster reuses. Nothing is posted.

    AUTH=<auth_token> CT0=<ct0> python x_cookie_save.py --account HigherPurposeLandscaping
"""

from __future__ import annotations

import argparse
import json
import os


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", required=True, help="X handle / label (for the filename)")
    ap.add_argument("--state-dir", default=os.path.expanduser("~/hp-auto/x"))
    a = ap.parse_args()

    auth = os.environ.get("AUTH", "").strip()
    ct0 = os.environ.get("CT0", "").strip()
    if not auth:
        print("Missing AUTH (the auth_token cookie). Set AUTH=... and re-run.")
        return 2

    os.makedirs(a.state_dir, exist_ok=True)
    dest = os.path.join(a.state_dir, f"x_state_{a.account}.json")

    cookies = []
    for domain in (".x.com", ".twitter.com"):
        cookies.append({"name": "auth_token", "value": auth, "domain": domain,
                        "path": "/", "expires": -1, "httpOnly": True,
                        "secure": True, "sameSite": "None"})
        if ct0:
            cookies.append({"name": "ct0", "value": ct0, "domain": domain,
                            "path": "/", "expires": -1, "httpOnly": False,
                            "secure": True, "sameSite": "Lax"})

    with open(dest, "w", encoding="utf-8") as f:
        json.dump({"cookies": cookies, "origins": []}, f, indent=2)

    print(f"X CONNECTED: {a.account} -> {dest}")
    if not ct0:
        print("(No CT0 given — auth_token alone usually works, but if the poster "
              "has trouble later, re-run with CT0 too.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
