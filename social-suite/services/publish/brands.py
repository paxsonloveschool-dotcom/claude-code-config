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
from dataclasses import dataclass, field

DEFAULT_BRANDS_FILE = "content/brands.json"
DEFAULT_BRAND = "default"


@dataclass
class BrandCreds:
    """The credentials a single brand needs to post across all platforms.

    Meta fields are top-level (backward-compatible with the original
    single-account shape). Each non-Meta platform carries its own optional
    sub-dict so a brand only needs creds for the platforms it actually posts to.

    Attributes:
        meta_access_token: Long-lived Meta Page token (FB + IG publishing).
        ig_user_id: Instagram Professional account id (for "instagram").
        fb_page_id: Facebook Page id (for "facebook").
        x: Optional ``{"access_token": ...}`` — X (Twitter) OAuth2 bearer token.
        tiktok: Optional TikTok creds. For unattended posting use the
            self-refreshing shape ``{"refresh_token", "client_key",
            "client_secret", "privacy_level"}`` (the runner mints a fresh
            ~24h access token each post). A static ``{"access_token"}`` also
            works for one-off/sandbox use. See ``TIKTOK_SETUP.md``.
        youtube: Optional ``{"access_token": ...}`` — YouTube OAuth token.
        gbp: Optional ``{"access_token", "account_id", "location_id"}`` for
            Google Business Profile.
    """

    meta_access_token: str = ""
    ig_user_id: str = ""
    fb_page_id: str = ""
    x: dict = field(default_factory=dict)
    tiktok: dict = field(default_factory=dict)
    youtube: dict = field(default_factory=dict)
    gbp: dict = field(default_factory=dict)


def _sub(raw: dict, key: str) -> dict:
    """Return a per-platform sub-dict, normalizing missing/null to ``{}``."""
    val = raw.get(key)
    if val is None:
        return {}
    if not isinstance(val, dict):
        raise ValueError(f"Brand {key!r} credentials must be an object.")
    return dict(val)


def _coerce(name: str, raw: dict) -> BrandCreds:
    """Build a ``BrandCreds`` from one brand's raw dict; unknown keys ignored."""
    if not isinstance(raw, dict):
        raise ValueError(
            f"Brand {name!r} credentials must be an object, got {type(raw).__name__}."
        )
    # ``.strip()`` defends against stray spaces/newlines a copied token can carry.
    return BrandCreds(
        meta_access_token=(raw.get("meta_access_token") or "").strip(),
        ig_user_id=(raw.get("ig_user_id") or "").strip(),
        fb_page_id=(raw.get("fb_page_id") or "").strip(),
        x=_sub(raw, "x"),
        tiktok=_sub(raw, "tiktok"),
        youtube=_sub(raw, "youtube"),
        gbp=_sub(raw, "gbp"),
    )


def _from_mapping(data: dict) -> dict[str, BrandCreds]:
    if not isinstance(data, dict):
        raise ValueError("Brands map must be a JSON object of {name: creds}.")
    return {name: _coerce(name, creds) for name, creds in data.items()}


# Flat per-brand env vars: BRAND_<NAME>_<FIELD>. No JSON to mangle — each secret
# is a single pasted value. Far more robust than hand-edited BRANDS_JSON.
#   BRAND_HP_META_ACCESS_TOKEN, BRAND_HP_FB_PAGE_ID, BRAND_HP_IG_USER_ID, ...
#   BRAND_HP_TIKTOK_REFRESH_TOKEN, BRAND_HP_TIKTOK_CLIENT_KEY, ...
# Each field maps to a path into the brand's creds dict: a 1-tuple is a top-level
# Meta field; a 2-tuple lands in a per-platform sub-dict (e.g. ("tiktok", ...)).
_FLAT_PREFIX = "BRAND_"
_FLAT_FIELDS = {
    "META_ACCESS_TOKEN": ("meta_access_token",),
    "FB_PAGE_ID": ("fb_page_id",),
    "IG_USER_ID": ("ig_user_id",),
    "TIKTOK_REFRESH_TOKEN": ("tiktok", "refresh_token"),
    "TIKTOK_CLIENT_KEY": ("tiktok", "client_key"),
    "TIKTOK_CLIENT_SECRET": ("tiktok", "client_secret"),
    "TIKTOK_PRIVACY_LEVEL": ("tiktok", "privacy_level"),
    "TIKTOK_ACCESS_TOKEN": ("tiktok", "access_token"),
    "TIKTOK_OPEN_ID": ("tiktok", "open_id"),
}


def _from_flat_env() -> dict[str, BrandCreds]:
    """Build the brand map from ``BRAND_<NAME>_<FIELD>`` env vars, or ``{}``.

    Returns an empty dict when no such vars are set, so callers can treat it as
    "not configured this way" and fall through to the other sources.
    """
    raw: dict[str, dict] = {}
    # Longest suffix first so a field that ends in a shorter field's name can
    # never be misclassified (e.g. ``..._TIKTOK_ACCESS_TOKEN`` must not match the
    # bare ``..._ACCESS_TOKEN`` of a future field).
    suffixes = sorted(_FLAT_FIELDS, key=len, reverse=True)
    for key, value in os.environ.items():
        if not key.startswith(_FLAT_PREFIX):
            continue
        for suffix in suffixes:
            if key.endswith("_" + suffix):
                name = key[len(_FLAT_PREFIX): -(len(suffix) + 1)].lower()
                if name:
                    path = _FLAT_FIELDS[suffix]
                    target = raw.setdefault(name, {})
                    for part in path[:-1]:
                        target = target.setdefault(part, {})
                    # Sub-dict values aren't stripped by ``_coerce`` (only the
                    # top-level Meta fields are), so trim them here.
                    target[path[-1]] = value.strip() if len(path) > 1 else value
                break
    return _from_mapping(raw)


def load_brands() -> dict[str, BrandCreds]:
    """Load the brand -> credentials map using the source-priority chain.

    Source priority:
        1. Flat ``BRAND_<NAME>_<FIELD>`` env vars (one secret per value — no JSON
           to mangle). Checked first so a leftover malformed ``BRANDS_JSON`` can't
           block this simpler, more robust path.
        2. ``BRANDS_JSON`` (one secret holding every brand's creds).
        3. ``BRANDS_FILE`` (local JSON file).
        4. Legacy single ``"default"`` brand from META_ACCESS_TOKEN/IG/FB.

    Returns:
        A dict mapping brand name to ``BrandCreds``. Always returns at least the
        ``"default"`` brand (from legacy env vars) when nothing else is set, so
        the single-account path keeps working.

    Raises:
        ValueError: If ``BRANDS_JSON`` / ``BRANDS_FILE`` holds invalid JSON or an
            unexpected shape.
    """
    flat = _from_flat_env()
    if flat:
        return flat

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
