"""FastAPI + HTMX/Jinja dashboard SHELL (read-only, Phase 0).

Routes:
  GET /                -> Clients grid: all brands + per-platform health dots.
  GET /brands/{id}     -> Brand detail: channels + health + settings (read-only).
  GET /health          -> {"status": "ok"}.

Heavy bits are wired lazily; ``init_db()`` runs on startup so a fresh SQLite
file gets its schema. Run ``python -m portal.seed`` first for demo data.
"""

from __future__ import annotations

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
