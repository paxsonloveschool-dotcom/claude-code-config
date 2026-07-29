"""Authorize ONE YouTube channel via Google's official OAuth — saves a reusable
token so the poster can upload through the approved API (zero ban risk).

One-time: you create an OAuth client in Google Cloud and download client_secret.json.
Then, per channel, this opens Google's consent page in your browser; you pick the
channel's Google account and click Allow, and it saves the token to
``~/hp-auto/youtube/yt_<channel>.json``. Nothing is posted.

    python youtube_connect_one.py --channel Landscaping \
        --client-secret ~/hp-auto/client_secret.json
"""

from __future__ import annotations

import argparse
import os

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True, help="channel label, e.g. Landscaping")
    ap.add_argument("--client-secret", default=os.path.expanduser("~/hp-auto/client_secret.json"))
    ap.add_argument("--token-dir", default=os.path.expanduser("~/hp-auto/youtube"))
    a = ap.parse_args()

    cs = os.path.expanduser(a.client_secret)
    if not os.path.exists(cs):
        print(f"client_secret.json not found at: {cs}")
        print("Create an OAuth client in Google Cloud and save the download there first.")
        return 2

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Google libraries aren't installed in this venv. Install them:")
        print("  ~/hp-venv/bin/pip install google-api-python-client "
              "google-auth-oauthlib google-auth-httplib2")
        return 2

    os.makedirs(a.token_dir, exist_ok=True)
    dest = os.path.join(a.token_dir, f"yt_{a.channel}.json")

    flow = InstalledAppFlow.from_client_secrets_file(cs, SCOPES)
    print(f"\n>>> A browser will open. Sign in with the Google account for the "
          f"{a.channel} YouTube channel and click Allow.")
    print(">>> NOTHING will be posted.\n")
    creds = flow.run_local_server(port=0, prompt="consent", authorization_prompt_message="")

    with open(dest, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    print(f"YOUTUBE CONNECTED: {a.channel} -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
