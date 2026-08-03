"""Regression tests for publication-bound governed relationship metadata."""

from __future__ import annotations

from collections.abc import Generator
from typing import cast

import pytest
from fastapi import HTTPException, status

from api.services import relationship_index
from src.logic.asset_graph import AssetRelationshipGraph


@pytest.fixture(autouse=True)
def _reset_relationship_index_caches() -> Generator[None, None, None]:
    """Keep cache and weak graph bindings isolated between tests."""
    relationship_index.invalidate_governed_relationship_index_cache()
    with relationship_index._runtime_graph_bindings_lock:  # pylint: disable=protected-access
        relationship_index._runtime_graph_bindings.clear()  # pylint: disable=protected-access
    yield
    relationship_index.invalidate_governed_relationship_index_cache()
    with relationship_index._runtime_graph_bindings_lock:  # pylint: disable=protected-access
        relationship_index._runtime_graph_bindings.clear()  # pylint: disable=protected-access


def test_managed_graph_fails_closed_until_latest_publication_is_synchronized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A peer cannot attach a newer publication to its older graph snapshot."""
    graph = AssetRelationshipGraph()
    monkeypatch.setattr(
        relationship_index,
        "_runtime_graph_publication_binding",
        lambda _graph: (True, "job-old"),
    )
    monkeypatch.setattr(
        relationship_index,
        "_latest_published_projection_binding_from_persistence",
        lambda: ("job-new", "revision-new"),
    )

    with pytest.raises(HTTPException) as exc_info:
        relationship_index.load_governed_relationship_index(graph)

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert exc_info.value.detail == "Graph publication synchronization is pending"


def test_unbound_managed_startup_graph_omits_optional_governance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Startup graphs not derived from a governed publication remain readable."""
    graph = AssetRelationshipGraph()
    monkeypatch.setattr(
        relationship_index,
        "_runtime_graph_publication_binding",
        lambda _graph: (True, None),
    )

    def unexpected_publication_lookup() -> tuple[str, str]:
        """Fail if an unbound startup graph probes governed publication state."""
        raise AssertionError("unexpected publication lookup")

    monkeypatch.setattr(
        relationship_index,
        "_latest_published_projection_binding_from_persistence",
        unexpected_publication_lookup,
    )

    assert relationship_index.load_governed_relationship_index(graph) == {}


def test_managed_graph_checks_shared_version_on_every_read_but_caches_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shared publication freshness is checked without rebuilding a stable index."""
    graph = AssetRelationshipGraph()
    version_checks = 0
    revision_loads = 0
    expected = {
        ("BOND", "ISSUER", "corporate_link"): {
            "assertion_id": "assertion-1",
            "governance_status": "governed",
            "revision_id": "revision-1",
            "scope_refs": ["financial.bond.issuer_reference@1"],
        }
    }

    monkeypatch.setattr(
        relationship_index,
        "_runtime_graph_publication_binding",
        lambda _graph: (True, "job-1"),
    )

    def latest_binding() -> tuple[str, str]:
        """Count the shared publication-version checks."""
        nonlocal version_checks
        version_checks += 1
        return "job-1", "revision-1"

    def load_revision(_revision_id: str) -> relationship_index.GovernedRelationshipIndex:
        """Count full metadata index loads for the immutable revision."""
        nonlocal revision_loads
        revision_loads += 1
        return cast(relationship_index.GovernedRelationshipIndex, expected)

    monkeypatch.setattr(
        relationship_index,
        "_latest_published_projection_binding_from_persistence",
        latest_binding,
    )
    monkeypatch.setattr(
        relationship_index,
        "_load_governed_relationship_index_for_revision",
        load_revision,
    )

    assert relationship_index.load_governed_relationship_index(graph) == expected
    assert relationship_index.load_governed_relationship_index(graph) == expected
    assert version_checks == 2
    assert revision_loads == 1


def test_stale_in_flight_graph_remains_bound_to_its_original_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An old graph object fails closed after the lifecycle advances to a new job."""
    graph = AssetRelationshipGraph()
    bindings = iter(((True, "job-old"), (True, "job-old")))
    publications = iter((("job-old", "revision-old"), ("job-new", "revision-new")))

    def runtime_binding(_graph: AssetRelationshipGraph) -> tuple[bool, str | None]:
        """Return the next runtime binding and fail clearly if the test is exhausted."""
        try:
            return next(bindings)
        except StopIteration as exc:
            raise AssertionError("unexpected runtime binding lookup") from exc

    def latest_publication() -> tuple[str, str] | None:
        """Return the next publication binding and fail clearly if the test is exhausted."""
        try:
            return next(publications)
        except StopIteration as exc:
            raise AssertionError("unexpected publication binding lookup") from exc

    monkeypatch.setattr(
        relationship_index,
        "_runtime_graph_publication_binding",
        runtime_binding,
    )
    monkeypatch.setattr(
        relationship_index,
        "_latest_published_projection_binding_from_persistence",
        latest_publication,
    )
    monkeypatch.setattr(
        relationship_index,
        "_load_governed_relationship_index_for_revision",
        lambda revision_id: cast(
            relationship_index.GovernedRelationshipIndex,
            {
                ("BOND", "ISSUER", "corporate_link"): {
                    "assertion_id": "assertion-old",
                    "governance_status": "governed",
                    "revision_id": revision_id,
                    "scope_refs": ["financial.bond.issuer_reference@1"],
                }
            },
        ),
    )

    first = relationship_index.load_governed_relationship_index(graph)
    assert first[("BOND", "ISSUER", "corporate_link")]["revision_id"] == "revision-old"

    with pytest.raises(HTTPException, match="synchronization is pending"):
        relationship_index.load_governed_relationship_index(graph)


@pytest.mark.parametrize(
    "error",
    [
        relationship_index.GraphPersistenceNotConfiguredError("not configured"),
        relationship_index.GraphPersistenceNonDurableError("non-durable"),
    ],
)
def test_latest_publication_binding_omits_optional_governance_without_durable_persistence(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    """Optional, unconfigured, or non-durable governance persistence yields no binding."""

    def raise_error() -> None:
        raise error

    monkeypatch.setattr(relationship_index, "_governance_session_factory", raise_error)

    assert relationship_index._latest_published_projection_binding_from_persistence() is None


def test_latest_publication_binding_still_fails_closed_for_invalid_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A genuinely misconfigured persistence URL remains a 503, not a silent omission."""

    def raise_error() -> None:
        raise relationship_index.GraphPersistenceInvalidUrlError("invalid url")

    monkeypatch.setattr(relationship_index, "_governance_session_factory", raise_error)

    with pytest.raises(HTTPException) as exc_info:
        relationship_index._latest_published_projection_binding_from_persistence()

    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert exc_info.value.detail == "Graph persistence database is misconfigured"


def test_unmanaged_graph_retains_isolated_loader_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test and tool graphs without lifecycle ownership keep the bounded legacy path."""
    graph = AssetRelationshipGraph()
    calls = 0

    monkeypatch.setattr(
        relationship_index,
        "_runtime_graph_publication_binding",
        lambda _graph: (False, None),
    )

    def load_unmanaged() -> relationship_index.GovernedRelationshipIndex:
        """Count loads through the unmanaged compatibility path."""
        nonlocal calls
        calls += 1
        return {}

    monkeypatch.setattr(
        relationship_index,
        "_load_governed_relationship_index_from_persistence",
        load_unmanaged,
    )

    assert relationship_index.load_governed_relationship_index(graph) == {}
    assert relationship_index.load_governed_relationship_index(graph) == {}
    assert calls == 1
