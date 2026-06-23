# Content Distribution Portal — Phase 0

The read-only shell of the multi-brand content distribution dashboard
(see [`../PORTAL_ARCHITECTURE.md`](../PORTAL_ARCHITECTURE.md)). One agency →
many client brands → 6 platforms (GBP, YouTube, TikTok, Instagram, Facebook, X).

Phase 0 delivers: the SQLAlchemy 2.0 data model, engine/session setup, token
encryption helpers, a FastAPI + HTMX + Jinja dashboard (Clients grid + Brand
detail), a demo seeder, and a `queue.json → Post/PostTarget` migrator.

## Stack

FastAPI · SQLAlchemy 2.x · Jinja2 · HTMX + Tailwind (CDN, no build step).
**SQLite** for dev (zero external services), Postgres in prod via `DATABASE_URL`.

## Run it

```bash
pip install fastapi uvicorn sqlalchemy jinja2 python-multipart
# (cryptography is only needed for OAuth token encryption, not the dashboard)

cd social-suite
python -m portal.seed                       # create portal.db + demo data
uvicorn portal.app:app --reload             # http://localhost:8000
```

Open <http://localhost:8000>:

- `/` — Clients grid with per-platform channel-health dots
  (green=connected, yellow=needs attention, red=expired, grey=disconnected).
- `/brands/{id}` — Brand detail: channels + health + read-only settings.
- `/health` — `{"status": "ok"}`.

## Configuration

| Env var | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./portal.db` | Point at Postgres in prod, e.g. `postgresql+psycopg://user:pass@host/db`. |
| `TOKEN_ENC_KEY` | _(unset)_ | Fernet key for encrypting OAuth tokens at rest. Only needed once channel OAuth (Phase 1) lands. |

Generate a token-encryption key:

```python
from portal.crypto import generate_key
print(generate_key())   # store as TOKEN_ENC_KEY in your secret store
```

## SQLite-dev vs Postgres-prod

`portal/db.py` reads `DATABASE_URL` and falls back to a local SQLite file so the
app and tests run with no external services. The same code targets Postgres in
prod by setting `DATABASE_URL`; SQLite-specific `check_same_thread` is applied
only for the `sqlite://` driver. (Alembic migrations arrive in Phase 0+/1; for
now `init_db()` / `Base.metadata.create_all()` builds the schema.)

## Migrate the old queue

```python
from portal.db import SessionLocal
from portal.migrate_queue import migrate_queue

db = SessionLocal()
n = migrate_queue("content/queue.json", db, brand_id=1)
print(f"migrated {n} posts")
```

## Tests

No network required. From `social-suite/`:

```bash
python3 tests/test_portal_models.py
python3 tests/test_portal_crypto.py
python3 tests/test_portal_migrate.py
python3 tests/test_portal_app.py
```

Tests skip-with-message (rather than error) if `sqlalchemy` / `fastapi` /
`cryptography` / `httpx` are not installed in the environment.
