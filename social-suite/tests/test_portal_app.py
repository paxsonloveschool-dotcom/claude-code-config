"""FastAPI dashboard tests against an in-memory seeded DB. No network.

Uses Starlette's TestClient when available; otherwise falls back to calling the
route functions directly so the suite still passes without httpx.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _Skip(Exception):
    pass


def _require_stack():
    try:
        import fastapi  # noqa: F401
        import sqlalchemy  # noqa: F401
    except ImportError as e:
        raise _Skip(f"{e.name} not installed")


def _seeded_sessionmaker():
    """In-memory SQLite shared across connections (StaticPool) + demo data."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from portal.db import init_db
    from portal.seed import seed

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    init_db(bind=engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
    return SessionLocal


def _has_testclient():
    try:
        import httpx  # noqa: F401
        from starlette.testclient import TestClient  # noqa: F401

        return True
    except ImportError:
        return False


def test_health_and_index_via_testclient():
    _require_stack()
    if not _has_testclient():
        raise _Skip("httpx/TestClient unavailable — see direct-call test")
    from starlette.testclient import TestClient

    from portal import app as app_module
    from portal.db import get_db

    SessionLocal = _seeded_sessionmaker()

    def _override():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app_module.app.dependency_overrides[get_db] = _override
    # Avoid the startup hook touching the real default engine.
    app_module.app.router.on_startup.clear()
    try:
        client = TestClient(app_module.app)

        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

        r = client.get("/")
        assert r.status_code == 200
        assert "HP Landscaping" in r.text
        assert "Restore" in r.text

        # Brand detail renders settings for an existing brand.
        r = client.get("/brands/1")
        assert r.status_code == 200
        r404 = client.get("/brands/99999")
        assert r404.status_code == 404
    finally:
        app_module.app.dependency_overrides.clear()


def test_index_via_direct_route_call():
    """Network-free fallback: invoke the route function directly."""
    _require_stack()
    from starlette.requests import Request

    from portal.app import clients_view, health

    SessionLocal = _seeded_sessionmaker()
    db = SessionLocal()
    try:
        assert health().status_code == 200

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
        }
        request = Request(scope)
        resp = clients_view(request, db=db)
        body = resp.body.decode()
        assert resp.status_code == 200
        assert "HP Landscaping" in body
        assert "Restore" in body
    finally:
        db.close()


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
