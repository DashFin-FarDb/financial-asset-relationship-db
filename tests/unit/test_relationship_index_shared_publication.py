"""Tests for cross-process governed relationship cache freshness."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy.engine import Engine

from api.services import relationship_index as relationship_index_service
from src.data.relationship_projection_persistence import PersistedProjectionRevision
from src.governance import relationship_assertion_contract as contract_models
from src.logic.asset_graph import AssetRelationshipGraph
from src.logic.relationship_projection import GovernedScope, ProjectionEdge, ProjectionRevision

UTC = timezone.utc
NOW = datetime(2026, 8, 2, 6, 0, tzinfo=UTC)
PURPOSE = "financial_graph_current_view"


@pytest.mark.unit
def test_governance_stays_consistent_with_graph_snapshot_across_publications(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Peer publication does not advance governance until the graph object is replaced.

    A warm peer that detects a newer published revision ID from persistence must not
    serve governance metadata from that newer publication while still returning edges
    from the pre-sync graph snapshot.  Governance is only refreshed when the
    in-memory graph object is replaced (i.e. after ``sync_with_latest_rebuild``
    completes and ``synchronize_runtime_graph`` installs a new instance) or when the
    local generation advances via explicit invalidation.  This guarantees that
    ``assertion_id`` and ``revision_id`` on returned edges always correspond to the
    publication the current graph was built from.
    """
    graph_v1 = AssetRelationshipGraph()
    current_revision_id = "revision-v1"
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

    def load_index() -> relationship_index_service.GovernedRelationshipIndex:
        """Load the index for the current revision from persistence."""
        nonlocal persistence_loads
        persistence_loads += 1
        return indexes[current_revision_id]

    monkeypatch.setattr(
        relationship_index_service,
        "_load_governed_relationship_index_from_persistence",
        load_index,
    )
    relationship_index_service.invalidate_governed_relationship_index_cache()

    try:
        # Initial warm-up: governance from revision-v1 is loaded and cached.
        assert relationship_index_service.load_governed_relationship_index(graph_v1) == indexes["revision-v1"]
        assert relationship_index_service.load_governed_relationship_index(graph_v1) == indexes["revision-v1"]
        assert persistence_loads == 1

        # Simulate another backend process committing a new publication (revision-v2).
        # This process receives no local invalidation signal and retains its warm cache.
        # Governance must NOT advance to revision-v2 while graph_v1 is still in use,
        # even if persistence now reports revision-v2 as the latest.
        current_revision_id = "revision-v2"

        assert relationship_index_service.load_governed_relationship_index(graph_v1) == indexes["revision-v1"]
        assert relationship_index_service.load_governed_relationship_index(graph_v1) == indexes["revision-v1"]
        _msg = "governance must not refresh from a new publication while the graph object is unchanged"
        assert persistence_loads == 1, _msg

        # Simulate sync_with_latest_rebuild completing: a new graph object is installed.
        # Governance now refreshes against the new graph, picking up revision-v2.
        graph_v2 = AssetRelationshipGraph()

        assert relationship_index_service.load_governed_relationship_index(graph_v2) == indexes["revision-v2"]
        assert relationship_index_service.load_governed_relationship_index(graph_v2) == indexes["revision-v2"]
        assert persistence_loads == 2

        # An in-flight request that still holds graph_v1 must retain revision-v1
        # governance even after graph_v2 has been loaded into the cache.
        assert relationship_index_service.load_governed_relationship_index(graph_v1) == indexes["revision-v1"]
        assert persistence_loads == 2
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


def _predicate(predicate_id: str) -> contract_models.PredicateSpec:
    """Build one governed predicate sharing a runtime edge type with its peer."""
    return contract_models.PredicateSpec(
        id=predicate_id,
        subject_type="Asset",
        object_type="Asset",
        method_ids=["test.relationship.resolution@1"],
        projection=contract_models.ProjectionSpec(
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
    predicates = contract_models.PredicatesDocument(
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
