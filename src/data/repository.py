"""Repository helpers for interacting with the asset relationship database."""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, NoReturn, TypeAlias, TypedDict
from uuid import uuid4

from sqlalchemy import and_, delete, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from src.logic.asset_graph import AssetRelationshipGraph
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
    DistributedLockORM,
    RebuildJobORM,
    RebuildJobStatus,
    RegulatoryEventAssetORM,
    RegulatoryEventORM,
)

UTC = timezone.utc


@dataclass(frozen=True, slots=True)
class LockRecord:
    """Immutable Lock DTO."""

    lock_name: str
    holder_id: str
    fencing_token: int
    updated_at: datetime
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class LockWriteResult:
    """Atomic write response for lock operations."""

    success: bool
    fencing_token: int
    updated_at: datetime
    contention: bool


@dataclass(frozen=True, slots=True)
class LockStateSnapshot:
    """Read-only coordination view snapshot of a distributed lock."""

    exists: bool
    valid: bool
    holder_id: str | None
    fencing_token: int | None
    updated_at: datetime | None
    expires_at: datetime | None


class CoordinationLockRepository:
    """
    Coordination-safe repository for coordination lock operations.

    Uses a SQLAlchemy Session internally but returns materialized DTOs (LockWriteResult,
    LockStateSnapshot) so callers do not receive ORM objects. This clarifies the
    repository's API and ownership of the session lifecycle.
    """

    def __init__(self, session: Session) -> None:
        """Initialize with an active database Session."""
        self.session = session

    def acquire_lock(
        self,
        *,
        lock_name: str,
        holder_id: str,
        ttl_seconds: int,
    ) -> LockWriteResult:
        """
        Try to acquire or refresh a distributed lock in the database.

        Atomic compare-and-set semantics.
        Executes on PRIMARY only.
        Returns a fully materialized result with no follow-up reads required.
        """
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than 0")
        now = datetime.now(timezone.utc)  # noqa: UP017
        expires_at = now + timedelta(seconds=ttl_seconds)

        update_stmt = (
            update(DistributedLockORM)
            .where(
                DistributedLockORM.lock_name == lock_name,
                or_(
                    DistributedLockORM.holder_id == holder_id,
                    DistributedLockORM.expires_at < now,
                ),
            )
            .values(
                holder_id=holder_id,
                expires_at=expires_at,
                updated_at=now,
            )
        )
        update_result = self.session.execute(update_stmt)
        if update_result.rowcount and update_result.rowcount > 0:  # type: ignore[attr-defined]
            stmt = select(DistributedLockORM).where(DistributedLockORM.lock_name == lock_name)
            record = self.session.execute(stmt).scalar_one_or_none()
            if record:
                updated_at = record.updated_at
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)  # noqa: UP017
                token = int(updated_at.timestamp() * 1_000_000)
                return LockWriteResult(
                    success=True,
                    fencing_token=token,
                    updated_at=updated_at,
                    contention=False,
                )

        try:
            with self.session.begin_nested():
                self.session.execute(
                    insert(DistributedLockORM).values(
                        lock_name=lock_name,
                        holder_id=holder_id,
                        expires_at=expires_at,
                        created_at=now,
                        updated_at=now,
                    )
                )
            return LockWriteResult(
                success=True,
                fencing_token=int(now.timestamp() * 1_000_000),
                updated_at=now,
                contention=False,
            )
        except IntegrityError:
            # Retry conditional update in case of insert race
            retry_result = self.session.execute(update_stmt)
            if retry_result.rowcount and retry_result.rowcount > 0:  # type: ignore[attr-defined]
                stmt = select(DistributedLockORM).where(DistributedLockORM.lock_name == lock_name)
                record = self.session.execute(stmt).scalar_one_or_none()
                if record:
                    updated_at = record.updated_at
                    if updated_at.tzinfo is None:
                        updated_at = updated_at.replace(tzinfo=timezone.utc)  # noqa: UP017
                    token = int(updated_at.timestamp() * 1_000_000)
                    return LockWriteResult(
                        success=True,
                        fencing_token=token,
                        updated_at=updated_at,
                        contention=False,
                    )

            # Succeeded to insert by other contender, we are blocked by contention
            stmt = select(DistributedLockORM).where(DistributedLockORM.lock_name == lock_name)
            record = self.session.execute(stmt).scalar_one_or_none()
            if record:
                updated_at = record.updated_at
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)  # noqa: UP017
                token = int(updated_at.timestamp() * 1_000_000)
                return LockWriteResult(
                    success=False,
                    fencing_token=token,
                    updated_at=updated_at,
                    contention=True,
                )
            return LockWriteResult(
                success=False,
                fencing_token=0,
                updated_at=now,
                contention=True,
            )

    def refresh_lock(
        self,
        *,
        lock_name: str,
        holder_id: str,
        ttl_seconds: int,
    ) -> LockWriteResult:
        """
        Refresh a distributed lock in the database.

        Delegates to acquire_lock, which uses atomic compare-and-set semantics
        and guarantees that the fencing token is updated monotonically.
        """
        return self.acquire_lock(
            lock_name=lock_name,
            holder_id=holder_id,
            ttl_seconds=ttl_seconds,
        )

    def release_lock(self, *, lock_name: str, holder_id: str) -> bool:
        """Release a distributed lock if held by the specified holder."""
        result = self.session.execute(
            delete(DistributedLockORM).where(
                DistributedLockORM.lock_name == lock_name,
                DistributedLockORM.holder_id == holder_id,
            )
        )
        return bool(result.rowcount and result.rowcount > 0)  # type: ignore[attr-defined]

    def get_lock_state(self, *, lock_name: str, holder_id: str) -> LockStateSnapshot:
        """Check the current state of a distributed lock and return a materialized snapshot DTO."""
        now = datetime.now(timezone.utc)  # noqa: UP017
        stmt = select(DistributedLockORM).where(DistributedLockORM.lock_name == lock_name)
        record = self.session.execute(stmt).scalar_one_or_none()

        if record is None:
            return LockStateSnapshot(
                exists=False,
                valid=False,
                holder_id=None,
                fencing_token=None,
                updated_at=None,
                expires_at=None,
            )

        updated_at = record.updated_at
        if updated_at is not None and updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)  # noqa: UP017

        expires_at = record.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)  # noqa: UP017

        valid = (record.holder_id == holder_id) and (expires_at is not None and now < expires_at)
        fencing_token = int(updated_at.timestamp() * 1_000_000) if updated_at is not None else None

        return LockStateSnapshot(
            exists=True,
            valid=valid,
            holder_id=record.holder_id,
            fencing_token=fencing_token,
            updated_at=updated_at,
            expires_at=expires_at,
        )


@contextmanager
def session_scope(
    session_factory: Callable[[], Session],
) -> Generator[Session, None, None]:
    """
    Provide a transactional scope around a series of operations.

    Tech spec alignment: session_scope is defined in repository.py to provide a
    standard transaction boundary for repository interactions.
    """
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@dataclass(frozen=True, slots=True)
class RebuildFailureDetails:
    """Encapsulates failure metadata for a rebuild job."""

    failure_category: str
    failure_message: str
    duration_ms: int


@dataclass
class RelationshipRecord:
    """Lightweight relationship representation returned by the repository."""

    source_id: str
    target_id: str
    relationship_type: str
    strength: float
    bidirectional: bool


@dataclass(frozen=True)
class _RelationshipUpsertSpec:
    """Input spec used to upsert relationship rows."""

    source_id: str
    target_id: str
    rel_type: str
    strength: float
    bidirectional: bool


class _BaseAssetKwargs(TypedDict):
    """Shared kwargs accepted by all asset model constructors."""

    id: str
    symbol: str
    name: str
    asset_class: AssetClass
    sector: str
    price: float
    market_cap: float | None
    currency: str


GraphRelationshipRows: TypeAlias = dict[str, list[tuple[str, str, float]]]
_IN_CLAUSE_CHUNK_SIZE = 400


def _iter_id_chunks(values: Iterable[str]) -> Generator[tuple[str, ...], None, None]:
    """
    Yield stable-size chunks for SQL IN predicates.

    The chunk size stays below common SQLite variable limits even when a query
    uses the same chunk in more than one IN predicate.
    """
    batch: list[str] = []
    for value in values:
        batch.append(value)
        if len(batch) == _IN_CLAUSE_CHUNK_SIZE:
            yield tuple(batch)
            batch = []
    if batch:
        yield tuple(batch)


class RebuildCancellationRequestedError(Exception):
    """Raised when a rebuild heartbeat update fails because the job was marked for cancellation."""


class AssetGraphRepository:
    """Data access layer for the asset relationship graph."""

    def __init__(self, session: Session):
        """
        Initialize the repository with a SQLAlchemy session for database operations.

        Parameters:
            session (Session): SQLAlchemy Session used for all database access by this repository.
        """
        self.session = session

    # ------------------------------------------------------------------
    # Graph persistence helpers
    # ------------------------------------------------------------------
    def save_graph(self, graph: AssetRelationshipGraph) -> None:
        """
        Persist an AssetRelationshipGraph snapshot to the database.

        Stores the graph's assets, directed relationships, and regulatory events using
        snapshot semantics. Layout and visualization metadata are intentionally not
        persisted.

        Args:
            graph: In-memory graph whose assets, relationships, and regulatory events
                replace the persisted state.

        Returns:
            None.

        Raises:
            SQLAlchemyError: If the active database session fails while staging
                replacement rows.
            ValueError: If a relationship strength is invalid.
        """
        self.replace_assets(graph.assets.values())
        self.replace_relationships_from_graph(graph.relationships)
        self.replace_regulatory_events(graph.regulatory_events)

    def load_graph(self) -> AssetRelationshipGraph:
        """
        Reconstruct an in-memory asset relationship graph from persisted rows.

        Loads only durable persisted data; does not derive relationships from other
        sources or restore visualization/layout metadata. Legacy persisted rows with
        bidirectional=True are expanded through AssetRelationshipGraph semantics only
        when no explicit reverse row of the same (target, source, relationship_type) is
        also persisted; an explicit reverse row always wins and is loaded as a directed
        edge so its strength is preserved. save_graph() persists the resulting graph
        back as directed rows.

        Returns:
            AssetRelationshipGraph: The reconstructed graph containing persisted assets,
            relationship rows, and regulatory events.
        """
        from src.config.settings import get_settings

        settings = get_settings()
        graph = AssetRelationshipGraph(
            same_sector_strength=settings.same_sector_strength,
            corporate_bond_strength=settings.corporate_bond_strength,
        )
        for asset in self.list_assets():
            graph.add_asset(asset)
        for event in self.list_regulatory_events():
            graph.add_regulatory_event(event)
        persisted_relationships = self.list_relationships()
        explicit_relationship_keys = {
            (rel.source_id, rel.target_id, rel.relationship_type) for rel in persisted_relationships
        }
        for relationship in persisted_relationships:
            expand_reverse = (
                relationship.bidirectional
                and (
                    relationship.target_id,
                    relationship.source_id,
                    relationship.relationship_type,
                )
                not in explicit_relationship_keys
            )
            graph.add_relationship(
                relationship.source_id,
                relationship.target_id,
                relationship.relationship_type,
                relationship.strength,
                bidirectional=expand_reverse,
            )
        return graph

    def replace_assets(self, assets: Iterable[Asset]) -> None:
        """
        Replace persisted assets with the supplied graph asset collection.

        Rows absent from the incoming graph are deleted so save/load behaves as
        a graph snapshot operation rather than a partial upsert.
        """
        incoming_assets = list(assets)
        incoming_ids = {asset.id for asset in incoming_assets}
        persisted_ids = set(self.session.execute(select(AssetORM.id)).scalars().all())
        stale_ids = persisted_ids - incoming_ids

        if stale_ids:
            stale_event_ids: set[str] = set()
            for stale_id_chunk in _iter_id_chunks(stale_ids):
                stale_event_ids.update(
                    self.session.execute(
                        select(RegulatoryEventORM.id).where(RegulatoryEventORM.asset_id.in_(stale_id_chunk))
                    )
                    .scalars()
                    .all()
                )

                self.session.execute(
                    delete(AssetRelationshipORM).where(
                        (AssetRelationshipORM.source_asset_id.in_(stale_id_chunk))
                        | (AssetRelationshipORM.target_asset_id.in_(stale_id_chunk))
                    ),
                    execution_options={"synchronize_session": "fetch"},
                )
                self.session.execute(
                    delete(RegulatoryEventAssetORM).where(RegulatoryEventAssetORM.asset_id.in_(stale_id_chunk)),
                    execution_options={"synchronize_session": "fetch"},
                )

            if stale_event_ids:
                for stale_event_id_chunk in _iter_id_chunks(stale_event_ids):
                    self.session.execute(
                        delete(RegulatoryEventAssetORM).where(
                            RegulatoryEventAssetORM.event_id.in_(stale_event_id_chunk)
                        ),
                        execution_options={"synchronize_session": "fetch"},
                    )
                    self.session.execute(
                        delete(RegulatoryEventORM).where(RegulatoryEventORM.id.in_(stale_event_id_chunk)),
                        execution_options={"synchronize_session": "fetch"},
                    )

            for stale_id_chunk in _iter_id_chunks(stale_ids):
                self.session.execute(
                    delete(AssetORM).where(AssetORM.id.in_(stale_id_chunk)),
                    execution_options={"synchronize_session": "fetch"},
                )
            self.session.flush()

        self.upsert_assets(incoming_assets)

    def replace_relationships_from_graph(
        self,
        relationships: GraphRelationshipRows,
    ) -> None:
        """
        Replace all persisted relationships with directed adjacency data.

        Deletes existing relationship rows and inserts one new row for each outgoing
        edge in `relationships`. Each outgoing tuple is interpreted as
        `(target_id, relationship_type, strength)`. Inserted rows are stored as directed
        edges with `bidirectional=False`.

        Args:
            relationships: Mapping from source asset ID to outgoing edge tuples.

        Returns:
            None.

        Raises:
            SQLAlchemyError: If the active database session fails while deleting or
                staging relationship rows.
            ValueError: If any relationship strength is invalid.
        """
        self.session.execute(
            delete(AssetRelationshipORM),
            execution_options={"synchronize_session": "fetch"},
        )
        self.session.flush()
        relationship_rows = [
            AssetRelationshipORM(
                source_asset_id=source_id,
                target_asset_id=target_id,
                relationship_type=relationship_type,
                strength=self._validate_relationship_strength(strength),
                bidirectional=False,
            )
            for source_id, outgoing_relationships in relationships.items()
            for target_id, relationship_type, strength in outgoing_relationships
        ]
        if relationship_rows:
            self.session.add_all(relationship_rows)

    def replace_regulatory_events(self, events: Iterable[RegulatoryEvent]) -> None:
        """
        Replace all persisted regulatory events with the supplied collection.

        Deletes existing regulatory events and event-asset link rows, flushes the
        deletion, then inserts ORM rows for each provided event and related asset
        association. Event IDs are used as the idempotency key for this compatibility
        mode.

        Args:
            events: Regulatory events to persist as the complete event set.

        Returns:
            None.

        Raises:
            SQLAlchemyError: If the active database session fails while deleting or
                staging event rows.
        """
        incoming_events = list(events)
        seen_event_ids: set[str] = set()
        duplicate_event_ids: set[str] = set()
        for event in incoming_events:
            if event.id in seen_event_ids:
                duplicate_event_ids.add(event.id)
            seen_event_ids.add(event.id)
        if duplicate_event_ids:
            duplicate_ids = ", ".join(sorted(duplicate_event_ids))
            raise ValueError(f"replace_regulatory_events() received duplicate event IDs: {duplicate_ids}")

        self.session.execute(
            delete(RegulatoryEventAssetORM),
            execution_options={"synchronize_session": "fetch"},
        )
        self.session.execute(
            delete(RegulatoryEventORM),
            execution_options={"synchronize_session": "fetch"},
        )
        self.session.flush()
        event_rows: list[RegulatoryEventORM] = []
        for event in incoming_events:
            event_orm = RegulatoryEventORM(
                id=event.id,
                asset_id=event.asset_id,
                event_type=event.event_type.value,
                date=event.date,
                description=event.description,
                impact_score=event.impact_score,
            )
            for related_id in dict.fromkeys(event.related_assets):
                event_orm.related_assets.append(RegulatoryEventAssetORM(asset_id=related_id))
            event_rows.append(event_orm)
        if event_rows:
            self.session.add_all(event_rows)

    # ------------------------------------------------------------------
    # Asset helpers
    # ------------------------------------------------------------------
    def upsert_asset(self, asset: Asset) -> None:
        """
        Create or update the persistent record for a domain Asset.

        Maps fields from the given domain `Asset` onto an `AssetORM`, creating
        one if needed, and stages the ORM instance on the repository session.

        Args:
            asset: Domain asset to persist or update.

        Returns:
            None.
        """
        existing = self.session.get(AssetORM, asset.id)
        if existing is None:
            existing = AssetORM(id=asset.id)
        self._update_asset_orm(existing, asset)
        self.session.add(existing)

    def upsert_assets(self, assets: Iterable[Asset]) -> None:
        """
        Create or update multiple assets in a single repository session.

        Args:
            assets: Domain assets to create or update.

        Returns:
            None.

        Raises:
            SQLAlchemyError: If the active database session fails while loading or
                staging asset rows.
        """
        incoming_assets = list(assets)
        if not incoming_assets:
            return

        incoming_ids = list(dict.fromkeys(asset.id for asset in incoming_assets))
        existing_assets: dict[str, AssetORM] = {}
        for incoming_id_chunk in _iter_id_chunks(incoming_ids):
            existing_assets.update(
                {
                    orm.id: orm
                    for orm in self.session.execute(select(AssetORM).where(AssetORM.id.in_(incoming_id_chunk)))
                    .scalars()
                    .all()
                }
            )

        for asset in incoming_assets:
            orm = existing_assets.get(asset.id)
            if orm is None:
                orm = AssetORM(id=asset.id)
                self.session.add(orm)
                existing_assets[asset.id] = orm
            self._update_asset_orm(orm, asset)

    def list_assets(self) -> list[Asset]:
        """
        Retrieve all assets ordered by id.

        Returns:
            List[Asset]: A list of domain Asset instances
                representing all assets in the database,
                ordered by asset id.
        """
        result = self.session.execute(select(AssetORM).order_by(AssetORM.id)).scalars().all()
        return [self._to_asset_model(record) for record in result]

    def get_assets_map(self) -> dict[str, Asset]:
        """
        Return a mapping of asset id to the corresponding Asset domain object.

        Returns:
            Dict[str, Asset]: Keys are asset ids and values are the
                corresponding Asset instances.
        """
        assets = self.list_assets()
        return {asset.id: asset for asset in assets}

    def get_asset_by_id(self, asset_id: str) -> Asset | None:
        """
        Return a single asset by its ID, or None if not found.

        Args:
            asset_id: Asset identifier to retrieve.
        Returns:
            Optional[Asset]: The asset if found, otherwise None.
        """
        orm = self.session.get(AssetORM, asset_id)
        if orm is None:
            return None
        return self._to_asset_model(orm)

    def delete_asset(self, asset_id: str) -> None:
        """Delete an asset and cascading relationships/events."""
        asset = self.session.get(AssetORM, asset_id)
        if asset is not None:
            self.session.delete(asset)

    # ------------------------------------------------------------------
    # Relationship helpers
    # ------------------------------------------------------------------
    def add_or_update_relationship(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Create or update an asset relationship and stage it on the repository session.

        Accepts either a single _RelationshipUpsertSpec or explicit fields
        (source_id, target_id, rel_type, strength[, bidirectional=False]).
        Strength must be a numeric value between -1.0 and 1.0 inclusive; boolean
        values are rejected.

        Parameters:
            *args: Either a single `_RelationshipUpsertSpec` or positional fields:
                (source_id, target_id, rel_type, strength[, bidirectional]).
            **kwargs: When not passing a `_RelationshipUpsertSpec`, may include
                `bidirectional` as a keyword.
        """
        relationship_spec = self._build_relationship_upsert_spec(
            *args,
            **kwargs,
        )
        relationship = self._get_or_create_relationship_orm(relationship_spec)
        self.session.add(relationship)

    def _build_relationship_upsert_spec(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> _RelationshipUpsertSpec:
        """
        Normalize input arguments for adding or updating an asset relationship into a _RelationshipUpsertSpec.

        Accepts either a single _RelationshipUpsertSpec positional argument, or positional fields:
        (source_id, target_id, rel_type, strength[, bidirectional]). Validates and normalizes
        the strength to a float within [-1.0, 1.0], converts identifiers and rel_type to strings,
        and converts bidirectional to a boolean.

        Parameters:
            *args: Either a single `_RelationshipUpsertSpec` or the explicit fields
                `(source_id, target_id, rel_type, strength[, bidirectional])`.
            **kwargs: May include `bidirectional` when explicit fields are provided; other
                keyword arguments are not allowed.

        Returns:
            _RelationshipUpsertSpec: A frozen spec with `source_id`, `target_id`, and `rel_type`
            as strings, `strength` as a float within [-1.0, 1.0], and `bidirectional` as a bool.

        Raises:
            TypeError: If an unexpected combination of positional/keyword arguments is supplied
                (including extra keywords or insufficient positional arguments).
        """
        if len(args) == 1 and isinstance(args[0], _RelationshipUpsertSpec):
            if kwargs:
                raise TypeError("Unexpected keyword arguments with spec argument")
            spec = args[0]
            normalized_strength = self._validate_relationship_strength(spec.strength)
            return _RelationshipUpsertSpec(
                source_id=spec.source_id,
                target_id=spec.target_id,
                rel_type=spec.rel_type,
                strength=normalized_strength,
                bidirectional=spec.bidirectional,
            )

        if len(args) < 4:
            raise TypeError("Expected (source_id, target_id, rel_type, strength[, bidirectional])")

        source_id = args[0]
        target_id = args[1]
        rel_type = args[2]
        strength = args[3]
        bidirectional = (
            args[4]
            if len(args) >= 5
            else kwargs.pop(
                "bidirectional",
                False,
            )
        )
        if kwargs:
            raise TypeError(f"Unexpected keyword arguments: {', '.join(kwargs.keys())}")

        normalized_strength = self._validate_relationship_strength(strength)
        return _RelationshipUpsertSpec(
            source_id=str(source_id),
            target_id=str(target_id),
            rel_type=str(rel_type),
            strength=normalized_strength,
            bidirectional=bool(bidirectional),
        )

    @staticmethod
    def _validate_relationship_strength(strength: float) -> float:
        """
        Validate and normalize a relationship strength value.

        Accepts a numeric strength in the range -1.0 to 1.0 (inclusive); boolean values are rejected.

        Parameters:
            strength (int | float): The value to validate and normalize.

        Returns:
            float: The validated strength converted to a float.

        Raises:
            ValueError: If `strength` is a boolean, not numeric, or outside the range [-1.0, 1.0].
        """
        if isinstance(strength, bool) or not isinstance(
            strength,
            (int, float),
        ):
            raise ValueError("strength must be a numeric value between -1.0 and 1.0")
        if strength < -1.0 or strength > 1.0:
            raise ValueError("strength must be between -1.0 and 1.0 (inclusive)")
        return float(strength)

    def _get_or_create_relationship_orm(
        self,
        relationship_spec: _RelationshipUpsertSpec,
    ) -> AssetRelationshipORM:
        """
        Obtain or construct an AssetRelationshipORM that corresponds to the provided upsert specification.

        Parameters:
            relationship_spec (_RelationshipUpsertSpec): Normalized relationship input containing
                source_id, target_id, rel_type, strength, and bidirectional.

        Returns:
            AssetRelationshipORM: An existing ORM instance matching source, target, and relationship type
            with its `strength` and `bidirectional` fields updated, or a new ORM instance populated
            from the specification if no existing row was found.
        """
        stmt = select(AssetRelationshipORM).where(
            AssetRelationshipORM.source_asset_id == relationship_spec.source_id,
            AssetRelationshipORM.target_asset_id == relationship_spec.target_id,
            AssetRelationshipORM.relationship_type == relationship_spec.rel_type,
        )
        relationship = self.session.execute(stmt).scalar_one_or_none()
        if relationship is None:
            return AssetRelationshipORM(
                source_asset_id=relationship_spec.source_id,
                target_asset_id=relationship_spec.target_id,
                relationship_type=relationship_spec.rel_type,
                strength=relationship_spec.strength,
                bidirectional=relationship_spec.bidirectional,
            )
        relationship.strength = relationship_spec.strength
        relationship.bidirectional = relationship_spec.bidirectional
        return relationship

    def list_relationships(self) -> list[RelationshipRecord]:
        """
        List all asset relationships stored in the repository.

        Returns:
            List[RelationshipRecord]: A list of RelationshipRecord objects, each
                containing source_id, target_id, relationship_type, strength
                (float), and bidirectional (bool).
        """
        result = (
            self.session.execute(
                select(AssetRelationshipORM).order_by(
                    AssetRelationshipORM.source_asset_id,
                    AssetRelationshipORM.target_asset_id,
                    AssetRelationshipORM.relationship_type,
                )
            )
            .scalars()
            .all()
        )
        return [
            RelationshipRecord(
                source_id=rel.source_asset_id,
                target_id=rel.target_asset_id,
                relationship_type=rel.relationship_type,
                strength=float(rel.strength),
                bidirectional=rel.bidirectional,
            )
            for rel in result
        ]

    def get_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
    ) -> RelationshipRecord | None:
        """
        Return the relationship between two assets for the given relationship type.

        Returns:
            `RelationshipRecord` if a matching relationship exists
            (with `strength` converted to a `float`), `None` otherwise.
        """
        stmt = select(AssetRelationshipORM).where(
            AssetRelationshipORM.source_asset_id == source_id,
            AssetRelationshipORM.target_asset_id == target_id,
            AssetRelationshipORM.relationship_type == rel_type,
        )
        relationship = self.session.execute(stmt).scalar_one_or_none()
        if relationship is None:
            return None
        return RelationshipRecord(
            source_id=relationship.source_asset_id,
            target_id=relationship.target_asset_id,
            relationship_type=relationship.relationship_type,
            strength=float(relationship.strength),
            bidirectional=relationship.bidirectional,
        )

    def delete_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
    ) -> None:
        """Remove a relationship."""
        stmt = select(AssetRelationshipORM).where(
            AssetRelationshipORM.source_asset_id == source_id,
            AssetRelationshipORM.target_asset_id == target_id,
            AssetRelationshipORM.relationship_type == rel_type,
        )
        relationship = self.session.execute(stmt).scalar_one_or_none()
        if relationship is not None:
            self.session.delete(relationship)

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
        existing.impact_score = event.impact_score
        existing.related_assets.clear()
        for related_id in dict.fromkeys(event.related_assets):
            existing.related_assets.append(RegulatoryEventAssetORM(asset_id=related_id))

        self.session.add(existing)

    def list_regulatory_events(self) -> list[RegulatoryEvent]:
        """
        Retrieve all persisted regulatory events ordered by date then id.

        Each returned event includes its associated related_assets (eagerly loaded).

        Returns:
            events (list[RegulatoryEvent]): RegulatoryEvent models ordered by `date`,
            then `id`, with `related_assets` populated.
        """
        result = (
            self.session.execute(
                select(RegulatoryEventORM)
                .options(selectinload(RegulatoryEventORM.related_assets))
                .order_by(
                    RegulatoryEventORM.date,
                    RegulatoryEventORM.id,
                )
            )
            .scalars()
            .all()
        )
        return [self._to_regulatory_event_model(record) for record in result]

    def delete_regulatory_event(self, event_id: str) -> None:
        """
        Delete the persisted regulatory event with the given id.

        Parameters:
            event_id (str): Primary key of the regulatory event to delete.
            If no matching record exists, no action is taken.
        """
        record = self.session.get(RegulatoryEventORM, event_id)
        if record is not None:
            self.session.delete(record)

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _update_asset_orm(orm: AssetORM, asset: Asset) -> None:
        """
        Populate an existing AssetORM row from an Asset (or subclass) instance.

        Clears and repopulates optional, asset-class-specific columns so
        missing attributes become NULL and stale values cannot persist
        across updates.
        """
        orm.symbol = asset.symbol
        orm.name = asset.name
        orm.asset_class = asset.asset_class.value
        orm.sector = asset.sector
        orm.price = float(asset.price)
        orm.market_cap = float(asset.market_cap) if asset.market_cap is not None else None
        orm.currency = asset.currency

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
        """
        Construct a domain Asset instance (specific subclass when applicable) from an AssetORM row.

        Parameters:
            orm (AssetORM): The persisted ORM row to convert.

        Returns:
            Asset: A domain Asset. Returns an Equity, Bond, Commodity, or Currency instance when
            `orm.asset_class` indicates that class; otherwise returns a generic `Asset`.
        """
        asset_class = AssetClass(orm.asset_class)
        base_kwargs: _BaseAssetKwargs = {
            "id": orm.id,
            "symbol": orm.symbol,
            "name": orm.name,
            "asset_class": asset_class,
            "sector": orm.sector,
            "price": orm.price,
            "market_cap": orm.market_cap,
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
        return Asset(**base_kwargs)

    @staticmethod
    def _to_regulatory_event_model(orm: RegulatoryEventORM) -> RegulatoryEvent:
        """
        Convert a RegulatoryEvent ORM row into a domain RegulatoryEvent model.

        Extracts related asset IDs from orm.related_assets and constructs a RegulatoryEvent
        with id, asset_id, event_type (mapped to RegulatoryActivity), date, description,
        impact_score, and related_assets.

        Returns:
            RegulatoryEvent: Domain model built from the ORM row.
        """
        related_assets = sorted(assoc.asset_id for assoc in orm.related_assets)
        return RegulatoryEvent(
            id=orm.id,
            asset_id=orm.asset_id,
            event_type=RegulatoryActivity(orm.event_type),
            date=orm.date,
            description=orm.description,
            impact_score=orm.impact_score,
            related_assets=related_assets,
        )

    # ------------------------------------------------------------------
    # Rebuild job helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_non_negative_metrics(
        *,
        duration_ms: int,
        node_count: int | None = None,
        edge_count: int | None = None,
    ) -> None:
        """Validate non-negative rebuild metrics."""
        named_values: dict[str, int] = {"duration_ms": duration_ms}
        if node_count is not None:
            named_values["node_count"] = node_count
        if edge_count is not None:
            named_values["edge_count"] = edge_count
        invalid = [name for name, value in named_values.items() if value < 0]
        if invalid:
            raise ValueError(f"{invalid[0]} must be non-negative")

    @staticmethod
    def _validate_failure_metadata(*, failure_category: str, failure_message: str) -> None:
        """Validate bounded failure metadata."""
        if len(failure_category) > 64:
            raise ValueError("failure_category must not exceed 64 characters")
        if len(failure_message) > 512:
            raise ValueError("failure_message must not exceed 512 characters")

    def create_rebuild_job(
        self,
        *,
        requested_by: str,
        source: str | None = None,
    ) -> str:
        """
        Create a new rebuild job record in pending status.

        Args:
            requested_by: Bounded username of the rebuild operator (max 64 chars).
            source: Optional rebuild source identifier (max 32 chars).

        Returns:
            str: The generated job_id (UUID format).

        Raises:
            ValueError: If requested_by exceeds 64 characters or source exceeds 32 characters.
        """
        if len(requested_by) > 64:
            raise ValueError("requested_by must not exceed 64 characters")
        if source is not None and len(source) > 32:
            raise ValueError("source must not exceed 32 characters")

        job_id = str(uuid4())
        now = datetime.now(timezone.utc)  # noqa: UP017

        job = RebuildJobORM(
            job_id=job_id,
            requested_by=requested_by,
            status=RebuildJobStatus.PENDING,
            source=source,
            created_at=now,
            updated_at=now,
        )
        self.session.add(job)
        self.session.flush()  # Flush to ensure job is visible to subsequent queries
        return job_id

    def update_rebuild_job_source(self, job_id: str, execution_id: str, source: str | None) -> None:
        """
        Update the source field on a rebuild job record atomatically.

        Args:
            job_id: The job identifier to update.
            execution_id: The unique identifier for this execution attempt.
            source: Rebuild source identifier (max 32 chars), or None to clear.

        Raises:
            ValueError: If the job does not exist, source exceeds 32 characters, or execution_id mismatches.
        """
        if source is not None and len(source) > 32:
            raise ValueError("source must not exceed 32 characters")

        # Flush any pending ORM changes to ensure UPDATE sees current state
        self.session.flush()

        # Atomic conditional update: only succeeds if execution_id matches
        now = datetime.now(timezone.utc)  # noqa: UP017
        stmt = (
            update(RebuildJobORM)
            .where(RebuildJobORM.job_id == job_id)
            .where(RebuildJobORM.execution_id == execution_id)
            .values(
                source=source,
                updated_at=now,
            )
        )
        result = self.session.execute(stmt)

        # If no rows were updated, check why
        if result.rowcount == 0:  # type: ignore[attr-defined]
            # Refresh to get current state (re-fetch from DB if needed)
            job = self.session.get(RebuildJobORM, job_id)
            if job is None:
                raise ValueError(f"Rebuild job {job_id} not found")

            if job.execution_id != execution_id:
                raise ValueError(f"Execution identity mismatch: {job.execution_id} != {execution_id}")
            # This case shouldn't be reached if job exists and execution_id matches,
            # but we raise a generic error just in case of concurrent deletion.
            raise ValueError(f"Failed to update source for job {job_id}")

    def mark_rebuild_job_running(self, job_id: str, execution_id: str) -> None:
        """
        Transition rebuild job from pending to running status and assign execution identity atomatically.

        Args:
            job_id: The job identifier to update.
            execution_id: The unique identifier for this execution attempt.

        Raises:
            ValueError: If the job does not exist or is not in pending status.
        """
        if len(execution_id) > 64:
            raise ValueError(f"execution_id exceeds maximum length of 64 characters: {len(execution_id)} chars")

        # Flush any pending ORM changes to ensure UPDATE sees current state
        self.session.flush()

        # Atomic conditional update: only succeeds if job is still PENDING
        now = datetime.now(timezone.utc)  # noqa: UP017
        stmt = (
            update(RebuildJobORM)
            .where(RebuildJobORM.job_id == job_id)
            .where(RebuildJobORM.status == RebuildJobStatus.PENDING)
            .values(
                status=RebuildJobStatus.RUNNING,
                started_at=now,
                updated_at=now,
                execution_id=execution_id,
            )
        )
        result = self.session.execute(stmt)

        # If no rows were updated, check why
        if result.rowcount == 0:  # type: ignore[attr-defined]
            # Refresh to get current state (re-fetch from DB if needed)
            job = self.session.get(RebuildJobORM, job_id)
            if job is None:
                raise ValueError(f"Rebuild job {job_id} not found")

            if job.status != RebuildJobStatus.PENDING:
                raise ValueError(f"Cannot transition job {job_id} from {job.status} to running")
            raise ValueError(f"Failed to mark job {job_id} as running")

    def mark_rebuild_job_succeeded(
        self,
        job_id: str,
        *,
        execution_id: str,
        node_count: int,
        edge_count: int,
        duration_ms: int,
    ) -> None:
        """
        Mark rebuild job as succeeded and persist success metadata atomatically.

        Args:
            job_id: The job identifier to update.
            execution_id: The unique identifier for this execution attempt.
            node_count: Number of nodes/assets in the rebuilt graph.
            edge_count: Number of edges/relationships in the rebuilt graph.
            duration_ms: Total rebuild duration in milliseconds.

        Raises:
            ValueError: If the job does not exist, is not running, or execution_id mismatches.
        """
        self._validate_non_negative_metrics(
            duration_ms=duration_ms,
            node_count=node_count,
            edge_count=edge_count,
        )

        # Flush any pending ORM changes to ensure UPDATE sees current state
        self.session.flush()

        # Atomic conditional update: only succeeds if job is RUNNING and execution_id matches
        now = datetime.now(timezone.utc)  # noqa: UP017
        stmt = (
            update(RebuildJobORM)
            .where(RebuildJobORM.job_id == job_id)
            .where(RebuildJobORM.status == RebuildJobStatus.RUNNING)
            .where(RebuildJobORM.execution_id == execution_id)
            .values(
                status=RebuildJobStatus.SUCCEEDED,
                completed_at=now,
                updated_at=now,
                node_count=node_count,
                edge_count=edge_count,
                duration_ms=duration_ms,
            )
        )
        result = self.session.execute(stmt)

        # If no rows were updated, check why
        if result.rowcount == 0:  # type: ignore[attr-defined]
            # Refresh to get current state (re-fetch from DB if needed)
            job = self.session.get(RebuildJobORM, job_id)
            if job is None:
                raise ValueError(f"Rebuild job {job_id} not found")

            if job.status != RebuildJobStatus.RUNNING:
                raise ValueError(f"Cannot transition job {job_id} from {job.status} to succeeded")
            if job.execution_id != execution_id:
                raise ValueError(f"Execution identity mismatch: {job.execution_id} != {execution_id}")
            raise ValueError(f"Failed to mark job {job_id} as succeeded")

    def mark_rebuild_job_cancel_requested(self, job_id: str) -> None:
        """
        Transition rebuild job to cancel_requested status.

        Args:
            job_id: The job identifier to update.

        Raises:
            ValueError: If the job does not exist or is not in a cancellable status.
        """
        # Flush any pending ORM changes to ensure UPDATE sees current state
        self.session.flush()

        # Atomic conditional update: only succeeds if job is in PENDING or RUNNING status
        now = datetime.now(timezone.utc)  # noqa: UP017
        stmt = (
            update(RebuildJobORM)
            .where(RebuildJobORM.job_id == job_id)
            .where(
                or_(
                    RebuildJobORM.status == RebuildJobStatus.PENDING,
                    RebuildJobORM.status == RebuildJobStatus.RUNNING,
                )
            )
            .values(
                status=RebuildJobStatus.CANCEL_REQUESTED,
                cancellation_requested_at=now,
                updated_at=now,
            )
        )
        result = self.session.execute(stmt)

        # If no rows were updated, check why
        if result.rowcount == 0:  # type: ignore[attr-defined]
            # Refresh to get current state (re-fetch from DB if needed)
            job = self.session.get(RebuildJobORM, job_id)
            if job is None:
                raise ValueError(f"Rebuild job {job_id} not found")

            if job.status == RebuildJobStatus.CANCEL_REQUESTED:
                # Already cancel_requested, idempotent success
                return

            raise ValueError(f"Cannot transition job {job_id} from {job.status} to cancel_requested")

    def mark_rebuild_job_cancelled(self, job_id: str, *, execution_id: str) -> None:
        """
        Mark rebuild job as cancelled and persist completion metadata.

        Args:
            job_id: The job identifier to update.
            execution_id: The unique identifier for this execution attempt.

        Raises:
            ValueError: If the job does not exist, is not cancel_requested, or execution_id mismatches.
        """
        # Flush any pending ORM changes to ensure UPDATE sees current state
        self.session.flush()

        # Atomic conditional update: only succeeds if:
        # 1. Job is in CANCEL_REQUESTED status
        # 2. execution_id matches
        now = datetime.now(timezone.utc)  # noqa: UP017
        stmt = (
            update(RebuildJobORM)
            .where(RebuildJobORM.job_id == job_id)
            .where(RebuildJobORM.status == RebuildJobStatus.CANCEL_REQUESTED)
            .where(RebuildJobORM.execution_id == execution_id)
            .values(
                status=RebuildJobStatus.CANCELLED,
                completed_at=now,
                updated_at=now,
            )
        )
        result = self.session.execute(stmt)

        # If no rows were updated, check why
        if result.rowcount == 0:  # type: ignore[attr-defined]
            # Refresh to get current state (re-fetch from DB if needed)
            job = self.session.get(RebuildJobORM, job_id)
            if job is None:
                raise ValueError(f"Rebuild job {job_id} not found")

            if job.status != RebuildJobStatus.CANCEL_REQUESTED:
                if job.status == RebuildJobStatus.CANCELLED:
                    # Already cancelled, idempotent success
                    return
                raise ValueError(f"Cannot transition job {job_id} from {job.status} to cancelled")
            if job.execution_id != execution_id:
                raise ValueError(f"Execution identity mismatch: {job.execution_id} != {execution_id}")

            raise ValueError(f"Failed to mark job {job_id} as cancelled")

    def mark_rebuild_job_failed(
        self,
        job_id: str,
        *,
        execution_id: str | None,
        details: RebuildFailureDetails,
    ) -> None:
        """
        Mark rebuild job as failed and persist sanitized failure metadata atomatically.

        Args:
            job_id: The job identifier to update.
            execution_id: The unique identifier for this execution attempt (required if running).
            failure_category: Sanitized failure category (max 64 chars).
            failure_message: Sanitized failure message (max 512 chars).
            duration_ms: Total rebuild duration in milliseconds.

        Raises:
            ValueError: If the job does not exist, is not in running/pending status,
                execution_id mismatches, or failure metadata exceeds bounds.
        """
        self._validate_failure_metadata(
            failure_category=details.failure_category,
            failure_message=details.failure_message,
        )
        self._validate_non_negative_metrics(duration_ms=details.duration_ms)

        # Flush any pending ORM changes to ensure UPDATE sees current state
        self.session.flush()

        # Atomic conditional update: only succeeds if job is RUNNING|PENDING and execution_id matches if RUNNING
        now = datetime.now(timezone.utc)  # noqa: UP017
        stmt = (
            update(RebuildJobORM)
            .where(RebuildJobORM.job_id == job_id)
            .where(
                or_(
                    # Transition from PENDING: no execution_id yet
                    RebuildJobORM.status == RebuildJobStatus.PENDING,
                    # Transition from RUNNING: execution_id must match
                    and_(
                        RebuildJobORM.status == RebuildJobStatus.RUNNING,
                        RebuildJobORM.execution_id == execution_id,
                    ),
                )
            )
            .values(
                status=RebuildJobStatus.FAILED,
                completed_at=now,
                updated_at=now,
                sanitized_failure_category=details.failure_category,
                sanitized_failure_message=details.failure_message,
                duration_ms=details.duration_ms,
            )
        )
        result = self.session.execute(stmt)

        # If no rows were updated, check why
        if result.rowcount == 0:  # type: ignore[attr-defined]
            # Refresh to get current state (re-fetch from DB if needed)
            job = self.session.get(RebuildJobORM, job_id)
            if job is None:
                raise ValueError(f"Rebuild job {job_id} not found")

            if job.status not in (RebuildJobStatus.RUNNING, RebuildJobStatus.PENDING):
                current_status = job.status.value if isinstance(job.status, RebuildJobStatus) else job.status
                raise ValueError(
                    f"Cannot transition job {job_id} from {current_status} to {RebuildJobStatus.FAILED.value}"
                )

            # If it's RUNNING, it must be an execution identity mismatch
            if job.status == RebuildJobStatus.RUNNING and job.execution_id != execution_id:
                raise ValueError(f"Execution identity mismatch: {job.execution_id} != {execution_id}")

            raise ValueError(f"Failed to mark job {job_id} as failed")

    def get_rebuild_job(self, job_id: str) -> RebuildJobORM | None:
        """
        Retrieve a rebuild job by its ID.

        Args:
            job_id: The job identifier to retrieve.

        Returns:
            RebuildJobORM | None: The job record if found, None otherwise.
        """
        return self.session.get(RebuildJobORM, job_id)

    def list_rebuild_jobs(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
        status: str | None = None,
    ) -> list[RebuildJobORM]:
        """
        List rebuild jobs ordered by created_at descending (most recent first).

        Args:
            limit: Optional maximum number of jobs to return.
            offset: Optional number of jobs to skip.
            status: Optional status filter (pending, running, succeeded, failed, cancelled).

        Returns:
            list[RebuildJobORM]: List of rebuild job records matching the filters.

        Raises:
            ValueError: If an invalid status value is provided.
        """
        self._validate_rebuild_job_status(status)
        stmt = select(RebuildJobORM).order_by(
            RebuildJobORM.created_at.desc(),
            RebuildJobORM.job_id.desc(),
        )
        if status is not None:
            stmt = stmt.where(RebuildJobORM.status == status)
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        return list(self.session.execute(stmt).scalars().all())

    def count_rebuild_jobs(self, *, status: str | None = None) -> int:
        """
        Count rebuild jobs matching the optional status filter before pagination.

        Args:
            status: Optional status filter (pending, running, succeeded, failed, cancelled).

        Returns:
            int: Total number of rebuild job records matching the filters.

        Raises:
            ValueError: If an invalid status value is provided.
        """
        self._validate_rebuild_job_status(status)
        stmt = select(func.count()).select_from(RebuildJobORM)
        if status is not None:
            stmt = stmt.where(RebuildJobORM.status == status)
        return int(self.session.execute(stmt).scalar_one())

    @staticmethod
    def _validate_rebuild_job_status(status: str | None) -> None:
        """Raise ValueError when the supplied rebuild job status is not valid."""
        if status is not None and status not in RebuildJobStatus.values():
            valid = RebuildJobStatus.values()
            raise ValueError(f"Invalid rebuild job status {status!r}. Must be one of: {valid}")

    def get_latest_successful_rebuild_job(self) -> RebuildJobORM | None:
        """
        Retrieve the most recent successfully completed rebuild job.

        Returns:
            RebuildJobORM | None: The most recent succeeded job record, or None.
        """
        stmt = (
            select(RebuildJobORM)
            .where(RebuildJobORM.status == RebuildJobStatus.SUCCEEDED)
            .order_by(RebuildJobORM.completed_at.desc(), RebuildJobORM.job_id.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    # Stage 5C.1: Recovery state tracking methods

    def update_rebuild_heartbeat(
        self,
        job_id: str,
        execution_id: str,
        worker_id: str,
    ) -> None:
        """Update the heartbeat timestamp for an active rebuild job."""
        if len(worker_id) > 64:
            raise ValueError(f"worker_id exceeds maximum length of 64 characters: {len(worker_id)} chars")

        self.session.flush()

        now = datetime.now(timezone.utc)  # noqa: UP017
        stmt = (
            update(RebuildJobORM)
            .where(RebuildJobORM.job_id == job_id)
            .where(RebuildJobORM.status == RebuildJobStatus.RUNNING)
            .where(RebuildJobORM.execution_id == execution_id)
            .where(
                or_(
                    RebuildJobORM.active_worker_id.is_(None),
                    RebuildJobORM.active_worker_id == worker_id,
                )
            )
            .values(
                active_worker_id=worker_id,
                last_heartbeat_at=now,
                updated_at=now,
            )
        )
        result = self.session.execute(stmt)

        if result.rowcount == 0:  # type: ignore[attr-defined]
            self._diagnose_heartbeat_failure(job_id, execution_id, worker_id)

    def _diagnose_heartbeat_failure(self, job_id: str, execution_id: str, worker_id: str) -> NoReturn:
        """Identify and raise the specific reason why a heartbeat update failed."""
        job = self.session.get(RebuildJobORM, job_id)
        if job is None:
            raise ValueError(f"Rebuild job {job_id} not found")

        # 1. Check for cancellation/terminal states
        self._raise_for_invalid_heartbeat_status(job)

        # 2. Check for identity/ownership conflicts
        self._raise_for_heartbeat_identity_conflict(job, execution_id, worker_id)

        # Fallback if somehow called incorrectly
        raise ValueError(f"Heartbeat update failed for job {job_id} for unknown reason")

    def _raise_for_invalid_heartbeat_status(self, job: RebuildJobORM) -> None:
        """Raise appropriate error if job status prevents heartbeat."""
        if job.status == RebuildJobStatus.RUNNING:
            return

        if job.status == RebuildJobStatus.CANCEL_REQUESTED:
            raise RebuildCancellationRequestedError(
                f"Heartbeat update failed for job {job.job_id}: cancellation has been requested"
            )

        current_status = job.status.value if isinstance(job.status, RebuildJobStatus) else str(job.status)
        raise ValueError(
            f"Cannot update heartbeat for job {job.job_id}: job status changed to {current_status} "
            "(job is no longer running)"
        )

    def _raise_for_heartbeat_identity_conflict(self, job: RebuildJobORM, execution_id: str, worker_id: str) -> None:
        """Raise appropriate error for execution or worker identity mismatch."""
        if job.execution_id != execution_id:
            raise ValueError(
                f"Heartbeat update failed for job {job.job_id}: execution identity mismatch "
                f"(current: {job.execution_id}, expected: {execution_id})"
            )

        if job.active_worker_id != worker_id:
            current_owner = job.active_worker_id
            raise ValueError(
                f"Cannot update heartbeat for job {job.job_id}: active worker is {current_owner}, not {worker_id}. "
                "Worker ownership has already been claimed."
            )

    def update_rebuild_checkpoint(self, job_id: str, execution_id: str, data: str | None) -> None:
        """
        Update the checkpoint_data field on a rebuild job record atomically.

        Args:
            job_id: The job identifier to update.
            execution_id: The unique identifier for this execution attempt.
            data: Checkpoint data (serialized JSON), or None to clear.

        Raises:
            ValueError: If the job does not exist, is not running, or execution_id mismatches.
        """
        # Flush any pending ORM changes to ensure UPDATE sees current state
        self.session.flush()

        # Atomic conditional update: only succeeds if execution_id matches and status is RUNNING
        now = datetime.now(timezone.utc)  # noqa: UP017
        stmt = (
            update(RebuildJobORM)
            .where(RebuildJobORM.job_id == job_id)
            .where(RebuildJobORM.status == RebuildJobStatus.RUNNING)
            .where(RebuildJobORM.execution_id == execution_id)
            .values(
                checkpoint_data=data,
                updated_at=now,
            )
        )
        result = self.session.execute(stmt)

        # If no rows were updated, check why
        if result.rowcount == 0:  # type: ignore[attr-defined]
            # Refresh to get current state (re-fetch from DB if needed)
            job = self.session.get(RebuildJobORM, job_id)
            if job is None:
                raise ValueError(f"Rebuild job {job_id} not found")

            if job.status != RebuildJobStatus.RUNNING:
                raise ValueError(f"Cannot update checkpoint for job {job_id} in {job.status} status")
            if job.execution_id != execution_id:
                raise ValueError(f"Execution identity mismatch: {job.execution_id} != {execution_id}")
            # This case shouldn't be reached if job exists, is RUNNING, and execution_id matches,
            # but we raise a generic error just in case of concurrent deletion.
            raise ValueError(f"Failed to update checkpoint for job {job_id}")

    def get_active_rebuild_state(self) -> RebuildJobORM | None:
        """
        Get the current authoritative rebuild state from the database.

        Returns the running job when exactly one is active, or None if no
        rebuild is currently active.

        Returns:
            The active rebuild job, or None if no job is running.

        Raises:
            ValueError: If multiple rebuild jobs are simultaneously in running
                status.
        """
        stmt = (
            select(RebuildJobORM)
            .where(RebuildJobORM.status == RebuildJobStatus.RUNNING)
            .order_by(RebuildJobORM.created_at.desc())
            # Fetch up to two rows to detect invalid multi-running state.
            .limit(2)
        )
        result = self.session.execute(stmt)
        running_jobs = list(result.scalars())
        if len(running_jobs) > 1:
            raise ValueError("Multiple rebuild jobs are in RUNNING state")
        if not running_jobs:
            return None
        return running_jobs[0]

    def get_last_successful_rebuild(self) -> RebuildJobORM | None:
        """
        Get the most recent successfully completed rebuild job.

        Returns:
            The most recent succeeded rebuild job, or None if no successful
            rebuild has been recorded.
        """
        return self.get_latest_successful_rebuild_job()

    def get_latest_rebuild_job(self) -> RebuildJobORM | None:
        """
        Get the most recent rebuild job regardless of status.

        This is used for metrics initialization to preserve terminal states
        across service restarts.

        Returns:
            The most recent rebuild job, or None if no jobs exist.
        """
        stmt = select(RebuildJobORM).order_by(RebuildJobORM.created_at.desc(), RebuildJobORM.job_id.desc()).limit(1)
        return self.session.execute(stmt).scalar_one_or_none()
