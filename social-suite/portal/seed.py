"""Seed a demo agency + 2 brands with channels in varied health states.

Idempotent: re-running won't duplicate the agency/brands/channels (matched by
name / (brand, platform)). Run with::

    python -m portal.seed
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SessionLocal, init_db
from .models import (
    Agency,
    Brand,
    BrandStatus,
    Channel,
    HealthStatus,
    Platform,
)

AGENCY_NAME = "Demo Agency"

# brand_name -> settings + channel health map
_BRANDS = {
    "HP Landscaping": {
        "settings": dict(
            timezone="America/New_York",
            default_schedule="weekdays 09:00",
            brand_voice="Friendly, practical lawn-care expert. Short, helpful tips.",
            default_hashtags="#lawncare #landscaping",
            gbp_cta_default="CALL",
            status=BrandStatus.active,
        ),
        "channels": {
            Platform.facebook: (HealthStatus.connected, True, "page_111"),
            Platform.instagram: (HealthStatus.connected, True, "ig_222"),
            Platform.x: (HealthStatus.needs_attention, True, "x_333"),
            Platform.gbp: (HealthStatus.disconnected, False, None),
            Platform.youtube: (HealthStatus.expired, True, "yt_444"),
        },
    },
    "Restore": {
        "settings": dict(
            timezone="America/Chicago",
            default_schedule="Mon/Wed/Fri 14:00",
            brand_voice="Calm, restorative wellness brand. Inspirational tone.",
            default_hashtags="#restore #wellness",
            gbp_cta_default="LEARN_MORE",
            status=BrandStatus.active,
        ),
        "channels": {
            Platform.instagram: (HealthStatus.connected, True, "ig_555"),
            Platform.facebook: (HealthStatus.needs_attention, True, "page_666"),
            Platform.tiktok: (HealthStatus.connected, True, "tt_777"),
            Platform.x: (HealthStatus.disconnected, False, None),
        },
    },
}


def _get_or_create_agency(db: Session) -> Agency:
    agency = db.execute(
        select(Agency).where(Agency.name == AGENCY_NAME)
    ).scalar_one_or_none()
    if agency is None:
        agency = Agency(name=AGENCY_NAME)
        db.add(agency)
        db.flush()
    return agency


def _get_or_create_brand(db: Session, agency: Agency, name: str, settings: dict) -> Brand:
    brand = db.execute(
        select(Brand).where(Brand.agency_id == agency.id, Brand.name == name)
    ).scalar_one_or_none()
    if brand is None:
        brand = Brand(agency_id=agency.id, name=name, **settings)
        db.add(brand)
        db.flush()
    return brand


def _ensure_channel(
    db: Session,
    brand: Brand,
    platform: Platform,
    health: HealthStatus,
    enabled: bool,
    external_id: str | None,
) -> None:
    existing = db.execute(
        select(Channel).where(
            Channel.brand_id == brand.id, Channel.platform == platform
        )
    ).scalar_one_or_none()
    if existing is None:
        db.add(
            Channel(
                brand_id=brand.id,
                platform=platform,
                health_status=health,
                enabled=enabled,
                external_account_id=external_id,
            )
        )


def seed(db: Session) -> Agency:
    """Create demo data idempotently. Returns the demo Agency."""
    agency = _get_or_create_agency(db)
    for name, spec in _BRANDS.items():
        brand = _get_or_create_brand(db, agency, name, spec["settings"])
        for platform, (health, enabled, ext) in spec["channels"].items():
            _ensure_channel(db, brand, platform, health, enabled, ext)
    db.commit()
    return agency


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        agency = seed(db)
        n_brands = len(agency.brands)
        n_channels = sum(len(b.channels) for b in agency.brands)
        print(
            f"Seeded agency '{agency.name}' with {n_brands} brands "
            f"and {n_channels} channels."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
