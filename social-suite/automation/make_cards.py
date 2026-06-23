"""Generate branded image cards for queued posts and wire them in for Instagram.

Instagram requires an image at a PUBLIC url; Facebook does not. Our per-brand
content is text-first, so for any post we want on Instagram we render the caption
into a branded card (``services.media.card``), save it under ``content/cards/``
(committed, so it gets a ``raw.githubusercontent.com`` url), set the post's
``media_url`` to that url, and add ``"instagram"`` to its platforms.

Safe by default: prints a PLAN and writes nothing unless ``--apply`` is given.
It never changes a post's ``status`` (paused stays paused) — so it cannot cause
anything to post. Pure stdlib except the lazy Pillow import inside the renderer.

Usage:
    python automation/make_cards.py --brand hp                 # dry-run plan
    python automation/make_cards.py --brand hp --apply         # render + wire
    python automation/make_cards.py --brand hp --add-instagram --apply
"""

from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
QUEUE_PATH = os.path.join(ROOT, "content", "queue.json")
CARDS_DIR = os.path.join(ROOT, "content", "cards")

DEFAULT_REPO = "paxsonloveschool-dotcom/claude-code-config"
DEFAULT_BRANCH = "main"
# Where committed cards live, relative to the repo root (for the raw url).
_CARDS_REPO_PATH = "social-suite/content/cards"

# Per-brand default look + footer label. Override with --theme / --brand-name.
BRAND_STYLE = {
    "hp": {"theme": "green", "brand_name": "HP Landscaping"},
    "restore": {"theme": "blue", "brand_name": "Restore"},
}


def raw_url(post_id: str, repo: str = DEFAULT_REPO, branch: str = DEFAULT_BRANCH) -> str:
    """Public URL a committed card will be served at."""
    return f"https://raw.githubusercontent.com/{repo}/{branch}/{_CARDS_REPO_PATH}/{post_id}.png"


def plan(
    queue: list[dict],
    *,
    brand: str | None = None,
    add_instagram: bool = False,
    repo: str = DEFAULT_REPO,
    branch: str = DEFAULT_BRANCH,
) -> list[dict]:
    """Decide which posts need a card. Returns a list of action dicts.

    A post is a candidate when it has no ``media_url`` yet and (matches ``brand``
    if given). Each action records the post id, the card url it will get, and
    whether ``"instagram"`` will be added to its platforms.
    """
    actions: list[dict] = []
    for post in queue:
        if brand is not None and (post.get("brand") or "default") != brand:
            continue
        if post.get("media_url"):
            continue  # already has media — leave it alone
        pid = post["id"]
        platforms = list(post.get("platforms") or [])
        will_add_ig = add_instagram and "instagram" not in platforms
        actions.append({
            "id": pid,
            "brand": post.get("brand") or "default",
            "card_url": raw_url(pid, repo, branch),
            "card_path": os.path.join(CARDS_DIR, f"{pid}.png"),
            "add_instagram": will_add_ig,
            "text": post.get("text", ""),
        })
    return actions


def apply(
    queue: list[dict],
    actions: list[dict],
    *,
    theme: str | None = None,
    brand_name: str | None = None,
    render_fn=None,
) -> int:
    """Render each action's card and update the queue in place. Returns count.

    ``render_fn(text, out_path, brand_name=, theme=)`` is injectable for tests;
    defaults to the real Pillow renderer (lazy-imported so this module loads
    without Pillow installed).
    """
    if render_fn is None:
        from services.media.card import render_card as render_fn  # lazy

    os.makedirs(CARDS_DIR, exist_ok=True)
    by_id = {p["id"]: p for p in queue}
    done = 0
    for act in actions:
        post = by_id[act["id"]]
        style = BRAND_STYLE.get(act["brand"], {})
        render_fn(
            post.get("text", ""),
            act["card_path"],
            brand_name=brand_name or style.get("brand_name"),
            theme=theme or style.get("theme", "green"),
        )
        post["media_url"] = act["card_url"]
        if act["add_instagram"]:
            platforms = list(post.get("platforms") or [])
            if "instagram" not in platforms:
                platforms.append("instagram")
            post["platforms"] = platforms
        # NOTE: status is deliberately left untouched (paused stays paused).
        done += 1
    return done


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Render cards for queued posts and wire them for Instagram.")
    parser.add_argument("--brand", default=None, help="Only this brand (e.g. hp).")
    parser.add_argument("--add-instagram", action="store_true", help="Add 'instagram' to each carded post's platforms.")
    parser.add_argument("--theme", default=None, help="Override card theme (green/blue/dark/light).")
    parser.add_argument("--brand-name", default=None, help="Override the footer brand label.")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="owner/repo for the raw card url.")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="branch for the raw card url.")
    parser.add_argument("--apply", action="store_true", help="Actually render + write (default: dry-run).")
    args = parser.parse_args(argv)

    with open(QUEUE_PATH, encoding="utf-8") as f:
        queue = json.load(f)

    actions = plan(queue, brand=args.brand, add_instagram=args.add_instagram,
                   repo=args.repo, branch=args.branch)
    if not actions:
        print("Nothing to do: no posts need a card (all have media or none match).")
        return 0

    print(f"{'APPLY' if args.apply else 'DRY-RUN'}: {len(actions)} post(s) would get a card:")
    for a in actions:
        ig = " +instagram" if a["add_instagram"] else ""
        print(f"  {a['id']} ({a['brand']}){ig} -> {a['card_url']}")

    if not args.apply:
        print("\nRe-run with --apply to render the cards and update the queue. "
              "Status is never changed — nothing will post.")
        return 0

    n = apply(queue, actions, theme=args.theme, brand_name=args.brand_name)
    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nRendered {n} card(s) into content/cards/ and updated the queue "
          "(statuses untouched — still paused).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
