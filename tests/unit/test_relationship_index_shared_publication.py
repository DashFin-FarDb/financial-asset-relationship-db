"""Tests for cross-process governed relationship cache freshness."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy.engine import Engine

from api.services import relationship_index as relationship_index_service
from src.data.relationship_projection_persistence import PersistedProjectionRevision
from src.governance.relationship_assertion_contract import (
    PredicateSpec,
    PredicatesDocument,
    ProjectionSpec,
)
from src.logic.asset_graph import AssetRelationshipGraph
from src.logic.relationship_projection import GovernedScope, ProjectionEdge, ProjectionRevision

UTC = timezone.utc
NOW = datetime(2026, 8, 2, 6, 0, tzinfo=UTC)
PURPOSE = "financial_graph_current_view"


@pytest.mark.unit
def test_shared_publication_revision_advances_warm_reader_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A peer publication changes the cache key without process-local invalidation."""
    graph = AssetRelationshipGraph()
    current_revision_id = "revision-v1"
    revision_checks = 0
    persistence_loads = 0

    indexes: dict[str, relationship_index_service.GovernedRelationshipIndex] = {
        "revision-v1": {
            ("BOND", "ISSUER", "issuer_link"): {
                "assertion_id": "assertion-v1",
                "governance_status": "governed",
                "revision_id": "revision-v1",
                "scope_refs": ["financial.bond.issuer_reference@1"],
            }
        },
        "revision-v2": {
            ("BOND", "ISSUER", "issuer_link"): {
                "assertion_id": "assertion-v2",
                "governance_status": "governed",
                "revision_id": "revision-v2",
                "scope_refs": ["financial.bond.issuer_reference@1"],
            }
        },
    }

    def latest_revision_id() -> str:
        """Return the publication version visible through shared persistence."""
        nonlocal revision_checks
        revision_checks += 1
        return current_revision_id

    def load_index() -> relationship_index_service.GovernedRelationshipIndex:
        """Load the index associated with the currently published revision."""
        nonlocal persistence_loads
        persistence_loads += 1
        return indexes[current_revision_id]

    monkeypatch.setattr(
        relationship_index_service,
        "_latest_published_revision_id_from_persistence",
        latest_revision_id,
    )
    monkeypatch.setattr(
        relationship_index_service,
        "_load_governed_relationship_index_from_persistence",
        load_index,
    )
    relationship_index_service.invalidate_governed_relationship_index_cache()

    try:
        assert relationship_index_service.load_governed_relationship_index(graph) == indexes["revision-v1"]
        assert relationship_index_service.load_governed_relationship_index(graph) == indexes["revision-v1"]
        assert persistence_loads == 1

        # Simulate another backend process committing a new publication. This
        # process receives no local invalidation signal and retains its warm LRU.
        current_revision_id = "revision-v2"

        assert relationship_index_service.load_governed_relationship_index(graph) == indexes["revision-v2"]
        assert relationship_index_service.load_governed_relationship_index(graph) == indexes["revision-v2"]
        assert persistence_loads == 2
        assert revision_checks == 4
    finally:
        relationship_index_service.invalidate_governed_relationship_index_cache()


@pytest.mark.unit
def test_persistence_runtime_reuses_engine_and_disposes_on_url_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hot-path version probes reuse pooling while runtime URL changes stay bounded."""
    engines = [Mock(spec=Engine), Mock(spec=Engine)]
    factories = [Mock(name="factory-one"), Mock(name="factory-two")]
    created_urls: list[str] = []

    def create_engine(persistence_url: str) -> Engine:
        """Return a distinct fake engine for each configured URL."""
        created_urls.append(persistence_url)
        return engines[len(created_urls) - 1]

    def create_factory(engine: Engine) -> Mock:
        """Return the factory associated with the supplied fake engine."""
        return factories[engines.index(engine)]

    relationship_index_service._reset_governance_persistence_runtime()
    monkeypatch.setattr(relationship_index_service, "create_engine_from_url", create_engine)
    monkeypatch.setattr(relationship_index_service, "create_session_factory", create_factory)

    try:
        first = relationship_index_service._session_factory_for_url("postgresql://graph-one")
        repeated = relationship_index_service._session_factory_for_url("postgresql://graph-one")

        assert first is factories[0]
        assert repeated is first
        assert created_urls == ["postgresql://graph-one"]
        engines[0].dispose.assert_not_called()

        second = relationship_index_service._session_factory_for_url("postgresql://graph-two")

        assert second is factories[1]
        assert created_urls == ["postgresql://graph-one", "postgresql://graph-two"]
        engines[0].dispose.assert_called_once_with()
        engines[1].dispose.assert_not_called()
    finally:
        relationship_index_service._reset_governance_persistence_runtime()

    engines[1].dispose.assert_called_once_with()


def _predicate(predicate_id: str) -> PredicateSpec:
    """Build one governed predicate sharing a runtime edge type with its peer."""
    return PredicateSpec(
        id=predicate_id,
        subject_type="Asset",
        object_type="Asset",
        method_ids=["test.relationship.resolution@1"],
        projection=ProjectionSpec(
            edge_type="corporate_link",
            strength="0.8",
            direction="subject_to_object",
            purpose=PURPOSE,
        ),
        conflict_key=["subject_id", "object_id", "method_id"],
    )


@pytest.mark.unit
def test_scope_refs_follow_each_edge_assertion_predicate() -> None:
    """Shared edge types do not merge unrelated governed predicate scopes."""
    predicates = PredicatesDocument(
        predicates=[
            _predicate("predicate-a"),
            _predicate("predicate-b"),
        ]
    )
    revision = ProjectionRevision(
        purpose=PURPOSE,
        effective_at=NOW,
        known_at=NOW,
        contract_version="grac.v1",
        projector_version="projector.v2",
        edge_set_hash="a" * 64,
        projection_hash="b" * 64,
        edges=(
            ProjectionEdge(
                "BOND-1",
                "ISSUER-1",
                "corporate_link",
                "0.8",
                "subject_to_object",
                "assertion-a",
            ),
            ProjectionEdge(
                "BOND-2",
                "ISSUER-2",
                "corporate_link",
                "0.8",
                "subject_to_object",
                "assertion-b",
            ),
        ),
        governed_scopes=(
            GovernedScope(PURPOSE, "predicate-a"),
            GovernedScope(PURPOSE, "predicate-b"),
        ),
    )
    published = PersistedProjectionRevision(
        revision_id="revision-v1",
        created_at=NOW,
        revision=revision,
        edge_ids=("edge-a", "edge-b"),
    )

    index = relationship_index_service._published_relationship_index(
        published,
        predicates,
        {
            "assertion-a": "predicate-a",
            "assertion-b": "predicate-b",
        },
    )

    assert index[("BOND-1", "ISSUER-1", "corporate_link")]["scope_refs"] == ["predicate-a"]
    assert index[("BOND-2", "ISSUER-2", "corporate_link")]["scope_refs"] == ["predicate-b"]
