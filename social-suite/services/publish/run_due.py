"""Publish all due posts from the queue — the script GitHub Actions runs.

Reads ``content/queue.json`` (overridable), finds posts that are due now,
resolves each post's ``brand`` to its Meta credentials, routes it to the right
platform poster, marks ``sent``/``failed`` per post, and writes the queue back.
One failing post never aborts the rest.

Multi-brand: each queued post may carry a ``brand`` (e.g. "hp" / "restore");
``services.publish.brands`` maps that to per-brand credentials. A post with no
``brand`` uses the ``"default"`` brand (legacy single account), so the original
single-account path keeps working unchanged.

Env (single-account / "default" brand fallback):
    META_ACCESS_TOKEN  Long-lived Meta token (FB Page + IG publishing).
    IG_USER_ID         Instagram Professional account id (for "instagram").
    FB_PAGE_ID         Facebook Page id (for "facebook").
Env (multi-brand):
    BRANDS_JSON        JSON object {brand: {meta_access_token, ig_user_id,
                       fb_page_id}} — one secret holding every brand's creds.
    BRANDS_FILE        Optional path to a brands JSON file (default
                       content/brands.json) used when BRANDS_JSON is unset.
    QUEUE_PATH         Optional queue file path (default content/queue.json).

Usage:
    python services/publish/run_due.py [queue_path] [--dry-run]
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

# Make this runnable both as a module and as a bare script (GitHub Actions runs
# it by path), so ``services.publish.*`` imports resolve either way.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.publish.brands import BrandCreds  # noqa: E402
from services.publish.queue import (  # noqa: E402
    QueuedPost,
    due_posts,
    load_queue,
    save_queue,
)

DEFAULT_QUEUE_PATH = "content/queue.json"
DEFAULT_BRAND = "default"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Platform adapters -------------------------------------------------------
# Each adapter takes (post, creds) and fires that ONE platform, raising a clear
# RuntimeError when the brand is missing the creds that platform needs. The
# ADAPTERS registry maps a platform name to its adapter; ``_post_one`` routes
# each of a post's platforms through it. Posters are imported lazily inside the
# adapters so importing this module needs no network and no third-party deps.


def _adapt_facebook(post: QueuedPost, creds: BrandCreds) -> None:
    from services.publish.direct import meta  # lazy

    token = creds.meta_access_token
    if not token:
        raise RuntimeError("meta_access_token is not set for this brand (needed for facebook).")
    page_id = creds.fb_page_id
    if not page_id:
        raise RuntimeError("fb_page_id is not set for this brand (needed for facebook).")
    meta.post_facebook(
        page_id=page_id,
        access_token=token,
        message=post.text,
        image_url=post.media_url,
    )


def _adapt_instagram(post: QueuedPost, creds: BrandCreds) -> None:
    from services.publish.direct import meta  # lazy

    token = creds.meta_access_token
    if not token:
        raise RuntimeError("meta_access_token is not set for this brand (needed for instagram).")
    ig_user_id = creds.ig_user_id
    if not ig_user_id:
        raise RuntimeError("ig_user_id is not set for this brand (needed for instagram).")
    if not post.media_url:
        raise RuntimeError("instagram requires a public media_url.")
    meta.post_instagram(
        ig_user_id=ig_user_id,
        access_token=token,
        caption=post.text,
        image_url=post.media_url,
    )


def _adapt_x(post: QueuedPost, creds: BrandCreds) -> None:
    from services.publish.direct import x  # lazy

    token = creds.x.get("access_token")
    if not token:
        raise RuntimeError("x.access_token is not set for this brand (needed for x).")
    media_urls = [post.media_url] if post.media_url else None
    x.post_x(text=post.text, access_token=token, media_urls=media_urls)


def _tiktok_access_token(creds: BrandCreds) -> str:
    """Return a usable TikTok access token for this brand.

    TikTok access tokens expire in ~24h, so a statically-pasted token is no good
    for an unattended cron. When the brand carries a ``refresh_token`` (+ app
    ``client_key``/``client_secret``), mint a fresh access token just-in-time;
    otherwise fall back to a static ``access_token`` (e.g. a sandbox token).
    """
    refresh_token = creds.tiktok.get("refresh_token")
    client_key = creds.tiktok.get("client_key")
    client_secret = creds.tiktok.get("client_secret")
    if refresh_token and client_key and client_secret:
        from services.publish.direct import tiktok_oauth  # lazy

        payload = tiktok_oauth.refresh_access_token(
            client_key, client_secret, refresh_token
        )
        token = payload.get("access_token")
        if not token:
            raise RuntimeError(f"TikTok refresh returned no access_token: {payload!r}")
        return token

    token = creds.tiktok.get("access_token")
    if not token:
        raise RuntimeError(
            "tiktok needs either a refresh_token (+client_key/client_secret) or a "
            "static access_token for this brand (see social-suite/TIKTOK_SETUP.md)."
        )
    return token


def _adapt_tiktok(post: QueuedPost, creds: BrandCreds) -> None:
    from services.publish.direct import tiktok  # lazy

    if not post.media_url:
        raise RuntimeError("tiktok requires a public video media_url.")
    token = _tiktok_access_token(creds)
    privacy = creds.tiktok.get("privacy_level", "SELF_ONLY")
    tiktok.post_tiktok(
        access_token=token,
        caption=post.text,
        video_url=post.media_url,
        privacy_level=privacy,
    )


def _adapt_youtube(post: QueuedPost, creds: BrandCreds) -> None:
    from services.publish.direct import youtube  # lazy

    token = creds.youtube.get("access_token")
    if not token:
        raise RuntimeError("youtube.access_token is not set for this brand (needed for youtube).")
    if not post.media_url:
        raise RuntimeError("youtube requires a video media_url (path or URL).")
    title = creds.youtube.get("title") or post.text[:100]
    youtube.post_youtube(
        access_token=token,
        title=title,
        description=post.text,
        video_path_or_url=post.media_url,
    )


def _adapt_gbp(post: QueuedPost, creds: BrandCreds) -> None:
    from services.publish.direct import gbp  # lazy

    token = creds.gbp.get("access_token")
    account_id = creds.gbp.get("account_id")
    location_id = creds.gbp.get("location_id")
    if not token:
        raise RuntimeError("gbp.access_token is not set for this brand (needed for gbp).")
    if not account_id or not location_id:
        raise RuntimeError(
            "gbp.account_id and gbp.location_id are required for this brand (needed for gbp)."
        )
    gbp.post_gbp(
        access_token=token,
        account_id=account_id,
        location_id=location_id,
        summary=post.text,
        media_url=post.media_url,
    )


# Adapter registry: platform name -> adapter callable. Generalizes the old
# if-ladder so adding a platform is one entry here plus its adapter module.
ADAPTERS = {
    "facebook": _adapt_facebook,
    "instagram": _adapt_instagram,
    "x": _adapt_x,
    "tiktok": _adapt_tiktok,
    "youtube": _adapt_youtube,
    "gbp": _adapt_gbp,
}


def _post_one(post: QueuedPost, creds: BrandCreds) -> None:
    """Route a single post to each of its target platforms using ``creds``.

    Raises on the first platform error so the caller can mark the post failed.
    """
    for platform in post.platforms:
        adapter = ADAPTERS.get(platform)
        if adapter is None:
            raise RuntimeError(f"Unsupported platform: {platform!r}")
        adapter(post, creds)


def run(queue_path: str, *, dry_run: bool = False, now_iso: str | None = None) -> dict:
    """Publish all due posts and return a summary dict.

    Args:
        queue_path: Path to the queue JSON file.
        dry_run: When True, route nothing — only print what WOULD post.
        now_iso: Override "now" (ISO-8601 UTC); defaults to the real now.

    Returns:
        {"posted": int, "failed": int, "skipped": int} counts.
    """
    from services.publish import brands as brands_mod  # lazy, stdlib-only

    now = now_iso or _now_iso()
    posts = load_queue(queue_path)
    due = due_posts(posts, now)
    due_ids = {id(p) for p in due}

    # Load the brand -> credentials map once. A bad BRANDS_JSON/file fails the
    # whole run loudly (CI should surface it), like a missing token used to.
    brand_map = brands_mod.load_brands()

    posted = failed = 0
    # Per-brand tallies for the summary, keyed by the resolved brand name.
    per_brand: dict[str, dict[str, int]] = {}

    def _tally(name: str, key: str) -> None:
        per_brand.setdefault(name, {"posted": 0, "failed": 0})[key] += 1

    for post in due:
        brand_name = post.brand or DEFAULT_BRAND
        targets = ",".join(post.platforms)
        if dry_run:
            print(
                f"[dry-run] WOULD post {post.id} (brand={brand_name}) "
                f"-> [{targets}]: {post.text[:60]!r}"
            )
            continue
        try:
            creds = brands_mod.get_brand(post.brand, brand_map)
            _post_one(post, creds)
            post.status = "sent"
            post.error = None
            posted += 1
            _tally(brand_name, "posted")
            print(f"[sent] {post.id} (brand={brand_name}) -> [{targets}]")
        except Exception as e:  # noqa: BLE001 — isolate per-post failures
            post.status = "failed"
            post.error = str(e)
            failed += 1
            _tally(brand_name, "failed")
            print(f"[failed] {post.id} (brand={brand_name}) -> [{targets}]: {e}")

    skipped = sum(1 for p in posts if id(p) not in due_ids and p.status == "pending")

    if not dry_run:
        save_queue(queue_path, posts)

    summary = {"posted": posted, "failed": failed, "skipped": skipped}
    if per_brand and not dry_run:
        print("\nPer-brand:")
        for name in sorted(per_brand):
            b = per_brand[name]
            print(f"  {name}: posted={b['posted']} failed={b['failed']}")
    print(
        f"\nSummary: posted={posted} failed={failed} "
        f"skipped(not-due)={skipped} (dry_run={dry_run})"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Publish due posts from the queue.")
    parser.add_argument(
        "queue_path",
        nargs="?",
        default=os.environ.get("QUEUE_PATH", DEFAULT_QUEUE_PATH),
        help="Path to queue.json (default: content/queue.json or $QUEUE_PATH).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Route nothing.")
    args = parser.parse_args(argv)

    summary = run(args.queue_path, dry_run=args.dry_run)
    # Non-zero exit if anything failed, so the Action surfaces it (but the queue
    # is already saved so successes persist).
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
