#!/usr/bin/env python3
"""Schedule social posts to Postiz via its public API.

Reads posts from a JSON file and creates/schedules each one through the
Postiz public API. Zero third-party dependencies (stdlib urllib only).

Confirmed against gitroomhq/postiz-app source:
  - Endpoint:  POST {base}/public/v1/posts
  - Auth:      `Authorization: <API_KEY>`  (raw key, NO "Bearer " prefix)
  - Body:      CreatePostDto (see build_payload below)
  Sources:
    apps/sdk/src/index.ts
    apps/backend/src/public-api/routes/v1/public.integrations.controller.ts
    libraries/nestjs-libraries/src/dtos/posts/create.post.dto.ts
    libraries/nestjs-libraries/src/dtos/media/media.dto.ts

Config (env vars):
  POSTIZ_API_URL   Base URL, e.g. https://api.postiz.com  or  https://social.example.com
                   (the script appends /public/v1/posts; do NOT include it yourself)
  POSTIZ_API_KEY   API key from Postiz UI -> Settings -> Public API

Posts file (JSON): a list of objects, each:
  {
    "text": "caption with #hashtags and emojis",     # required
    "channels": ["INTEGRATION_ID", ...],             # required (Postiz integration ids)
    "schedule": "2026-07-01T14:00:00Z" | null,       # ISO 8601; null = post now
    "image": "https://.../photo.jpg" | null          # optional public media URL
  }

Usage:
  POSTIZ_API_URL=https://api.postiz.com POSTIZ_API_KEY=xxx \\
      python3 schedule_posts.py content/hp-landscaping.json
  python3 schedule_posts.py content/restore.json --dry-run
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone


def load_posts(path):
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        sys.exit(f"Error: {path} must contain a JSON array of post objects.")
    return data


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_channel_map(path):
    """Optional friendly-label -> integration-id map (automation/channels.json).

    Lets content files use readable names like "hp-instagram" instead of raw
    Postiz integration ids, so you can see at a glance which business/account a
    post targets. Returns {} when no map file exists (raw ids still work).
    """
    if path and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def resolve_channels(channels, cmap, known_labels):
    """Return (resolved_ids, unresolved_labels) for a post's channel entries.

    - A known friendly label (or REPLACE_WITH placeholder) MUST resolve via the
      map; if it isn't in the map it's reported unresolved (and the post is
      skipped) — never sent as a literal id.
    - Anything else with no map is treated as a raw integration id (e.g. ids
      injected by plan_calendar.py --channels).
    """
    resolved, unresolved = [], []
    for c in channels:
        if c in cmap:
            resolved.append(cmap[c])
        elif c in known_labels or "REPLACE_WITH" in c:
            unresolved.append(c)
        elif cmap:
            unresolved.append(c)
        else:
            resolved.append(c)
    return resolved, unresolved


def build_payload(post, channel_ids):
    """Map a simple post dict to the Postiz CreatePostDto shape.

    Postiz requires the SAME content to be duplicated per target integration
    inside the `posts` array (one entry per channel). `channel_ids` are the
    resolved Postiz integration ids (after label lookup).
    """
    text = post.get("text")
    if not text:
        raise ValueError("post is missing required 'text'")
    if not channel_ids:
        raise ValueError("post has no resolved channels")

    schedule = post.get("schedule")
    # type: 'now' posts immediately, 'schedule' posts at `date`.
    post_type = "schedule" if schedule else "now"
    date = schedule if schedule else now_iso()

    image = post.get("image")
    # MediaDto requires id + path. For a plain URL we don't have an uploaded
    # media id, so we reuse the url as id. ASSUMED: passing an external url as
    # both id and path works for self-hosted; otherwise upload media first and
    # use the returned media id. Empty list when no image.
    images = [{"id": image, "path": image}] if image else []

    per_channel = []
    for cid in channel_ids:
        per_channel.append(
            {
                "integration": {"id": cid},
                "value": [{"content": text, "image": images}],
                # settings is required unless type == 'draft'. Empty object lets
                # Postiz apply each provider's defaults.
                "settings": {},
            }
        )

    return {
        "type": post_type,
        "date": date,
        "shortLink": False,
        "tags": [],
        "posts": per_channel,
    }


def send(base_url, api_key, payload):
    url = base_url.rstrip("/") + "/public/v1/posts"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": api_key,  # raw key, no "Bearer " prefix
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, resp.read().decode("utf-8")


def main():
    parser = argparse.ArgumentParser(description="Schedule posts to Postiz.")
    parser.add_argument("posts_file", help="Path to JSON posts file.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payloads without calling the API.",
    )
    parser.add_argument(
        "--channels-map",
        default=None,
        help="Path to a label->id JSON map (default: channels.json next to this "
             "script, or $POSTIZ_CHANNELS_MAP).",
    )
    args = parser.parse_args()

    posts = load_posts(args.posts_file)

    map_path = (args.channels_map or os.environ.get("POSTIZ_CHANNELS_MAP")
                or os.path.join(os.path.dirname(os.path.abspath(__file__)), "channels.json"))
    cmap = load_channel_map(map_path)
    if cmap:
        print(f"Using channel map: {map_path} ({len(cmap)} labels)")
    # Friendly labels we ship — these must always resolve via a map.
    example_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "channels.example.json")
    known_labels = set(load_channel_map(example_path).keys())

    base_url = os.environ.get("POSTIZ_API_URL")
    api_key = os.environ.get("POSTIZ_API_KEY")
    if not args.dry_run and (not base_url or not api_key):
        sys.exit("Error: set POSTIZ_API_URL and POSTIZ_API_KEY (or use --dry-run).")

    failures = 0
    for i, post in enumerate(posts, 1):
        label = post.get("text", "")[:50].replace("\n", " ")
        channels = post.get("channels") or []
        resolved, unresolved = resolve_channels(channels, cmap, known_labels)

        if args.dry_run:
            try:
                payload = build_payload(post, resolved or channels)
            except ValueError as exc:
                print(f"[{i}] SKIP ({exc}): {label!r}")
                failures += 1
                continue
            print(f"[{i}] DRY-RUN -> POST {(base_url or '<POSTIZ_API_URL>')}"
                  "/public/v1/posts  channels={}".format(resolved or channels))
            if unresolved:
                print(f"    note: unresolved label(s) {unresolved} — add them to "
                      "channels.json before a live run")
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            continue

        if unresolved or not resolved:
            why = (f"unresolved channel label(s) {unresolved}" if unresolved
                   else "no channels")
            print(f"[{i}] SKIP ({why}; fill channels.json or the JSON): {label!r}")
            failures += 1
            continue

        try:
            payload = build_payload(post, resolved)
        except ValueError as exc:
            print(f"[{i}] SKIP ({exc}): {label!r}")
            failures += 1
            continue

        try:
            status, text = send(base_url, api_key, payload)
            print(f"[{i}] OK ({status}): {label!r}")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            print(f"[{i}] FAIL ({exc.code}): {label!r}\n    {detail}")
            failures += 1
        except urllib.error.URLError as exc:
            print(f"[{i}] FAIL (network): {label!r}\n    {exc.reason}")
            failures += 1

    if failures:
        sys.exit(f"\nDone with {failures} failure(s).")
    print("\nAll posts processed successfully.")


if __name__ == "__main__":
    main()
