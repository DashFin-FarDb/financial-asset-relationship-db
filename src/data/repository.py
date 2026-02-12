"""Repository helpers for interacting with the asset relationship database."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.financial_models import (
    Asset,
    AssetClass,
    Bond,
    Commodity,
    Currency,
    Equity,
    RegulatoryActivity,
    RegulatoryEvent,
)

from .db_models import (
    AssetORM,
    AssetRelationshipORM,
    RegulatoryEventAssetORM,
    RegulatoryEventORM,
)


@dataclass(frozen=True, slots=True)
class RelationshipRecord:
    """Lightweight relationship representation returned by the repository."""

    source_id: str
    target_id: str
    relationship_type: str
    strength: float
    bidirectional: bool


class AssetGraphRepository:
    """Data access layer for the asset relationship graph."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Asset helpers
    # ------------------------------------------------------------------
    def upsert_asset(self, asset: Asset) -> None:
        """Create or update an asset record."""
        existing = self.session.get(AssetORM, asset.id)
        if existing is None:
            existing = AssetORM(id=asset.id)
        self._update_asset_orm(existing, asset)
        self.session.add(existing)

    def list_assets(self) -> list[Asset]:
        """Return all assets as dataclass instances ordered by id."""
        records = self.session.execute(select(AssetORM).order_by(AssetORM.id)).scalars().all()
        return [self._to_asset_model(record) for record in records]

    def get_assets_map(self) -> dict[str, Asset]:
        """Return mapping of asset id to asset dataclass."""
        assets = self.list_assets()
        return {asset.id: asset for asset in assets}

    def get_asset_by_id(self, asset_id: str) -> Asset | None:
        """Return a single asset by its ID, or None if not found."""
        orm = self.session.get(AssetORM, asset_id)
        return None if orm is None else self._to_asset_model(orm)

    def delete_asset(self, asset_id: str) -> None:
        """Delete an asset (cascades per ORM config)."""
        asset = self.session.get(AssetORM, asset_id)
        if asset is not None:
            self.session.delete(asset)

    # ------------------------------------------------------------------
    # Relationship helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_strength(strength: float) -> None:
        """Validate relationship strength is numeric and in [-1.0, 1.0]."""
        # bool is a subclass of int, so reject explicitly
        if isinstance(strength, bool) or not isinstance(strength, (int, float)):
            raise ValueError("strength must be a numeric value between -1.0 and 1.0")
        if strength < -1.0 or strength > 1.0:
            raise ValueError("strength must be between -1.0 and 1.0 (inclusive)")

    def _get_relationship_orm(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
    ) -> AssetRelationshipORM | None:
        stmt = select(AssetRelationshipORM).where(
            AssetRelationshipORM.source_asset_id == source_id,
            AssetRelationshipORM.target_asset_id == target_id,
            AssetRelationshipORM.relationship_type == rel_type,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def add_or_update_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        strength: float,
        bidirectional: bool = False,
    ) -> None:
        """
        Add or update a relationship between two assets.

        Strength must be numeric in the inclusive range [-1.0, 1.0].
        Negative values represent negative correlations.
        """
        self._validate_strength(strength)

        existing = self._get_relationship_orm(source_id, target_id, rel_type)
        if existing is None:
            existing = AssetRelationshipORM(
                source_asset_id=source_id,
                target_asset_id=target_id,
                relationship_type=rel_type,
                strength=float(strength),
                bidirectional=bidirectional,
            )
        else:
            existing.strength = float(strength)
            existing.bidirectional = bidirectional

        self.session.add(existing)

    def list_relationships(self) -> list[RelationshipRecord]:
        """Return all relationships from the database."""
        records = self.session.execute(select(AssetRelationshipORM)).scalars().all()
        return [self._to_relationship_record(rel) for rel in records]

    def get_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
    ) -> RelationshipRecord | None:
        """Return a single relationship matching the given identifiers, if present."""
        relationship = self._get_relationship_orm(source_id, target_id, rel_type)
        return None if relationship is None else self._to_relationship_record(relationship)

    def delete_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
    ) -> None:
        """Remove a relationship if present."""
        relationship = self._get_relationship_orm(source_id, target_id, rel_type)
        if relationship is not None:
            self.session.delete(relationship)

    @staticmethod
    def _to_relationship_record(rel: AssetRelationshipORM) -> RelationshipRecord:
        return RelationshipRecord(
            source_id=rel.source_asset_id,
            target_id=rel.target_asset_id,
            relationship_type=rel.relationship_type,
            strength=float(rel.strength),
            bidirectional=bool(rel.bidirectional),
        )

    # ------------------------------------------------------------------
    # Regulatory events
    # ------------------------------------------------------------------
    def upsert_regulatory_event(self, event: RegulatoryEvent) -> None:
        """Create or update a regulatory event record."""
        existing = self.session.get(RegulatoryEventORM, event.id)
        if existing is None:
            existing = RegulatoryEventORM(id=event.id)

        existing.asset_id = event.asset_id
        existing.event_type = event.event_type.value
        existing.date = event.date
        existing.description = event.description
        existing.impact_score = float(event.impact_score)

        # Rebuild associations to avoid stale rows
        existing.related_assets.clear()
        for related_id in event.related_assets:
            existing.related_assets.append(RegulatoryEventAssetORM(asset_id=related_id))

        self.session.add(existing)

    def list_regulatory_events(self) -> list[RegulatoryEvent]:
        """Return all regulatory events."""
        records = self.session.execute(select(RegulatoryEventORM)).scalars().all()
        return [self._to_regulatory_event_model(record) for record in records]

    def delete_regulatory_event(self, event_id: str) -> None:
        """Delete a regulatory event if present."""
        record = self.session.get(RegulatoryEventORM, event_id)
        if record is not None:
            self.session.delete(record)

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _maybe_float(value: Any) -> float | None:
        if value is None:
            return None
        return float(value)

    @staticmethod
    def _update_asset_orm(orm: AssetORM, asset: Asset) -> None:
        """
        Populate an existing AssetORM row from an Asset (or subclass) instance.

        Always updates common Asset fields and clears/repopulates optional
        subtype fields to prevent stale data lingering after type changes.
        """
        orm.symbol = asset.symbol
        orm.name = asset.name
        orm.asset_class = asset.asset_class.value
        orm.sector = asset.sector
        orm.price = float(asset.price)
        orm.market_cap = float(asset.market_cap) if asset.market_cap is not None else None
        orm.currency = asset.currency

        # Reset optional fields
        orm.pe_ratio = getattr(asset, "pe_ratio", None)
        orm.dividend_yield = getattr(asset, "dividend_yield", None)
        orm.earnings_per_share = getattr(asset, "earnings_per_share", None)
        orm.book_value = getattr(asset, "book_value", None)

        orm.yield_to_maturity = getattr(asset, "yield_to_maturity", None)
        orm.coupon_rate = getattr(asset, "coupon_rate", None)
        orm.maturity_date = getattr(asset, "maturity_date", None)
        orm.credit_rating = getattr(asset, "credit_rating", None)
        orm.issuer_id = getattr(asset, "issuer_id", None)

        orm.contract_size = getattr(asset, "contract_size", None)
        orm.delivery_date = getattr(asset, "delivery_date", None)
        orm.volatility = getattr(asset, "volatility", None)

        orm.exchange_rate = getattr(asset, "exchange_rate", None)
        orm.country = getattr(asset, "country", None)
        orm.central_bank_rate = getattr(asset, "central_bank_rate", None)

    @staticmethod
    def _to_asset_model(orm: AssetORM) -> Asset:
        """Convert an AssetORM database object to an Asset domain model instance."""
        asset_class = AssetClass(orm.asset_class)
        base_kwargs: dict[str, Any] = {
            "id": orm.id,
            "symbol": orm.symbol,
            "name": orm.name,
            "asset_class": asset_class,
            "sector": orm.sector,
            "price": float(orm.price),
            "market_cap": AssetGraphRepository._maybe_float(orm.market_cap),
            "currency": orm.currency,
        }

        if asset_class == AssetClass.EQUITY:
            return Equity(
                **base_kwargs,
                pe_ratio=orm.pe_ratio,
                dividend_yield=orm.dividend_yield,
                earnings_per_share=orm.earnings_per_share,
                book_value=orm.book_value,
            )
        if asset_class == AssetClass.FIXED_INCOME:
            return Bond(
                **base_kwargs,
                yield_to_maturity=orm.yield_to_maturity,
                coupon_rate=orm.coupon_rate,
                maturity_date=orm.maturity_date,
                credit_rating=orm.credit_rating,
                issuer_id=orm.issuer_id,
            )
        if asset_class == AssetClass.COMMODITY:
            return Commodity(
                **base_kwargs,
                contract_size=orm.contract_size,
                delivery_date=orm.delivery_date,
                volatility=orm.volatility,
            )
        if asset_class == AssetClass.CURRENCY:
            return Currency(
                **base_kwargs,
                exchange_rate=orm.exchange_rate,
                country=orm.country,
                central_bank_rate=orm.central_bank_rate,
            )

        # Fallback base Asset
        return Asset(**base_kwargs)

    @staticmethod
    def _to_regulatory_event_model(orm: RegulatoryEventORM) -> RegulatoryEvent:
        """Convert a RegulatoryEventORM database object to a RegulatoryEvent domain model instance."""
        related_assets = [assoc.asset_id for assoc in orm.related_assets]
        return RegulatoryEvent(
            id=orm.id,
            asset_id=orm.asset_id,
            event_type=RegulatoryActivity(orm.event_type),
            date=orm.date,
            description=orm.description,
            impact_score=float(orm.impact_score),
            related_assets=related_assets,
        )
