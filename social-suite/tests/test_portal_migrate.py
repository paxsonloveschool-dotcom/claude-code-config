"""queue.json -> Post/PostTarget migration tests. No network."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _Skip(Exception):
    pass


def _require_sqlalchemy():
    try:
        import sqlalchemy  # noqa: F401
    except ImportError:
        raise _Skip("sqlalchemy not installed")


def _seeded_brand_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from portal.db import init_db
    from portal.models import Agency, Brand

    engine = create_engine("sqlite:///:memory:", future=True)
    init_db(bind=engine)
    db = sessionmaker(bind=engine, expire_on_commit=False)()
    agency = Agency(name="Acme")
    db.add(agency)
    db.flush()
    brand = Brand(agency_id=agency.id, name="HP Landscaping")
    db.add(brand)
    db.commit()
    return db, brand.id


_QUEUE = [
    {
        "id": "p1",
        "text": "mowing tip",
        "media_url": "https://x/a.jpg",
        "platforms": ["instagram", "facebook"],
        "schedule": None,
        "status": "pending",
        "error": None,
    },
    {
        "id": "p2",
        "text": "before after",
        "media_url": None,
        "platforms": ["instagram"],
        "schedule": "2026-06-19T14:00:00+00:00",
        "status": "pending",
        "error": None,
    },
    {
        "id": "p3",
        "text": "fb only",
        "media_url": None,
        "platforms": ["facebook"],
        "schedule": "2026-06-20T13:30:00+00:00",
        "status": "sent",
        "error": None,
    },
]


def _write_queue(items):
    d = tempfile.mkdtemp()
    path = str(Path(d) / "queue.json")
    Path(path).write_text(json.dumps(items))
    return path


def test_migrate_counts_posts_and_targets():
    _require_sqlalchemy()
    from sqlalchemy import func, select

    from portal.migrate_queue import migrate_queue
    from portal.models import MediaAsset, Post, PostTarget

    db, brand_id = _seeded_brand_session()
    created = migrate_queue(_write_queue(_QUEUE), db, brand_id=brand_id)

    assert created == 3
    assert db.execute(select(func.count(Post.id))).scalar_one() == 3
    # 2 + 1 + 1 platforms = 4 targets.
    assert db.execute(select(func.count(PostTarget.id))).scalar_one() == 4
    # one media asset (only p1 has media_url).
    assert db.execute(select(func.count(MediaAsset.id))).scalar_one() == 1


def test_migrate_maps_status_and_schedule():
    _require_sqlalchemy()
    from sqlalchemy import select

    from portal.migrate_queue import migrate_queue
    from portal.models import Post, PostStatus

    db, brand_id = _seeded_brand_session()
    migrate_queue(_write_queue(_QUEUE), db, brand_id=brand_id)

    p3 = db.execute(
        select(Post).where(Post.external_ref == "p3")
    ).scalar_one()
    assert p3.status is PostStatus.published  # "sent" -> published
    assert p3.scheduled_for is not None

    p1 = db.execute(
        select(Post).where(Post.external_ref == "p1")
    ).scalar_one()
    assert p1.status is PostStatus.scheduled  # "pending" -> scheduled


def test_migrate_is_idempotent_on_external_ref():
    _require_sqlalchemy()
    from sqlalchemy import func, select

    from portal.migrate_queue import migrate_queue
    from portal.models import Post

    db, brand_id = _seeded_brand_session()
    path = _write_queue(_QUEUE)
    migrate_queue(path, db, brand_id=brand_id)
    second = migrate_queue(path, db, brand_id=brand_id)

    assert second == 0
    assert db.execute(select(func.count(Post.id))).scalar_one() == 3


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
