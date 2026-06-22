"""Tests for the per-brand credential loader (env JSON, file, fallback). No network."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.publish.brands import (  # noqa: E402
    BrandCreds,
    get_brand,
    load_brands,
)

_ENV_KEYS = (
    "BRANDS_JSON",
    "BRANDS_FILE",
    "META_ACCESS_TOKEN",
    "IG_USER_ID",
    "FB_PAGE_ID",
)


def _clear_env():
    for k in _ENV_KEYS:
        os.environ.pop(k, None)
    # Also clear any flat BRAND_* vars so they never leak between tests.
    for k in [k for k in os.environ if k.startswith("BRAND_")]:
        os.environ.pop(k, None)


def test_brands_json_env_takes_priority():
    _clear_env()
    os.environ["BRANDS_JSON"] = (
        '{"hp": {"meta_access_token": "hpT", "ig_user_id": "hpIG", "fb_page_id": "hpFB"},'
        ' "restore": {"meta_access_token": "rT", "ig_user_id": "rIG", "fb_page_id": "rFB"}}'
    )
    # Legacy env present too — must be IGNORED in favor of BRANDS_JSON.
    os.environ["META_ACCESS_TOKEN"] = "legacy"
    try:
        brands = load_brands()
    finally:
        _clear_env()

    assert set(brands) == {"hp", "restore"}
    assert brands["hp"] == BrandCreds("hpT", "hpIG", "hpFB")
    assert brands["restore"].fb_page_id == "rFB"


def test_brands_file_loaded_when_no_env_json():
    _clear_env()
    with tempfile.TemporaryDirectory() as d:
        path = str(Path(d) / "brands.json")
        Path(path).write_text(
            '{"restore": {"meta_access_token": "fT", "ig_user_id": "fIG", "fb_page_id": "fFB"}}'
        )
        os.environ["BRANDS_FILE"] = path
        try:
            brands = load_brands()
        finally:
            _clear_env()

    assert set(brands) == {"restore"}
    assert brands["restore"] == BrandCreds("fT", "fIG", "fFB")


def test_single_env_fallback_builds_default_brand():
    _clear_env()
    os.environ["META_ACCESS_TOKEN"] = "tok"
    os.environ["IG_USER_ID"] = "ig9"
    os.environ["FB_PAGE_ID"] = "fb9"
    # BRANDS_FILE points at a path that does NOT exist -> fall through to env.
    os.environ["BRANDS_FILE"] = str(Path(tempfile.gettempdir()) / "definitely-missing.json")
    try:
        brands = load_brands()
        creds = get_brand(None, brands)  # None -> "default"
    finally:
        _clear_env()

    assert set(brands) == {"default"}
    assert creds == BrandCreds("tok", "ig9", "fb9")


def test_get_brand_missing_raises_keyerror_listing_available():
    _clear_env()
    os.environ["BRANDS_JSON"] = (
        '{"hp": {"meta_access_token": "t", "ig_user_id": "i", "fb_page_id": "f"}}'
    )
    try:
        brands = load_brands()
        raised = None
        try:
            get_brand("restore", brands)
        except KeyError as e:
            raised = str(e)
    finally:
        _clear_env()

    assert raised is not None
    assert "restore" in raised
    assert "hp" in raised  # error lists what IS available


def test_invalid_brands_json_raises_valueerror():
    _clear_env()
    os.environ["BRANDS_JSON"] = "{not valid json"
    try:
        err = None
        try:
            load_brands()
        except ValueError as e:
            err = str(e)
    finally:
        _clear_env()
    assert err is not None
    assert "BRANDS_JSON" in err


def test_get_brand_default_name_when_none():
    _clear_env()
    os.environ["META_ACCESS_TOKEN"] = "tok"
    try:
        # No explicit map -> get_brand loads it itself and resolves "default".
        creds = get_brand(None)
    finally:
        _clear_env()
    assert creds.meta_access_token == "tok"


def test_flat_brand_env_vars_build_brands():
    _clear_env()
    os.environ["BRAND_HP_META_ACCESS_TOKEN"] = "hpTOK"
    os.environ["BRAND_HP_FB_PAGE_ID"] = "hpFB"
    os.environ["BRAND_RESTORE_META_ACCESS_TOKEN"] = "rTOK"
    os.environ["BRAND_RESTORE_FB_PAGE_ID"] = "rFB"
    try:
        brands = load_brands()
    finally:
        _clear_env()
    assert set(brands) == {"hp", "restore"}
    assert brands["hp"].meta_access_token == "hpTOK"
    assert brands["hp"].fb_page_id == "hpFB"
    assert brands["restore"].meta_access_token == "rTOK"


def test_flat_env_takes_priority_over_brands_json():
    _clear_env()
    os.environ["BRAND_HP_META_ACCESS_TOKEN"] = "flatTOK"
    os.environ["BRAND_HP_FB_PAGE_ID"] = "flatFB"
    # A (even malformed) BRANDS_JSON must be ignored when flat vars are present.
    os.environ["BRANDS_JSON"] = "{not valid json"
    try:
        brands = load_brands()
    finally:
        _clear_env()
    assert set(brands) == {"hp"}
    assert brands["hp"].meta_access_token == "flatTOK"


def test_flat_env_strips_whitespace_and_newlines():
    _clear_env()
    # A copied token often carries a trailing newline/spaces — must be stripped.
    os.environ["BRAND_HP_META_ACCESS_TOKEN"] = "  hpTOK\n"
    os.environ["BRAND_HP_FB_PAGE_ID"] = "hpFB\n"
    try:
        brands = load_brands()
    finally:
        _clear_env()
    assert brands["hp"].meta_access_token == "hpTOK"
    assert brands["hp"].fb_page_id == "hpFB"


def test_flat_env_builds_tiktok_subdict():
    _clear_env()
    # Same flat-secret pattern as Meta, extended to TikTok's sub-dict fields.
    os.environ["BRAND_HP_META_ACCESS_TOKEN"] = "hpTOK"
    os.environ["BRAND_HP_TIKTOK_REFRESH_TOKEN"] = "  hpRFT\n"
    os.environ["BRAND_HP_TIKTOK_CLIENT_KEY"] = "CK"
    os.environ["BRAND_HP_TIKTOK_CLIENT_SECRET"] = "CS"
    os.environ["BRAND_HP_TIKTOK_PRIVACY_LEVEL"] = "PUBLIC_TO_EVERYONE"
    os.environ["BRAND_RESTORE_TIKTOK_REFRESH_TOKEN"] = "rRFT"
    os.environ["BRAND_RESTORE_TIKTOK_CLIENT_KEY"] = "CK"
    os.environ["BRAND_RESTORE_TIKTOK_CLIENT_SECRET"] = "CS"
    try:
        brands = load_brands()
    finally:
        _clear_env()

    assert set(brands) == {"hp", "restore"}
    hp = brands["hp"]
    assert hp.meta_access_token == "hpTOK"
    # Whitespace/newline trimmed on the sub-dict value too.
    assert hp.tiktok == {
        "refresh_token": "hpRFT",
        "client_key": "CK",
        "client_secret": "CS",
        "privacy_level": "PUBLIC_TO_EVERYONE",
    }
    assert brands["restore"].tiktok["refresh_token"] == "rRFT"
    assert brands["restore"].meta_access_token == ""  # tiktok-only brand is fine


def _run():
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  PASS {name}")
            passed += 1
    print(f"\n{passed} tests passed.")


if __name__ == "__main__":
    _run()
