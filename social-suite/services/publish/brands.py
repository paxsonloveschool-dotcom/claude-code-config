"""Per-brand Meta credentials — turn the single-account poster into multi-brand.

Each brand (e.g. HP Landscaping, Restore) posts to its OWN Instagram + Facebook
using its OWN Meta credentials. This module loads a brand -> credentials map so
``run_due`` can route each queued post to the right account.

Source priority (first that resolves wins):
    1. Env var ``BRANDS_JSON`` — a JSON object of all brands (used in CI; one
       GitHub Secret holds every brand's creds).
    2. Local file ``BRANDS_FILE`` (default ``content/brands.json``) if it exists.
    3. Fallback: a single ``"default"`` brand built from the legacy env vars
       ``META_ACCESS_TOKEN`` / ``IG_USER_ID`` / ``FB_PAGE_ID`` (backward compat).

Map shape::

    {"hp":      {"meta_access_token": "...", "ig_user_id": "...", "fb_page_id": "..."},
     "restore": {"meta_access_token": "...", "ig_user_id": "...", "fb_page_id": "..."}}

This module NEVER writes tokens to disk; the real ``content/brands.json`` is
gitignored and only ``content/brands.example.json`` ships. Pure stdlib, no
network — imports cleanly with no third-party deps.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

DEFAULT_BRANDS_FILE = "content/brands.json"
DEFAULT_BRAND = "default"


@dataclass
class BrandCreds:
    """The three Meta values a single brand needs to post.

    Attributes:
        meta_access_token: Long-lived Meta Page token (FB + IG publishing).
        ig_user_id: Instagram Professional account id (for "instagram").
        fb_page_id: Facebook Page id (for "facebook").
    """

    meta_access_token: str = ""
    ig_user_id: str = ""
    fb_page_id: str = ""


def _coerce(name: str, raw: dict) -> BrandCreds:
    """Build a ``BrandCreds`` from one brand's raw dict; unknown keys ignored."""
    if not isinstance(raw, dict):
        raise ValueError(
            f"Brand {name!r} credentials must be an object, got {type(raw).__name__}."
        )
    return BrandCreds(
        meta_access_token=raw.get("meta_access_token", "") or "",
        ig_user_id=raw.get("ig_user_id", "") or "",
        fb_page_id=raw.get("fb_page_id", "") or "",
    )


def _from_mapping(data: dict) -> dict[str, BrandCreds]:
    if not isinstance(data, dict):
        raise ValueError("Brands map must be a JSON object of {name: creds}.")
    return {name: _coerce(name, creds) for name, creds in data.items()}


def load_brands() -> dict[str, BrandCreds]:
    """Load the brand -> credentials map using the source-priority chain.

    Returns:
        A dict mapping brand name to ``BrandCreds``. Always returns at least the
        ``"default"`` brand (from legacy env vars) when nothing else is set, so
        the single-account path keeps working.

    Raises:
        ValueError: If ``BRANDS_JSON`` / ``BRANDS_FILE`` holds invalid JSON or an
            unexpected shape.
    """
    raw_json = os.environ.get("BRANDS_JSON", "").strip()
    if raw_json:
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"BRANDS_JSON is not valid JSON: {e}") from e
        return _from_mapping(data)

    path = os.environ.get("BRANDS_FILE", DEFAULT_BRANDS_FILE)
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            text = f.read().strip()
        if text:
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path} is not valid JSON: {e}") from e
            return _from_mapping(data)

    # Fallback: single "default" brand from the legacy env vars.
    return {
        DEFAULT_BRAND: BrandCreds(
            meta_access_token=os.environ.get("META_ACCESS_TOKEN", ""),
            ig_user_id=os.environ.get("IG_USER_ID", ""),
            fb_page_id=os.environ.get("FB_PAGE_ID", ""),
        )
    }


def get_brand(
    name: str | None, brands: dict[str, BrandCreds] | None = None
) -> BrandCreds:
    """Return the ``BrandCreds`` for ``name`` (default ``"default"``).

    Args:
        name: Brand key to look up; ``None`` resolves to ``"default"``.
        brands: Optional preloaded map (avoids reloading per-post). When omitted,
            ``load_brands()`` is called.

    Raises:
        KeyError: If the requested brand is not in the map — with a clear message
            listing the brands that ARE available.
    """
    name = name or DEFAULT_BRAND
    brands = brands if brands is not None else load_brands()
    if name not in brands:
        available = ", ".join(sorted(brands)) or "(none)"
        raise KeyError(
            f"Unknown brand {name!r}. Available brands: {available}. "
            "Add it to BRANDS_JSON / content/brands.json."
        )
    return brands[name]
