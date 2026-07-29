"""Upload ONE video to a YouTube channel as a Short — via the official API.

Uses the token saved by youtube_connect_one.py. Called by post_multi.py. Marks
the upload a Short by keeping it vertical (uniquify already renders 1080x1920) and
appending #Shorts to the description.

    python youtube_upload_one.py --channel Landscaping --video clip.mp4 \
        --title "..." --description "..." --tags "a,b,c" --privacy public
"""

from __future__ import annotations

import argparse
import os

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True)
    ap.add_argument("--video", required=True)
    ap.add_argument("--title", default="Higher Purpose")
    ap.add_argument("--description", default="")
    ap.add_argument("--tags", default="")  # comma-separated
    ap.add_argument("--privacy", default="public", choices=["public", "unlisted", "private"])
    ap.add_argument("--token-dir", default=os.path.expanduser("~/hp-auto/youtube"))
    a = ap.parse_args()

    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    token = os.path.join(a.token_dir, f"yt_{a.channel}.json")
    if not os.path.exists(token):
        print(f"No YouTube token for {a.channel} at {token}. Run youtube_connect_one.py first.")
        return 2

    creds = Credentials.from_authorized_user_file(token, SCOPES)
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())

    yt = build("youtube", "v3", credentials=creds)

    desc = (a.description + "\n\n#Shorts").strip()
    tags = [t.strip() for t in a.tags.split(",") if t.strip()]
    body = {
        "snippet": {"title": a.title[:100], "description": desc[:5000],
                    "tags": tags, "categoryId": "22"},  # 22 = People & Blogs
        "status": {"privacyStatus": a.privacy, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(a.video, chunksize=-1, resumable=True, mimetype="video/*")
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    resp = None
    while resp is None:
        _status, resp = request.next_chunk()
    print(f"youtube ok: {a.channel} -> https://youtu.be/{resp['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
