"""FastAPI + HTMX/Jinja dashboard SHELL (read-only, Phase 0).

Routes:
  GET /                -> Clients grid: all brands + per-platform health dots.
  GET /brands/{id}     -> Brand detail: channels + health + settings (read-only).
  GET /calendar        -> Content calendar: every queued post per brand, with
                          schedule + live status (reads content/queue.json).
  GET /health          -> {"status": "ok"}.

Heavy bits are wired lazily; ``init_db()`` runs on startup so a fresh SQLite
file gets its schema. Run ``python -m portal.seed`` first for demo data.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .db import get_db, init_db
from .models import Brand, Channel, Platform

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# The poster's queue file (same one the GitHub-Actions runner reads). Override
# with QUEUE_PATH for tests / alternate locations.
_DEFAULT_QUEUE_PATH = Path(__file__).resolve().parent.parent / "content" / "queue.json"

# Tailwind dot colors per queue post status (calendar view).
QUEUE_STATUS_COLORS = {
    "pending": "bg-blue-500",
    "paused": "bg-gray-400",
    "sent": "bg-green-500",
    "failed": "bg-red-500",
    "skipped": "bg-yellow-400",
}

# Ordered list of the 6 platforms for the health-dot columns.
PLATFORM_ORDER: list[Platform] = [
    Platform.gbp,
    Platform.youtube,
    Platform.tiktok,
    Platform.instagram,
    Platform.facebook,
    Platform.x,
]

# Tailwind color classes per health status (used by templates).
HEALTH_COLORS = {
    "connected": "bg-green-500",
    "needs_attention": "bg-yellow-400",
    "expired": "bg-red-500",
    "disconnected": "bg-gray-300",
}

app = FastAPI(title="Content Distribution Portal", version="0.1.0")


@app.on_event("startup")
def _startup() -> None:
    init_db()


def _channels_by_platform(brand: Brand) -> dict[str, Channel]:
    return {ch.platform.value: ch for ch in brand.channels}


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/", response_class=HTMLResponse)
def clients_view(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    brands = (
        db.execute(
            select(Brand)
            .options(selectinload(Brand.channels))
            .order_by(Brand.name)
        )
        .scalars()
        .all()
    )
    rows = [
        {
            "brand": b,
            "channels": _channels_by_platform(b),
        }
        for b in brands
    ]
    return templates.TemplateResponse(
        request,
        "clients.html",
        {
            "rows": rows,
            "platforms": PLATFORM_ORDER,
            "health_colors": HEALTH_COLORS,
        },
    )


def _queue_path() -> Path:
    return Path(os.environ.get("QUEUE_PATH", str(_DEFAULT_QUEUE_PATH)))


def _load_queue_grouped() -> tuple[list[dict], dict[str, int]]:
    """Read queue.json → posts grouped by brand + a status tally.

    Read-only and dependency-free (plain JSON). Missing/empty file → no posts.
    Posts are sorted so unscheduled ("post now") items surface first, then by
    schedule time. Returns ``(brand_groups, totals)``.
    """
    path = _queue_path()
    if not path.exists():
        return [], {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8") or "[]")
    except (json.JSONDecodeError, OSError):
        return [], {}

    by_brand: dict[str, list[dict]] = {}
    totals: dict[str, int] = {}
    for p in raw:
        brand = p.get("brand") or "default"
        status = p.get("status", "pending")
        totals[status] = totals.get(status, 0) + 1
        by_brand.setdefault(brand, []).append({
            "id": p.get("id", ""),
            "text": (p.get("text") or "").replace("\n", " "),
            "platforms": p.get("platforms") or [],
            "schedule": p.get("schedule"),
            "status": status,
            "has_media": bool(p.get("media_url")),
        })

    groups: list[dict] = []
    for brand in sorted(by_brand):
        posts = sorted(by_brand[brand], key=lambda x: (x["schedule"] is not None, x["schedule"] or ""))
        groups.append({"brand": brand, "posts": posts, "count": len(posts)})
    return groups, totals


@app.get("/calendar", response_class=HTMLResponse)
def calendar_view(request: Request) -> HTMLResponse:
    groups, totals = _load_queue_grouped()
    return templates.TemplateResponse(
        request,
        "calendar.html",
        {
            "groups": groups,
            "totals": totals,
            "status_colors": QUEUE_STATUS_COLORS,
            "total_posts": sum(g["count"] for g in groups),
        },
    )


@app.get("/brands/{brand_id}", response_class=HTMLResponse)
def brand_detail(
    brand_id: int, request: Request, db: Session = Depends(get_db)
) -> HTMLResponse:
    brand = db.execute(
        select(Brand)
        .options(selectinload(Brand.channels))
        .where(Brand.id == brand_id)
    ).scalar_one_or_none()
    if brand is None:
        raise HTTPException(status_code=404, detail="Brand not found")
    return templates.TemplateResponse(
        request,
        "brand_detail.html",
        {
            "brand": brand,
            "platforms": PLATFORM_ORDER,
            "channels": _channels_by_platform(brand),
            "health_colors": HEALTH_COLORS,
        },
    )
