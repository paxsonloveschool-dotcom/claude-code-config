"""SQLAlchemy 2.0 declarative models — Phase 0 multi-tenant data model.

    Agency --< Brand --< Channel --< PostTarget >-- Post >-- MediaAsset
                           |
                       OAuthToken (1:1 per channel, encrypted at rest)

Enums (``Platform`` + the various status enums) are plain ``str``-valued Python
enums so they serialize cleanly and read naturally in templates. The UNIQUE
constraint on ``Channel(brand_id, platform)`` enforces one channel per platform
per brand. Tokens are NEVER stored in plaintext columns — see
``OAuthToken.access_token_enc`` and ``portal.crypto``.
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------- #
# Enums                                                                        #
# --------------------------------------------------------------------------- #
class Platform(str, enum.Enum):
    gbp = "gbp"            # Google Business Profile
    youtube = "youtube"
    tiktok = "tiktok"
    instagram = "instagram"
    facebook = "facebook"
    x = "x"


class HealthStatus(str, enum.Enum):
    """Channel token/connection health (flipped by the nightly refresh job)."""

    connected = "connected"      # green
    needs_attention = "needs_attention"  # yellow (expiring soon / warnings)
    expired = "expired"          # red (token expired / refresh failed)
    disconnected = "disconnected"  # grey (never connected)


class BrandStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    archived = "archived"


class PostStatus(str, enum.Enum):
    draft = "draft"
    scheduled = "scheduled"
    publishing = "publishing"
    published = "published"
    failed = "failed"


class PostTargetStatus(str, enum.Enum):
    pending = "pending"
    publishing = "publishing"
    published = "published"
    failed = "failed"
    skipped = "skipped"


class PostSource(str, enum.Enum):
    manual = "manual"
    pipeline = "pipeline"


class MediaKind(str, enum.Enum):
    image = "image"
    video = "video"


# --------------------------------------------------------------------------- #
# Models                                                                       #
# --------------------------------------------------------------------------- #
class Agency(Base):
    """Tenant root. App-level platform secrets live in the host secret store,
    NOT here — this row is just the tenant anchor."""

    __tablename__ = "agency"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    brands: Mapped[list["Brand"]] = relationship(
        back_populates="agency",
        cascade="all, delete-orphan",
    )


class Brand(Base):
    """A client brand. Settings here feed the copywriter / scheduler."""

    __tablename__ = "brand"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agency_id: Mapped[int] = mapped_column(
        ForeignKey("agency.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="America/New_York")
    default_schedule: Mapped[str | None] = mapped_column(String(200), default=None)
    brand_voice: Mapped[str | None] = mapped_column(Text, default=None)
    default_hashtags: Mapped[str | None] = mapped_column(Text, default=None)
    gbp_cta_default: Mapped[str | None] = mapped_column(String(200), default=None)
    status: Mapped[BrandStatus] = mapped_column(
        SAEnum(BrandStatus), default=BrandStatus.active
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    agency: Mapped["Agency"] = relationship(back_populates="brands")
    channels: Mapped[list["Channel"]] = relationship(
        back_populates="brand",
        cascade="all, delete-orphan",
        order_by="Channel.platform",
    )
    posts: Mapped[list["Post"]] = relationship(
        back_populates="brand",
        cascade="all, delete-orphan",
    )
    media_assets: Mapped[list["MediaAsset"]] = relationship(
        back_populates="brand",
        cascade="all, delete-orphan",
    )


class Channel(Base):
    """One row per platform per brand. UNIQUE(brand_id, platform)."""

    __tablename__ = "channel"
    __table_args__ = (
        UniqueConstraint("brand_id", "platform", name="uq_channel_brand_platform"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brand.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[Platform] = mapped_column(SAEnum(Platform), nullable=False)
    external_account_id: Mapped[str | None] = mapped_column(String(200), default=None)
    health_status: Mapped[HealthStatus] = mapped_column(
        SAEnum(HealthStatus), default=HealthStatus.disconnected
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    brand: Mapped["Brand"] = relationship(back_populates="channels")
    oauth_token: Mapped["OAuthToken | None"] = relationship(
        back_populates="channel",
        cascade="all, delete-orphan",
        uselist=False,
    )
    post_targets: Mapped[list["PostTarget"]] = relationship(
        back_populates="channel",
        cascade="all, delete-orphan",
    )


class OAuthToken(Base):
    """Per-channel OAuth token, 1:1 with Channel, ENCRYPTED AT REST.

    ``access_token_enc`` / ``refresh_token_enc`` hold Fernet ciphertext produced
    by ``portal.crypto.encrypt`` (key from secret store ``TOKEN_ENC_KEY``). Raw
    tokens are decrypted only in the poster at send time — they are never stored
    or logged in plaintext.
    """

    __tablename__ = "oauth_token"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channel.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # 1:1 with Channel
    )
    access_token_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    refresh_token_enc: Mapped[bytes | None] = mapped_column(
        LargeBinary, default=None
    )
    scopes: Mapped[str | None] = mapped_column(Text, default=None)
    access_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=None
    )
    refresh_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    channel: Mapped["Channel"] = relationship(back_populates="oauth_token")


class MediaAsset(Base):
    """Stored media. Several platforms (IG/FB/GBP/TikTok-pull) fetch the asset
    server-side from ``public_url``."""

    __tablename__ = "media_asset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brand.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[MediaKind] = mapped_column(SAEnum(MediaKind), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(500), default=None)
    public_url: Mapped[str | None] = mapped_column(String(1000), default=None)
    width: Mapped[int | None] = mapped_column(Integer, default=None)
    height: Mapped[int | None] = mapped_column(Integer, default=None)
    # Comma/JSON-encoded list of generated variant descriptors (9:16, 1:1, 16:9).
    variants: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    brand: Mapped["Brand"] = relationship(back_populates="media_assets")
    post_targets: Mapped[list["PostTarget"]] = relationship(
        back_populates="media_asset"
    )


class Post(Base):
    """Shared content fanned out across channels via PostTarget."""

    __tablename__ = "post"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brand.id", ondelete="CASCADE"), nullable=False
    )
    base_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    base_hashtags: Mapped[str | None] = mapped_column(Text, default=None)
    # Comma-separated MediaAsset ids (lightweight; a join table comes later).
    media_asset_ids: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[PostStatus] = mapped_column(
        SAEnum(PostStatus), default=PostStatus.draft
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    source: Mapped[PostSource] = mapped_column(
        SAEnum(PostSource), default=PostSource.manual
    )
    # Stable external id from the source system (e.g. queue.json post id).
    external_ref: Mapped[str | None] = mapped_column(String(200), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    brand: Mapped["Brand"] = relationship(back_populates="posts")
    targets: Mapped[list["PostTarget"]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
    )


class PostTarget(Base):
    """Fan-out join: one Post -> N Channels, with per-platform overrides."""

    __tablename__ = "post_target"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("post.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channel.id", ondelete="CASCADE"), nullable=False
    )
    media_asset_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_asset.id", ondelete="SET NULL"), default=None
    )
    override_text: Mapped[str | None] = mapped_column(Text, default=None)
    # JSON-encoded per-platform options (YT title/desc, GBP CTA, TikTok privacy).
    platform_options: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[PostTargetStatus] = mapped_column(
        SAEnum(PostTargetStatus), default=PostTargetStatus.pending
    )
    external_post_id: Mapped[str | None] = mapped_column(String(200), default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    post: Mapped["Post"] = relationship(back_populates="targets")
    channel: Mapped["Channel"] = relationship(back_populates="post_targets")
    media_asset: Mapped["MediaAsset | None"] = relationship(
        back_populates="post_targets"
    )
