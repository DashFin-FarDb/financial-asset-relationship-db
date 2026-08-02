"""Governed relationship index loading and cache management."""

from __future__ import annotations

from functools import lru_cache
from threading import Lock
from typing import Literal, TypeAlias, TypedDict

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.engine import Engine

from src.data.database import create_engine_from_url, create_session_factory
from src.data.db_models import RebuildJobORM
from src.data.relationship_assertion_db_models import (
    RelationshipProjectionPublicationORM,
    RelationshipProjectionRevisionORM,
)
from src.data.relationship_assertion_repository import RelationshipAssertionRepository
from src.data.relationship_projection_persistence import PersistedProjectionRevision
from src.data.repository import session_scope
from src.governance.relationship_assertion_contract import PredicatesDocument, load_contract_bundle
from src.logic.asset_graph import AssetRelationshipGraph
from src.logic.relationship_projection import ProjectionEdge

from ..graph_lifecycle_providers import (
    GraphPersistenceInvalidUrlError,
    GraphPersistenceNonDurableError,
    GraphPersistenceNotConfiguredError,
    get_graph_lifecycle_settings,
    resolve_durable_graph_persistence_url,
    resolve_hosted_graph_database_url,
)

_GRAC_CURRENT_PURPOSE = "financial_graph_current_view"
_cache_generation_lock = Lock()


class _CacheGeneration:
    """Mutable cache-generation state guarded by the cache-generation lock."""

    def __init__(self) -> None:
        self.value = 0


_cache_generation = _CacheGeneration()


class GovernanceMetadata(TypedDict):
    """Strict governance fields attached to one published relationship edge."""

    assertion_id: str
    governance_status: Literal["governed"]
    revision_id: str
    scope_refs: list[str]


GovernedRelationshipIndex: TypeAlias = dict[tuple[str, str, str], GovernanceMetadata]


def _current_cache_generation() -> int:
    """Return the current governed relationship index cache generation."""
    with _cache_generation_lock:
        return _cache_generation.value


@lru_cache(maxsize=1)
def _load_contract_predicates() -> PredicatesDocument:
    """Load validated predicates once from the immutable pinned contract bundle."""
    _contract, predicates, _transitions = load_contract_bundle()
    return predicates


def _dispose_engine(engine: Engine | None) -> None:
    """Dispose an optional governance persistence engine after each bounded read."""
    if engine is not None:
        engine.dispose()


def _resolve_governance_persistence_url() -> str:
    """Resolve the durable graph database used by governed relationship reads."""
    settings = get_graph_lifecycle_settings()
    hosted_url = resolve_hosted_graph_database_url(settings)
    legacy_url = getattr(settings, "database_url", None) if not hasattr(settings, "asset_graph_database_url") else None
    return resolve_durable_graph_persistence_url(hosted_url or legacy_url)


def _scope_refs_by_edge_type(
    published: PersistedProjectionRevision,
    predicates: PredicatesDocument,
) -> dict[str, list[str]]:
    """Index the published governed predicate scopes by projected edge type."""
    predicates_by_id = {predicate.id: predicate for predicate in predicates.predicates}
    edge_type_scopes: dict[str, list[str]] = {}
    for scope in published.revision.governed_scopes:
        predicate = predicates_by_id.get(scope.predicate_id)
        if predicate is not None:
            edge_type_scopes.setdefault(predicate.projection.edge_type, []).append(scope.predicate_id)
    return edge_type_scopes


def _add_governed_edge(
    index: GovernedRelationshipIndex,
    edge: ProjectionEdge,
    metadata: GovernanceMetadata,
) -> None:
    """Add forward and, when governed as bidirectional, reverse index entries."""
    index[(edge.source_id, edge.target_id, edge.edge_type)] = metadata
    if edge.direction == "bidirectional":
        index[(edge.target_id, edge.source_id, edge.edge_type)] = metadata


def _published_relationship_index(
    published: PersistedProjectionRevision,
    predicates: PredicatesDocument,
) -> GovernedRelationshipIndex:
    """Build governance response metadata for one published projection revision."""
    edge_type_scopes = _scope_refs_by_edge_type(published, predicates)
    index: GovernedRelationshipIndex = {}
    for edge in published.revision.edges:
        metadata: GovernanceMetadata = {
            "assertion_id": edge.assertion_id,
            "governance_status": "governed",
            "revision_id": published.revision_id,
            "scope_refs": sorted(set(edge_type_scopes.get(edge.edge_type, []))),
        }
        _add_governed_edge(index, edge, metadata)
    return index


def _latest_published_revision_id_from_persistence() -> str | None:
    """Read the shared latest successful publication revision used as a cache version."""
    engine: Engine | None = None
    try:
        engine = create_engine_from_url(_resolve_governance_persistence_url())
        session_factory = create_session_factory(engine)
        with session_scope(session_factory) as session:
            return session.execute(
                select(RelationshipProjectionPublicationORM.revision_id)
                .join(
                    RelationshipProjectionRevisionORM,
                    RelationshipProjectionRevisionORM.id == RelationshipProjectionPublicationORM.revision_id,
                )
                .join(
                    RebuildJobORM,
                    RebuildJobORM.job_id == RelationshipProjectionPublicationORM.rebuild_job_id,
                )
                .where(RelationshipProjectionRevisionORM.purpose == _GRAC_CURRENT_PURPOSE)
                .where(RebuildJobORM.status == "succeeded")
                .order_by(
                    RelationshipProjectionPublicationORM.published_at.desc(),
                    RelationshipProjectionPublicationORM.rebuild_job_id.desc(),
                    RelationshipProjectionPublicationORM.id.desc(),
                )
                .limit(1)
            ).scalar_one_or_none()
    except GraphPersistenceInvalidUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph persistence database is misconfigured",
        ) from exc
    except (GraphPersistenceNotConfiguredError, GraphPersistenceNonDurableError):
        return None
    finally:
        _dispose_engine(engine)


def _load_governed_relationship_index_from_persistence() -> GovernedRelationshipIndex:
    """Load governed metadata from durable assertion projection persistence."""
    engine: Engine | None = None
    try:
        engine = create_engine_from_url(_resolve_governance_persistence_url())
        session_factory = create_session_factory(engine)
        with session_scope(session_factory) as session:
            repository = RelationshipAssertionRepository(session)
            published = repository.latest_published_projection(_GRAC_CURRENT_PURPOSE)
            if published is None:
                return {}
            predicates = _load_contract_predicates()
            return _published_relationship_index(published, predicates)
    except GraphPersistenceInvalidUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph persistence database is misconfigured",
        ) from exc
    except (GraphPersistenceNotConfiguredError, GraphPersistenceNonDurableError):
        return {}
    finally:
        _dispose_engine(engine)


@lru_cache(maxsize=1)
def _load_governed_relationship_index(
    _graph: AssetRelationshipGraph,
    _published_revision_id: str | None,
    _generation: int,
) -> GovernedRelationshipIndex:
    """Load governed metadata for one graph, shared publication, and local generation."""
    return _load_governed_relationship_index_from_persistence()


def load_governed_relationship_index(graph: AssetRelationshipGraph) -> GovernedRelationshipIndex:
    """Return metadata cached against the shared latest publication revision."""
    published_revision_id = _latest_published_revision_id_from_persistence()
    return _load_governed_relationship_index(
        graph,
        published_revision_id,
        _current_cache_generation(),
    )


def invalidate_governed_relationship_index_cache() -> None:
    """Advance the cache generation and clear entries after publication writes."""
    with _cache_generation_lock:
        _cache_generation.value += 1
        _load_governed_relationship_index.cache_clear()
