"""SQLAlchemy ORM models for the asset relationship database."""

from __future__ import annotations

from typing import List

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class AssetORM(Base):
    """Persistent representation of an asset."""

    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    asset_class: Mapped[str] = mapped_column(String, nullable=False)
    sector: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    # Equity-specific fields
    pe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    dividend_yield: Mapped[float | None] = mapped_column(Float, nullable=True)
    earnings_per_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    book_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Bond-specific fields
    yield_to_maturity: Mapped[float | None] = mapped_column(Float, nullable=True)
    coupon_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    maturity_date: Mapped[str | None] = mapped_column(String, nullable=True)
    credit_rating: Mapped[str | None] = mapped_column(String, nullable=True)
    issuer_id: Mapped[str | None] = mapped_column(String, nullable=True)

    # Commodity fields
    contract_size: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_date: Mapped[str | None] = mapped_column(String, nullable=True)
    volatility: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Currency fields
    exchange_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)
    central_bank_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

    outgoing_relationships: Mapped[List["AssetRelationshipORM"]] = relationship(
        "AssetRelationshipORM",
        back_populates="source",
        cascade="all, delete-orphan",
        foreign_keys="AssetRelationshipORM.source_asset_id",
    )
    incoming_relationships: Mapped[List["AssetRelationshipORM"]] = relationship(
        "AssetRelationshipORM",
        back_populates="target",
        cascade="all, delete-orphan",
        foreign_keys="AssetRelationshipORM.target_asset_id",
    )
    regulatory_events: Mapped[List["RegulatoryEventORM"]] = relationship(
        "RegulatoryEventORM", back_populates="asset", cascade="all, delete-orphan"
    )


class AssetRelationshipORM(Base):
    """Stores directed relationships between assets."""

    __tablename__ = "asset_relationships"
    __table_args__ = (
        UniqueConstraint("source_asset_id", "target_asset_id", "relationship_type", name="uq_relationship"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    target_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String, nullable=False)
    strength: Mapped[float] = mapped_column(Float, nullable=False)
    bidirectional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    source: Mapped[AssetORM] = relationship(
        "AssetORM", foreign_keys=[source_asset_id], back_populates="outgoing_relationships"
    )
    target: Mapped[AssetORM] = relationship(
        "AssetORM", foreign_keys=[target_asset_id], back_populates="incoming_relationships"
    )


class RegulatoryEventORM(Base):
    """Persistent regulatory event."""

    __tablename__ = "regulatory_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    date: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    impact_score: Mapped[float] = mapped_column(Float, nullable=False)

    asset: Mapped[AssetORM] = relationship("AssetORM", back_populates="regulatory_events")
    related_assets: Mapped[List["RegulatoryEventAssetORM"]] = relationship(
        "RegulatoryEventAssetORM", back_populates="event", cascade="all, delete-orphan"
    )


class RegulatoryEventAssetORM(Base):
    """Join table linking regulatory events to related assets."""

    __tablename__ = "regulatory_event_assets"
    __table_args__ = (UniqueConstraint("event_id", "asset_id", name="uq_event_asset"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("regulatory_events.id", ondelete="CASCADE"), nullable=False)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)

    event: Mapped[RegulatoryEventORM] = relationship("RegulatoryEventORM", back_populates="related_assets")
    asset: Mapped[AssetORM] = relationship("AssetORM")
