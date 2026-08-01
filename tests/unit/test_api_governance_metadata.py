"""Focused tests for governed relationship and visualization response metadata."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from types import ModuleType, SimpleNamespace
from typing import cast

import pytest
from fastapi.testclient import TestClient

from api.routers import graph_admin
from api.routers import relationships as relationships_router
from api.routers import visualization as visualization_router
from api.services import relationship_index as relationship_index_service
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

pytest_plugins = ("tests.unit.api_assertion_test_support",)


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
    monkeypatch.setattr(relationship_index_service, "get_graph_lifecycle_settings", lambda: legacy_settings)
    monkeypatch.setattr(relationship_index_service, "resolve_hosted_graph_database_url", lambda _settings: None)
    monkeypatch.setattr(
        relationship_index_service,
        "resolve_durable_graph_persistence_url",
        lambda _url: "sqlite:///:memory:",
    )
    monkeypatch.setattr(
        relationship_index_service.RelationshipAssertionRepository,
        "latest_published_projection",
        lambda _repository, _purpose: published,
    )

    def fail_contract_load() -> None:
        """Simulate an unexpected governed-contract failure."""
        raise RuntimeError("contract load failed")

    monkeypatch.setattr(relationship_index_service, "load_contract_bundle", fail_contract_load)

    with pytest.raises(RuntimeError, match="contract load failed"):
        relationship_index_service.load_governed_relationship_index(AssetRelationshipGraph())


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
    monkeypatch.setattr(relationship_index_service, "get_graph_lifecycle_settings", lambda: settings)
    monkeypatch.setattr(
        relationship_index_service,
        "resolve_durable_graph_persistence_url",
        lambda _url: "sqlite:///:memory:",
    )
    bundle = relationship_index_service.load_contract_bundle()
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

    monkeypatch.setattr(relationship_index_service, "load_contract_bundle", recording_load)
    monkeypatch.setattr(
        relationship_index_service.RelationshipAssertionRepository,
        "latest_published_projection",
        load_projection,
    )
    first_graph = AssetRelationshipGraph()
    replacement_graph = AssetRelationshipGraph()

    assert relationship_index_service.load_governed_relationship_index(first_graph) == {}
    assert relationship_index_service.load_governed_relationship_index(first_graph) == {}
    assert relationship_index_service.load_governed_relationship_index(replacement_graph) == {}
    assert projection_loads == 2
    assert contract_loads == 1


@pytest.mark.unit
def test_cache_primed_read_is_refreshed_after_admin_publication(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """A cached metadata read is invalidated by successful admin publication."""
    graph = AssetRelationshipGraph()
    graph.relationships = {"BOND": [("ISSUER", "issuer_link", 0.9)]}
    monkeypatch.setattr(relationships_router, "get_graph", lambda: graph)
    monkeypatch.setattr(visualization_router, "get_graph", lambda: graph)

    state = {"assertion_id": "assertion-v1", "revision_id": "revision-v1"}

    def load_published_index() -> relationship_index_service.GovernedRelationshipIndex:
        """Return the currently published relationship metadata for cache behavior checks."""
        return {
            ("BOND", "ISSUER", "issuer_link"): {
                "assertion_id": state["assertion_id"],
                "governance_status": "governed",
                "revision_id": state["revision_id"],
                "scope_refs": ["financial.bond.issuer_reference@1"],
            }
        }

    monkeypatch.setattr(
        relationship_index_service,
        "_load_governed_relationship_index_from_persistence",
        load_published_index,
    )
    relationship_index_service.invalidate_governed_relationship_index_cache()

    first = client.get("/api/relationships")
    assert first.status_code == 200
    assert first.json()[0]["assertion_id"] == "assertion-v1"
    assert first.json()[0]["revision_id"] == "revision-v1"

    first_visualization = client.get("/api/visualization")
    assert first_visualization.status_code == 200
    assert first_visualization.json()["edges"][0]["assertion_id"] == "assertion-v1"
    assert first_visualization.json()["edges"][0]["revision_id"] == "revision-v1"
    state["assertion_id"] = "assertion-v2"
    state["revision_id"] = "revision-v2"

    @contextmanager
    def fake_publication_transactions(*_args: object, **_kwargs: object):
        """Return a bounded publication context with no database dependency."""
        yield object(), None

    class _FakeAssertionRepository:
        """Minimal publication repository double for finalize flow tests."""

        def __init__(self, _session: object) -> None:
            pass

        def next_publication_time(self, _purpose: str) -> datetime:
            return datetime.now(tz=timezone.utc)

        def finalize_projection_publication(self, *_args: object, **_kwargs: object) -> None:
            return None

    publication_graph = AssetRelationshipGraph()
    publication_graph.relationships = graph.relationships

    monkeypatch.setattr(graph_admin, "_verify_execution_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(graph_admin, "_publication_transactions", fake_publication_transactions)
    monkeypatch.setattr(graph_admin, "_guard_publication_lock", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(graph_admin, "RelationshipAssertionRepository", _FakeAssertionRepository)
    monkeypatch.setattr(graph_admin, "stage_graph_snapshot", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        graph_admin,
        "_prepare_projection_publication",
        lambda *_args, **_kwargs: (
            SimpleNamespace(),
            publication_graph,
            SimpleNamespace(asset_count=1, relationship_count=1),
        ),
    )

    graph_admin._finalize_rebuild_success(
        session_factory=lambda: None,
        job_id="job-test",
        execution_id="exec-test",
        graph=graph,
        source="sample",
        job_started_at=0.0,
        lock_lost=threading.Event(),
        cancel_event=threading.Event(),
    )

    second = client.get("/api/relationships")
    assert second.status_code == 200
    assert second.json()[0]["assertion_id"] == "assertion-v2"
    assert second.json()[0]["revision_id"] == "revision-v2"

    second_visualization = client.get("/api/visualization")
    assert second_visualization.status_code == 200
    assert second_visualization.json()["edges"][0]["assertion_id"] == "assertion-v2"
    assert second_visualization.json()["edges"][0]["revision_id"] == "revision-v2"

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
    monkeypatch.setattr(relationship_index_service, "get_graph_lifecycle_settings", lambda: settings)

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

    index = relationship_index_service._published_relationship_index(
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
