"""INSERT-only persistence helpers for GRAC v1 projection revisions.

Module for persisting relationship projections, providing utilities for
ID generation, timestamp normalization, foreign key error detection, and
ORM conversion functions for projection edges and revisions.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import NoReturn
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.data.db_models import RebuildJobORM
from src.data.relationship_assertion_db_models import (
    RelationshipProjectionEdgeORM,
    RelationshipProjectionPublicationORM,
    RelationshipProjectionRevisionORM,
)
from src.governance.relationship_assertion import ConcurrencyConflict, ValidationError
from src.logic.relationship_projection import (
    GovernedScope,
    ProjectionEdge,
    ProjectionRevision,
    canonicalize_governed_scopes,
)

UTC = timezone.utc


def _serialize_governed_scopes(scopes: Sequence[GovernedScope], purpose: str) -> str:
    """Encode the canonical scope metadata stored independently of edge rows."""
    canonical = canonicalize_governed_scopes(scopes, purpose)
    return json.dumps(
        [{"predicate_id": scope.predicate_id, "purpose": scope.purpose} for scope in canonical],
        separators=(",", ":"),
        sort_keys=True,
    )


def _deserialize_governed_scopes(raw: str, purpose: str) -> tuple[GovernedScope, ...]:
    """Decode stored scope metadata and reject malformed or non-canonical values."""
    try:
        values = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValidationError("projection revision governed_scopes is not valid JSON") from exc
    if not isinstance(values, list):
        raise ValidationError("projection revision governed_scopes must be a JSON array")
    try:
        scopes = tuple(GovernedScope(purpose=value["purpose"], predicate_id=value["predicate_id"]) for value in values)
    except (KeyError, TypeError) as exc:
        raise ValidationError("projection revision governed_scopes has invalid entries") from exc
    canonical = canonicalize_governed_scopes(scopes, purpose)
    if raw != _serialize_governed_scopes(canonical, purpose):
        raise ValidationError("projection revision governed_scopes is not canonical")
    return canonical


@dataclass(frozen=True)
class PersistProjectionRequest:
    """Inputs for INSERT-only persistence of a candidate projection revision."""

    revision: ProjectionRevision
    revision_id: str | None = None
    created_at: datetime | None = None
    edge_ids: Sequence[str] | None = None


@dataclass(frozen=True)
class PersistedProjectionRevision:
    """Stored projection revision identity plus domain revision payload."""

    revision_id: str
    created_at: datetime
    revision: ProjectionRevision
    edge_ids: tuple[str, ...]


def _new_id() -> str:
    """Generate a new unique identifier string for a projection or edge."""
    return str(uuid4())


def _as_utc(value: datetime | None) -> datetime | None:
    """Convert a datetime to UTC timezone, returning None if input is None."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _is_foreign_key_integrity_error(exc: IntegrityError) -> bool:
    """Determine if an IntegrityError is caused by a foreign key violation."""
    detail = str(getattr(exc, "orig", None) or exc).lower()
    return "foreign key" in detail or "foreignkeyviolation" in detail


def _raise_projection_persist_integrity_error(revision_id: str, exc: IntegrityError) -> NoReturn:
    """Translate projection insert IntegrityError into a domain exception."""
    if _is_foreign_key_integrity_error(exc):
        raise ValidationError(
            f"projection revision foreign-key violation for {revision_id} (check assertion_id references on edges)"
        ) from exc
    raise ConcurrencyConflict(f"projection revision insert conflicted for {revision_id}") from exc


def _projection_edge_orm(revision_id: str, edge_id: str, edge: ProjectionEdge) -> RelationshipProjectionEdgeORM:
    """Convert a ProjectionEdge domain object into its ORM representation."""
    return RelationshipProjectionEdgeORM(
        id=edge_id,
        revision_id=revision_id,
        source_id=edge.source_id,
        target_id=edge.target_id,
        edge_type=edge.edge_type,
        strength=edge.strength,
        direction=edge.direction,
        assertion_id=edge.assertion_id,
    )


def _projection_edge_from_orm(row: RelationshipProjectionEdgeORM) -> ProjectionEdge:
    """Convert an ORM row into a ProjectionEdge domain object."""
    return ProjectionEdge(
        source_id=row.source_id,
        target_id=row.target_id,
        edge_type=row.edge_type,
        strength=row.strength,
        direction=row.direction,
        assertion_id=row.assertion_id,
    )


def _resolve_persist_edge_ids(request: PersistProjectionRequest) -> list[str]:
    """Validate or generate edge IDs for a projection persist request."""
    revision = request.revision
    edge_ids = [_new_id() for _ in revision.edges] if request.edge_ids is None else list(request.edge_ids)
    if len(edge_ids) != len(revision.edges):
        raise ValidationError("edge_ids length must match revision.edges")
    if len(set(edge_ids)) != len(edge_ids):
        raise ValidationError("edge_ids must be unique")
    return edge_ids


def _projection_revision_orm(
    revision_id: str,
    revision: ProjectionRevision,
    created_at: datetime,
) -> RelationshipProjectionRevisionORM:
    """Convert a ProjectionRevision domain object into its ORM representation."""
    return RelationshipProjectionRevisionORM(
        id=revision_id,
        purpose=revision.purpose,
        effective_at=revision.effective_at,
        known_at=revision.known_at,
        contract_version=revision.contract_version,
        projector_version=revision.projector_version,
        edge_set_hash=revision.edge_set_hash,
        governed_scopes=_serialize_governed_scopes(revision.governed_scopes, revision.purpose),
        projection_hash=revision.projection_hash,
        created_at=created_at,
    )


def _require_projection_timestamps(
    row: RelationshipProjectionRevisionORM,
) -> tuple[datetime, datetime, datetime]:
    """Return UTC timestamps from a revision row or fail closed."""
    effective_at = _as_utc(row.effective_at)
    known_at = _as_utc(row.known_at)
    created_at = _as_utc(row.created_at)
    if effective_at is None:
        raise ValidationError("projection revision effective_at missing")
    if known_at is None:
        raise ValidationError("projection revision known_at missing")
    if created_at is None:
        raise ValidationError("projection revision created_at missing")
    return effective_at, known_at, created_at


def _domain_revision_from_orm(
    row: RelationshipProjectionRevisionORM,
    edges: tuple[ProjectionEdge, ...],
    governed_scopes: tuple[GovernedScope, ...],
) -> tuple[ProjectionRevision, datetime]:
    """Map a stored revision row plus edges/scopes into domain types."""
    effective_at, known_at, created_at = _require_projection_timestamps(row)
    revision = ProjectionRevision(
        purpose=row.purpose,
        effective_at=effective_at,
        known_at=known_at,
        contract_version=row.contract_version,
        projector_version=row.projector_version,
        edge_set_hash=row.edge_set_hash,
        projection_hash=row.projection_hash,
        edges=edges,
        governed_scopes=governed_scopes,
    )
    return revision, created_at


class ProjectionRevisionStore:
    """Session-bound INSERT-only writer/reader for projection revisions."""

    def __init__(self, session: Session, *, clock: Callable[[], datetime]) -> None:
        """Bind SQLAlchemy session and injectable clock."""
        self._session = session
        self._clock = clock

    def persist(self, request: PersistProjectionRequest) -> PersistedProjectionRevision:
        """INSERT a candidate projection revision and its edges."""
        revision = request.revision
        revision_id = request.revision_id or _new_id()
        created_at = _as_utc(request.created_at or self._clock())
        if created_at is None:
            raise ValidationError("created_at is required")
        edge_ids = _resolve_persist_edge_ids(request)
        try:
            with self._session.begin_nested():
                self._insert_rows(revision_id, revision, created_at, edge_ids)
        except IntegrityError as exc:
            _raise_projection_persist_integrity_error(revision_id, exc)
        return PersistedProjectionRevision(
            revision_id=revision_id,
            created_at=created_at,
            revision=revision,
            edge_ids=tuple(edge_ids),
        )

    def get(self, revision_id: str) -> PersistedProjectionRevision | None:
        """Load a persisted candidate revision and its ordered edges."""
        row = self._session.get(RelationshipProjectionRevisionORM, revision_id)
        if row is None:
            return None
        edge_rows = self._load_edge_rows(revision_id)
        edges = tuple(_projection_edge_from_orm(edge_row) for edge_row in edge_rows)
        governed_scopes = _deserialize_governed_scopes(row.governed_scopes, row.purpose)
        revision, created_at = _domain_revision_from_orm(row, edges, governed_scopes)
        return PersistedProjectionRevision(
            revision_id=row.id,
            created_at=created_at,
            revision=revision,
            edge_ids=tuple(edge_row.id for edge_row in edge_rows),
        )

    def get_with_single_edge(self, revision_id: str, projection_edge_id: str) -> PersistedProjectionRevision | None:
        """Load a persisted candidate revision and only the single requested edge."""
        row = self._session.get(RelationshipProjectionRevisionORM, revision_id)
        if row is None:
            return None
        edge_row = self._session.execute(
            select(RelationshipProjectionEdgeORM)
            .where(RelationshipProjectionEdgeORM.revision_id == revision_id)
            .where(RelationshipProjectionEdgeORM.id == projection_edge_id)
        ).scalar_one_or_none()
        if edge_row is None:
            return None
        edges = (_projection_edge_from_orm(edge_row),)
        governed_scopes = _deserialize_governed_scopes(row.governed_scopes, row.purpose)
        revision, created_at = _domain_revision_from_orm(row, edges, governed_scopes)
        return PersistedProjectionRevision(
            revision_id=row.id,
            created_at=created_at,
            revision=revision,
            edge_ids=(projection_edge_id,),
        )

    def latest_published_scopes(self, purpose: str) -> tuple[GovernedScope, ...]:
        """Load metadata from the latest successful publication for the purpose."""
        row = self._session.execute(
            select(RelationshipProjectionRevisionORM)
            .join(
                RelationshipProjectionPublicationORM,
                RelationshipProjectionPublicationORM.revision_id == RelationshipProjectionRevisionORM.id,
            )
            .where(RelationshipProjectionRevisionORM.purpose == purpose)
            .join(
                RebuildJobORM,
                RebuildJobORM.job_id == RelationshipProjectionPublicationORM.rebuild_job_id,
            )
            .where(RebuildJobORM.status == "succeeded")
            .order_by(
                RelationshipProjectionPublicationORM.published_at.desc(),
                RelationshipProjectionPublicationORM.rebuild_job_id.desc(),
                RelationshipProjectionPublicationORM.id.desc(),
            )
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            return ()
        return _deserialize_governed_scopes(row.governed_scopes, purpose)

    def _insert_rows(
        self,
        revision_id: str,
        revision: ProjectionRevision,
        created_at: datetime,
        edge_ids: Sequence[str],
    ) -> None:
        """Persist revision header and edge rows inside the current savepoint."""
        self._session.add(_projection_revision_orm(revision_id, revision, created_at))
        self._session.flush()
        for edge_id, edge in zip(edge_ids, revision.edges, strict=True):
            self._session.add(_projection_edge_orm(revision_id, edge_id, edge))
        self._session.flush()

    def _load_edge_rows(self, revision_id: str) -> list[RelationshipProjectionEdgeORM]:
        """Return projection edges for ``revision_id`` in deterministic order."""
        return list(
            self._session.execute(
                select(RelationshipProjectionEdgeORM)
                .where(RelationshipProjectionEdgeORM.revision_id == revision_id)
                .order_by(
                    RelationshipProjectionEdgeORM.source_id,
                    RelationshipProjectionEdgeORM.target_id,
                    RelationshipProjectionEdgeORM.edge_type,
                    RelationshipProjectionEdgeORM.strength,
                    RelationshipProjectionEdgeORM.direction,
                    RelationshipProjectionEdgeORM.assertion_id,
                    RelationshipProjectionEdgeORM.id,
                )
            )
            .scalars()
            .all()
        )
