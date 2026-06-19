"""Protocol boundaries for repository-style data access."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session

from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import Asset, RegulatoryEvent

from .db_models import RebuildJobORM
from .repository import (
    LockStateSnapshot,
    LockWriteResult,
    RebuildCancellationRequestedError,
    RebuildFailureDetails,
    RelationshipRecord,
)


@runtime_checkable
class ICoordinationLockRepository(Protocol):
    """Protocol for distributed lock coordination repositories."""

    session: Session

    def acquire_lock(self, *, lock_name: str, holder_id: str, ttl_seconds: int) -> LockWriteResult:
        """Acquire or refresh a distributed lock in the database."""
        ...

    def refresh_lock(self, *, lock_name: str, holder_id: str, ttl_seconds: int) -> LockWriteResult:
        """Refresh a distributed lock in the database."""
        ...

    def release_lock(self, *, lock_name: str, holder_id: str) -> bool:
        """Release a distributed lock if held by the specified holder."""
        ...

    def get_lock_state(self, *, lock_name: str, holder_id: str) -> LockStateSnapshot:
        """Check the current state of a distributed lock and return a materialized snapshot."""
        ...


@runtime_checkable
class IAssetGraphRepository(Protocol):
    """Protocol for asset graph persistence and rebuild-job repositories."""

    session: Session

    def save_graph(self, graph: AssetRelationshipGraph) -> None:
        """Persist an AssetRelationshipGraph snapshot to the database."""
        ...

    def load_graph(self) -> AssetRelationshipGraph:
        """Reconstruct an in-memory asset relationship graph from persisted rows."""
        ...

    def replace_assets(self, assets: Iterable[Asset]) -> None:
        """Replace persisted assets with the supplied collection."""
        ...

    def replace_relationships_from_graph(self, relationships: dict[str, list[tuple[str, str, float]]]) -> None:
        """Replace all persisted relationships with directed adjacency data."""
        ...

    def replace_regulatory_events(self, events: Iterable[RegulatoryEvent]) -> None:
        """Replace all persisted regulatory events with the supplied collection."""
        ...

    def upsert_asset(self, asset: Asset) -> None:
        """Create or update the persistent record for a domain Asset."""
        ...

    def upsert_assets(self, assets: Iterable[Asset]) -> None:
        """Create or update multiple assets in a single repository session."""
        ...

    def list_assets(self) -> list[Asset]:
        """Retrieve all assets ordered by id."""
        ...

    def get_assets_map(self) -> dict[str, Asset]:
        """Return a mapping of asset id to the corresponding Asset domain object."""
        ...

    def get_asset_by_id(self, asset_id: str) -> Asset | None:
        """Return a single asset by its ID, or None if not found."""
        ...

    def delete_asset(self, asset_id: str) -> None:
        """Delete an asset and cascading relationships/events."""
        ...

    def add_or_update_relationship(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self, source_id: str, target_id: str, rel_type: str, strength: float, bidirectional: bool = False
    ) -> None:
        """Create or update an asset relationship and stage it on the repository session."""
        ...

    def list_relationships(self) -> list[RelationshipRecord]:
        """Retrieve all persisted relationships."""
        ...

    def get_relationship(self, source_id: str, target_id: str, rel_type: str) -> RelationshipRecord | None:
        """Return a single relationship by its composite key, or None if not found."""
        ...

    def delete_relationship(self, source_id: str, target_id: str, rel_type: str) -> None:
        """Delete a relationship by its composite key."""
        ...

    def upsert_regulatory_event(self, event: RegulatoryEvent) -> None:
        """Create or update a regulatory event."""
        ...

    def list_regulatory_events(self) -> list[RegulatoryEvent]:
        """Retrieve all regulatory events."""
        ...

    def delete_regulatory_event(self, event_id: str) -> None:
        """Delete a regulatory event."""
        ...

    def create_rebuild_job(self, *, requested_by: str, source: str | None = None) -> str:
        """Create a new pending rebuild job."""
        ...

    def update_rebuild_job_source(self, job_id: str, execution_id: str, source: str | None) -> None:
        """Update the source field of a rebuild job."""
        ...

    def mark_rebuild_job_running(self, job_id: str, execution_id: str) -> None:
        """Transition a job from PENDING to RUNNING."""
        ...

    def mark_rebuild_job_succeeded(  # pylint: disable=too-many-arguments
        self, job_id: str, *, execution_id: str, node_count: int, edge_count: int, duration_ms: int
    ) -> None:
        """Transition a job to SUCCEEDED and record metrics."""
        ...

    def mark_rebuild_job_cancel_requested(self, job_id: str) -> None:
        """Mark a job for cancellation."""
        ...

    def mark_rebuild_job_cancelled(self, job_id: str, *, execution_id: str) -> None:
        """Transition a job to CANCELLED."""
        ...

    def mark_rebuild_job_failed(self, job_id: str, *, execution_id: str | None, details: RebuildFailureDetails) -> None:
        """Transition a job to FAILED and record failure details."""
        ...

    def get_rebuild_job(self, job_id: str) -> RebuildJobORM | None:
        """Retrieve a rebuild job by its ID."""
        ...

    def list_rebuild_jobs(
        self, *, limit: int | None = None, offset: int | None = None, status: str | None = None
    ) -> list[RebuildJobORM]:
        """List rebuild jobs, optionally filtered by status."""
        ...

    def get_latest_successful_rebuild_job(self) -> RebuildJobORM | None:
        """Return the most recently completed SUCCEEDED job."""
        ...

    def update_rebuild_heartbeat(self, job_id: str, execution_id: str, worker_id: str) -> None:
        """Update the heartbeat timestamp for a running rebuild job."""
        ...

    def update_rebuild_checkpoint(self, job_id: str, execution_id: str, data: str | None) -> None:
        """Save an intermediate checkpoint for a running rebuild job."""
        ...

    def get_active_rebuild_state(self) -> RebuildJobORM | None:
        """Return the currently RUNNING or CANCEL_REQUESTED job, if any."""
        ...

    def get_last_successful_rebuild(self) -> RebuildJobORM | None:
        """Return the most recently completed SUCCEEDED job."""
        ...

    def get_latest_rebuild_job(self) -> RebuildJobORM | None:
        """Return the most recently created rebuild job."""
        ...


__all__ = [
    "IAssetGraphRepository",
    "ICoordinationLockRepository",
    "LockStateSnapshot",
    "LockWriteResult",
    "RebuildCancellationRequestedError",
]
