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
    RelationshipRecord,
)


@runtime_checkable
class ICoordinationLockRepository(Protocol):
    """Protocol for distributed lock coordination repositories."""

    session: Session

    def acquire_lock(self, *, lock_name: str, holder_id: str, ttl_seconds: int) -> LockWriteResult:
        """Docstring."""
        ...

    def refresh_lock(self, *, lock_name: str, holder_id: str, ttl_seconds: int) -> LockWriteResult:
        """Docstring."""
        ...

    def release_lock(self, *, lock_name: str, holder_id: str) -> bool:
        """Docstring."""
        ...

    def get_lock_state(self, *, lock_name: str, holder_id: str) -> LockStateSnapshot:
        """Docstring."""
        ...


@runtime_checkable
class IAssetGraphRepository(Protocol):
    """Protocol for asset graph persistence and rebuild-job repositories."""

    session: Session

    def save_graph(self, graph: AssetRelationshipGraph) -> None:
        """Docstring."""
        ...

    def load_graph(self) -> AssetRelationshipGraph:
        """Docstring."""
        ...

    def replace_assets(self, assets: Iterable[Asset]) -> None:
        """Docstring."""
        ...

    def replace_relationships_from_graph(self, relationships: dict[str, list[tuple[str, str, float]]]) -> None:
        """Docstring."""
        ...

    def replace_regulatory_events(self, events: Iterable[RegulatoryEvent]) -> None:
        """Docstring."""
        ...

    def upsert_asset(self, asset: Asset) -> None:
        """Docstring."""
        ...

    def upsert_assets(self, assets: Iterable[Asset]) -> None:
        """Docstring."""
        ...

    def list_assets(self) -> list[Asset]:
        """Docstring."""
        ...

    def get_assets_map(self) -> dict[str, Asset]:
        """Docstring."""
        ...

    def get_asset_by_id(self, asset_id: str) -> Asset | None:
        """Docstring."""
        ...

    def delete_asset(self, asset_id: str) -> None:
        """Docstring."""
        ...

    def add_or_update_relationship(self, *args: object, **kwargs: object) -> None:
        """Docstring."""
        ...

    def list_relationships(self) -> list[RelationshipRecord]:
        """Docstring."""
        ...

    def get_relationship(self, source_id: str, target_id: str, rel_type: str) -> RelationshipRecord | None:
        """Docstring."""
        ...

    def delete_relationship(self, source_id: str, target_id: str, rel_type: str) -> None:
        """Docstring."""
        ...

    def upsert_regulatory_event(self, event: RegulatoryEvent) -> None:
        """Docstring."""
        ...

    def list_regulatory_events(self) -> list[RegulatoryEvent]:
        """Docstring."""
        ...

    def delete_regulatory_event(self, event_id: str) -> None:
        """Docstring."""
        ...

    def create_rebuild_job(self, *, requested_by: str, source: str | None = None) -> str:
        """Docstring."""
        ...

    def mark_rebuild_job_running(self, job_id: str, execution_id: str) -> None:
        """Docstring."""
        ...

    def mark_rebuild_job_succeeded(
        self,
        job_id: str,
        *,
        execution_id: str,
        node_count: int | None = None,
        edge_count: int | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Docstring."""
        ...

    def mark_rebuild_job_cancel_requested(self, job_id: str) -> None:
        """Docstring."""
        ...

    def mark_rebuild_job_cancelled(self, job_id: str, *, execution_id: str) -> None:
        """Docstring."""
        ...

    def mark_rebuild_job_failed(
        self,
        job_id: str,
        *,
        execution_id: str,
        error: Exception | None = None,
        sanitized_failure_category: str | None = None,
        sanitized_failure_message: str | None = None,
    ) -> None:
        """Docstring."""
        ...

    def get_rebuild_job(self, job_id: str) -> RebuildJobORM | None:
        """Docstring."""
        ...

    def list_rebuild_jobs(self, *, limit: int | None = None, offset: int = 0) -> list[RebuildJobORM]:
        """Docstring."""
        ...


__all__ = [
    "IAssetGraphRepository",
    "ICoordinationLockRepository",
    "LockStateSnapshot",
    "LockWriteResult",
    "RebuildCancellationRequestedError",
]
