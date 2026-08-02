"""Tests for cross-process governed relationship cache freshness."""

from __future__ import annotations

import pytest

from api.services import relationship_index as relationship_index_service
from src.logic.asset_graph import AssetRelationshipGraph


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
