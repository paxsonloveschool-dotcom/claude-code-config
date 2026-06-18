"""Engine / session setup.

Dev defaults to a local SQLite file so the portal runs with zero external
services (CI/sandbox). Point ``DATABASE_URL`` at Postgres in prod, e.g.
``postgresql+psycopg://user:pass@host/db``.
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

DATABASE_URL = os.environ.get("DATABASE_URL") or "sqlite:///./portal.db"

# SQLite needs check_same_thread=False to be used across FastAPI threads.
_connect_args = (
    {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db(bind=None) -> None:
    """Create all tables. Pass ``bind`` to target a custom engine (e.g. tests)."""
    Base.metadata.create_all(bind or engine)


def get_db():
    """FastAPI dependency yielding a session, always closed after the request."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
