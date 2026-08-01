"""Focused tests for governed relationship and visualization response metadata."""

from __future__ import annotations

from dataclasses import dataclass
from types import ModuleType, SimpleNamespace
from typing import cast

import pytest
from fastapi.testclient import TestClient

from api.routers import relationships as relationships_router
from api.routers import visualization as visualization_router
from src.data.relationship_assertion_repository import RelationshipAssertionRepository
from src.data.relationship_projection_persistence import PersistedProjectionRevision
from src.governance.relationship_assertion_contract import (
    ContractDocument,
    PredicatesDocument,
    TransitionsDocument,
)
from src.logic.asset_graph import AssetRelationshipGraph

from .api_assertion_test_support import (
    _assert_error_response,
)
from .api_assertion_test_support import (
    client as client,
)
from .api_assertion_test_support import (
    configure_graph_persistence as configure_graph_persistence,
)
from .api_assertion_test_support import (
    initialize_assertion_store as initialize_assertion_store,
)


@dataclass(frozen=True)
class _GovernanceRouteCase:
    """One public route that consumes governed relationship metadata."""

    route_module: ModuleType
    path: str


@pytest.mark.unit
def test_governance_contract_failure_propagates_from_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unexpected contract failures propagate instead of producing legacy metadata."""
    published = cast(
        PersistedProjectionRevision,
        SimpleNamespace(
            revision=SimpleNamespace(governed_scopes=(), edges=()),
            revision_id="revision-test",
        ),
    )
    legacy_settings = SimpleNamespace(database_url="unused")
    monkeypatch.setattr(relationships_router, "get_graph_lifecycle_settings", lambda: legacy_settings)
    monkeypatch.setattr(relationships_router, "resolve_hosted_graph_database_url", lambda _settings: None)
    monkeypatch.setattr(
        relationships_router,
        "resolve_durable_graph_persistence_url",
        lambda _url: "sqlite:///:memory:",
    )
    monkeypatch.setattr(
        relationships_router.RelationshipAssertionRepository,
        "latest_published_projection",
        lambda _repository, _purpose: published,
    )

    def fail_contract_load() -> None:
        """Simulate an unexpected governed-contract failure."""
        raise RuntimeError("contract load failed")

    monkeypatch.setattr(relationships_router, "load_contract_bundle", fail_contract_load)

    with pytest.raises(RuntimeError, match="contract load failed"):
        relationships_router.load_governed_relationship_index(AssetRelationshipGraph())


@pytest.mark.unit
def test_runtime_graph_replacement_invalidates_index_while_contract_stays_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh runtime graph reloads governance while reusing the immutable contract bundle."""
    published = cast(
        PersistedProjectionRevision,
        SimpleNamespace(
            revision=SimpleNamespace(governed_scopes=(), edges=()),
            revision_id="revision-test",
        ),
    )
    settings = SimpleNamespace(asset_graph_database_url="unused", database_url=None)
    monkeypatch.setattr(relationships_router, "get_graph_lifecycle_settings", lambda: settings)
    monkeypatch.setattr(
        relationships_router,
        "resolve_durable_graph_persistence_url",
        lambda _url: "sqlite:///:memory:",
    )
    bundle = relationships_router.load_contract_bundle()
    contract_loads = 0
    projection_loads = 0

    def recording_load() -> tuple[ContractDocument, PredicatesDocument, TransitionsDocument]:
        """Count contract loads while returning the validated test bundle."""
        nonlocal contract_loads
        contract_loads += 1
        return bundle

    def load_projection(
        _repository: RelationshipAssertionRepository,
        _purpose: str,
    ) -> PersistedProjectionRevision:
        """Count published projection loads while returning the bounded test revision."""
        nonlocal projection_loads
        projection_loads += 1
        return published

    monkeypatch.setattr(relationships_router, "load_contract_bundle", recording_load)
    monkeypatch.setattr(
        relationships_router.RelationshipAssertionRepository,
        "latest_published_projection",
        load_projection,
    )
    first_graph = AssetRelationshipGraph()
    replacement_graph = AssetRelationshipGraph()

    assert relationships_router.load_governed_relationship_index(first_graph) == {}
    assert relationships_router.load_governed_relationship_index(first_graph) == {}
    assert relationships_router.load_governed_relationship_index(replacement_graph) == {}
    assert projection_loads == 2
    assert contract_loads == 1


@pytest.mark.unit
@pytest.mark.parametrize(
    "case",
    [
        _GovernanceRouteCase(relationships_router, "/api/relationships"),
        _GovernanceRouteCase(visualization_router, "/api/visualization"),
    ],
    ids=["relationships", "visualization"],
)
def test_governance_failure_reaches_route_error_handler(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    case: _GovernanceRouteCase,
) -> None:
    """Public graph routes convert governance-loader failures to bounded 500s."""

    def fail_governance_load(_graph: AssetRelationshipGraph) -> None:
        """Simulate a governance persistence or contract outage."""
        raise RuntimeError("governance load failed")

    monkeypatch.setattr(case.route_module, "load_governed_relationship_index", fail_governance_load)

    response = client.get(case.path)
    _assert_error_response(response, 500, "An internal error occurred. Please try again later.")


@pytest.mark.unit
@pytest.mark.parametrize("path", ["/api/relationships", "/api/visualization"])
def test_invalid_governance_url_returns_service_unavailable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    """Malformed configured governance persistence fails closed with a 503."""
    settings = SimpleNamespace(asset_graph_database_url="not a database url", database_url=None)
    monkeypatch.setattr(relationships_router, "get_graph_lifecycle_settings", lambda: settings)

    response = client.get(path)

    _assert_error_response(response, 503, "Graph persistence database is misconfigured")


@pytest.mark.unit
def test_bidirectional_governed_edge_indexes_both_runtime_directions() -> None:
    """A canonical bidirectional projection enriches both runtime graph directions."""
    edge = SimpleNamespace(
        source_id="BOND",
        target_id="ISSUER",
        edge_type="issuer_link",
        direction="bidirectional",
        assertion_id="assertion-test",
    )
    published = SimpleNamespace(
        revision_id="revision-test",
        revision=SimpleNamespace(
            edges=(edge,),
            governed_scopes=(SimpleNamespace(predicate_id="predicate-test"),),
        ),
    )
    predicates = SimpleNamespace(
        predicates=(
            SimpleNamespace(
                id="predicate-test",
                projection=SimpleNamespace(edge_type="issuer_link"),
            ),
        )
    )

    index = relationships_router._published_relationship_index(
        cast(PersistedProjectionRevision, published),
        cast(PredicatesDocument, predicates),
    )

    assert index[("BOND", "ISSUER", "issuer_link")] == index[("ISSUER", "BOND", "issuer_link")]
    assert index[("ISSUER", "BOND", "issuer_link")]["assertion_id"] == "assertion-test"


@pytest.mark.unit
def test_legacy_relationship_and_visualization_payloads_omit_new_optional_fields(client: TestClient) -> None:
    """Legacy graph payloads omit every optional governance field."""
    relationships = client.get("/api/relationships")
    assert relationships.status_code == 200
    if relationships.json():
        row = relationships.json()[0]
        assert "assertion_id" not in row
        assert "governance_status" not in row
        assert "revision_id" not in row
        assert "scope_refs" not in row

    visualization = client.get("/api/visualization")
    assert visualization.status_code == 200
    if visualization.json()["edges"]:
        edge = visualization.json()["edges"][0]
        assert "assertion_id" not in edge
        assert "governance_status" not in edge
        assert "revision_id" not in edge
        assert "scope_refs" not in edge
