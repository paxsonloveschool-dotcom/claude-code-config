"""Portal model tests — in-memory SQLite, relationships, UNIQUE constraint.

No network. Skips cleanly if sqlalchemy is not installed.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _Skip(Exception):
    pass


def _require_sqlalchemy():
    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        raise _Skip("sqlalchemy not installed")


def _fresh_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from portal.db import init_db

    engine = create_engine("sqlite:///:memory:", future=True)
    init_db(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_full_graph_inserts_and_relationships_load():
    _require_sqlalchemy()
    from portal.models import (
        Agency,
        Brand,
        Channel,
        MediaAsset,
        MediaKind,
        Platform,
        Post,
        PostTarget,
    )

    db = _fresh_session()
    agency = Agency(name="Acme")
    db.add(agency)
    db.flush()

    brand = Brand(agency_id=agency.id, name="HP Landscaping")
    db.add(brand)
    db.flush()

    channel = Channel(brand_id=brand.id, platform=Platform.facebook)
    db.add(channel)
    db.flush()

    asset = MediaAsset(
        brand_id=brand.id, kind=MediaKind.image, public_url="https://x/a.jpg"
    )
    db.add(asset)
    db.flush()

    post = Post(brand_id=brand.id, base_text="hello")
    db.add(post)
    db.flush()

    target = PostTarget(
        post_id=post.id, channel_id=channel.id, media_asset_id=asset.id
    )
    db.add(target)
    db.commit()

    # Relationships load both directions.
    assert agency.brands[0].name == "HP Landscaping"
    assert brand.agency.name == "Acme"
    assert brand.channels[0].platform is Platform.facebook
    assert post.targets[0].channel.platform is Platform.facebook
    assert target.media_asset.public_url == "https://x/a.jpg"
    assert channel.post_targets[0].post.base_text == "hello"
    assert brand.media_assets[0].id == asset.id


def test_unique_brand_platform_raises_on_duplicate():
    _require_sqlalchemy()
    from sqlalchemy.exc import IntegrityError

    from portal.models import Agency, Brand, Channel, Platform

    db = _fresh_session()
    agency = Agency(name="Acme")
    db.add(agency)
    db.flush()
    brand = Brand(agency_id=agency.id, name="B")
    db.add(brand)
    db.flush()

    db.add(Channel(brand_id=brand.id, platform=Platform.instagram))
    db.commit()

    db.add(Channel(brand_id=brand.id, platform=Platform.instagram))
    raised = False
    try:
        db.commit()
    except IntegrityError:
        raised = True
        db.rollback()
    assert raised, "duplicate (brand_id, platform) should violate UNIQUE"


def test_oauth_token_stores_bytes_not_plaintext():
    _require_sqlalchemy()
    from portal.models import Agency, Brand, Channel, OAuthToken, Platform

    db = _fresh_session()
    agency = Agency(name="Acme")
    db.add(agency)
    db.flush()
    brand = Brand(agency_id=agency.id, name="B")
    db.add(brand)
    db.flush()
    channel = Channel(brand_id=brand.id, platform=Platform.x)
    db.add(channel)
    db.flush()

    tok = OAuthToken(channel_id=channel.id, access_token_enc=b"\x00\x01ciphertext")
    db.add(tok)
    db.commit()

    assert isinstance(channel.oauth_token.access_token_enc, (bytes, bytearray))
    assert channel.oauth_token.refresh_token_enc is None


def _run():
    passed = skipped = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS {name}")
                passed += 1
            except _Skip as e:
                print(f"  SKIP {name} ({e})")
                skipped += 1
    print(f"\n{passed} passed, {skipped} skipped.")
    return passed, skipped


if __name__ == "__main__":
    _run()
