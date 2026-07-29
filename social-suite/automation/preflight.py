"""Pre-flight: confirm every ENABLED account is ready to post — before any send.

Checks that each account's credential is present and non-empty:
  * facebook  -> page_id set + token_file exists & non-empty
  * instagram -> sessionid_file exists & non-empty
  * tiktok    -> TK_cookies_<account>.json exists & non-empty in the cookie dir
  * youtube   -> reported as not-wired (skipped)

Posts NOTHING. Prints a ✅/❌ table and exits 1 if anything is missing, so you
never kick off a live multi-account send with a half-configured account.
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS_PATH = os.path.join(os.path.dirname(HERE), "content", "accounts.json")
TIKTOK_COOKIE_DIR = os.path.expanduser(os.getenv("TIKTOK_COOKIE_DIR", "~/hp-auto/tiktok"))


def _load_accounts() -> dict:
    path = ACCOUNTS_PATH if os.path.exists(ACCOUNTS_PATH) else os.path.join(
        os.path.dirname(HERE), "content", "accounts.example.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f), path


def _nonempty(path: str) -> bool:
    p = os.path.expanduser(path)
    try:
        return os.path.getsize(p) > 0
    except OSError:
        return False


def _check(acct: dict) -> tuple[bool, str]:
    plat = acct.get("platform")
    if plat == "facebook":
        if not acct.get("page_id"):
            return False, "no page_id"
        tf = acct.get("token_file", "")
        return (_nonempty(tf), f"token {tf}") if tf else (False, "no token_file")
    if plat == "instagram":
        sf = acct.get("sessionid_file", "")
        return (_nonempty(sf), f"sessionid {sf}") if sf else (False, "no sessionid_file")
    if plat == "tiktok":
        name = acct.get("tiktok_account", "")
        cookie = os.path.join(TIKTOK_COOKIE_DIR, f"TK_cookies_{name}.json")
        return (_nonempty(cookie), f"cookies {cookie}")
    if plat == "youtube":
        chan = acct.get("yt_channel", "")
        if not chan:
            return False, "no yt_channel"
        token = os.path.expanduser(os.path.join("~/hp-auto/youtube", f"yt_{chan}.json"))
        return (_nonempty(token), f"token {token}")
    return False, f"unknown platform {plat!r}"


def main() -> int:
    cfg, path = _load_accounts()
    print(f"Config: {path}")
    print(f"TikTok cookie dir: {TIKTOK_COOKIE_DIR}\n")

    enabled = [a for a in cfg.get("accounts", []) if a.get("enabled")]
    if not enabled:
        print("No enabled accounts.")
        return 1

    ok_count = 0
    for a in enabled:
        ready, detail = _check(a)
        mark = "✅" if ready else "❌"
        ok_count += ready
        print(f"  {mark}  {a['id']:12} {a['platform']:10} {a.get('brand',''):12} {detail}")

    missing = len(enabled) - ok_count
    print(f"\n{ok_count}/{len(enabled)} accounts ready.")
    if missing:
        print(f"❌ {missing} not ready — fix the ❌ rows above before sending.")
        return 1
    print("✅ All enabled accounts are ready to post.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
