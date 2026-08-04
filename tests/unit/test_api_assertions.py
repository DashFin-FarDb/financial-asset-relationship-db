"""Focused tests for protected governed assertion command APIs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from api.auth import User
from api.main import app
from api.routers import assertions as assertions_router
from src.data.relationship_assertion_repository import RelationshipAssertionRepository

# Autouse fixtures are imported directly (rather than via `pytest_plugins`) so
# their autouse behavior stays scoped to this module instead of leaking into
# every test in the session (`pytest_plugins` registers fixtures
# session-wide even when declared in a test module). The `client` fixture is
# redeclared locally instead of imported, since importing it would collide
# with the `client` parameter name used throughout this module's tests.
from .api_assertion_test_support import (
    _assert_error_response,
    _decision_payload,
    _headers,
    _proposal_payload,
    _supersession_headers,
    _token,
    configure_graph_persistence,
    initialize_assertion_store,
    seed_users,
)

# `configure_graph_persistence`, `initialize_assertion_store`, and `seed_users` are
# pytest autouse fixtures used implicitly by every test in this module. Reference
# them here (rather than a per-import noqa comment) so the import stays a single,
# lint-stable block instead of flip-flopping between merged/split import styles.
_ = (configure_graph_persistence, initialize_assertion_store, seed_users)


@pytest.fixture
def client() -> TestClient:
    """Return a FastAPI test client."""
    return TestClient(app)


@dataclass(frozen=True)
class _DecisionAuthorizationCase:
    """One protected decision authorization expectation."""

    proposer: str
    actor: str
    to_state: str
    expected_status: int


@pytest.mark.unit
def test_assertion_proposal_requires_authentication(client: TestClient) -> None:
    """Proposal commands reject anonymous callers."""
    assertion_id = str(uuid4())
    response = client.post("/api/assertions", json=_proposal_payload(assertion_id))
    assert response.status_code == 401


@pytest.mark.unit
def test_proposal_propagates_correlation_id(client: TestClient) -> None:
    """Authenticated command responses preserve the request correlation identifier."""
    headers = _headers(_token("proposer_a"))
    headers["X-Correlation-ID"] = "corr-assertion-api"

    response = client.post(
        "/api/assertions",
        json=_proposal_payload(str(uuid4())),
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["event"]["correlation_id"] == "corr-assertion-api"


@pytest.mark.unit
def test_idempotent_reuse_and_foreign_reuse_rejection(client: TestClient) -> None:
    """Equivalent reuse is reported only for the proposer of record."""
    assertion_id = str(uuid4())
    owner_headers = _headers(_token("proposer_a"))
    payload = _proposal_payload(assertion_id)

    first = client.post("/api/assertions", json=payload, headers=owner_headers)
    assert first.status_code == 200
    assert first.json()["idempotent_reuse"] is False
    event_id = first.json()["event"]["event_id"]

    second = client.post("/api/assertions", json=payload, headers=owner_headers)
    assert second.status_code == 200
    assert second.json()["idempotent_reuse"] is True
    assert second.json()["event"]["event_id"] == event_id

    foreign = client.post("/api/assertions", json=payload, headers=_headers(_token("proposer_b")))
    assert foreign.status_code == 409


@pytest.mark.unit
@pytest.mark.parametrize(
    "case",
    [
        _DecisionAuthorizationCase("proposer_a", "proposer_a", "Accepted", 403),
        _DecisionAuthorizationCase("admin", "admin", "Accepted", 409),
        _DecisionAuthorizationCase("proposer_a", "proposer_b", "Withdrawn", 409),
    ],
    ids=["reviewer-boundary", "same-principal", "foreign-withdrawal"],
)
def test_decision_authorization_matrix(client: TestClient, case: _DecisionAuthorizationCase) -> None:
    """Decision routes enforce reviewer, actor-separation, and ownership rules."""
    assertion_id = str(uuid4())
    owner_headers = _headers(_token(case.proposer))
    create = client.post("/api/assertions", json=_proposal_payload(assertion_id), headers=owner_headers)
    assert create.status_code == 200

    decision = client.post(
        f"/api/assertions/{assertion_id}/decisions",
        json=_decision_payload(case.to_state, 1, "test decision"),
        headers=_headers(_token(case.actor)),
    )
    assert decision.status_code == case.expected_status


@pytest.mark.unit
def test_supersession_conflict_rolls_back_successor_write(client: TestClient) -> None:
    """A stale supersession conflict rolls back every successor write."""
    predecessor_id = str(uuid4())
    successor_id = str(uuid4())
    owner_headers = _headers(_token("proposer_a"))
    reviewer_token = _token("admin")
    reviewer_headers = _headers(reviewer_token)

    create = client.post("/api/assertions", json=_proposal_payload(predecessor_id), headers=owner_headers)
    assert create.status_code == 200
    accept = client.post(
        f"/api/assertions/{predecessor_id}/decisions",
        json=_decision_payload("Accepted", 1, "accept"),
        headers=reviewer_headers,
    )
    assert accept.status_code == 200

    supersede = client.post(
        f"/api/assertions/{predecessor_id}/supersessions",
        json={
            "expected_sequence": 1,
            "rationale": "supersede predecessor",
            "accept_rationale": "accept successor",
            "successor_proposal": _proposal_payload(successor_id),
        },
        headers=_supersession_headers(reviewer_token, _token("proposer_b")),
    )
    assert supersede.status_code == 409

    predecessor_history = client.get(f"/api/assertions/{predecessor_id}/history")
    assert predecessor_history.status_code == 200
    assert [row["sequence"] for row in predecessor_history.json()["events"]] == [1, 2]

    successor_read = client.get(f"/api/assertions/{successor_id}")
    assert successor_read.status_code == 404


@pytest.mark.unit
def test_self_supersession_maps_to_conflict(client: TestClient) -> None:
    """Self-supersession is a bounded 409 rather than an unhandled domain error."""
    assertion_id = str(uuid4())
    owner_headers = _headers(_token("proposer_a"))
    reviewer_token = _token("admin")
    reviewer_headers = _headers(reviewer_token)
    assert (
        client.post("/api/assertions", json=_proposal_payload(assertion_id), headers=owner_headers).status_code == 200
    )
    assert (
        client.post(
            f"/api/assertions/{assertion_id}/decisions",
            json=_decision_payload("Accepted", 1, "accept"),
            headers=reviewer_headers,
        ).status_code
        == 200
    )

    response = client.post(
        f"/api/assertions/{assertion_id}/supersessions",
        json={
            "expected_sequence": 2,
            "rationale": "invalid self-supersession",
            "accept_rationale": "accept successor",
            "successor_proposal": _proposal_payload(assertion_id),
        },
        headers=_supersession_headers(reviewer_token, _token("proposer_b")),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "self-supersession is forbidden"


@pytest.mark.unit
def test_unexpected_command_failure_is_sanitized(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unexpected repository failures become generic 500 responses."""

    def fail_proposal(*_args: object, **_kwargs: object) -> None:
        """Simulate an unexpected persistence failure containing private detail."""
        raise RuntimeError("private persistence detail")

    monkeypatch.setattr(RelationshipAssertionRepository, "propose", fail_proposal)
    response = client.post(
        "/api/assertions",
        json=_proposal_payload(str(uuid4())),
        headers=_headers(_token("proposer_a")),
    )

    _assert_error_response(response, 500, "An internal error occurred. Please try again later.")


@pytest.mark.unit
def test_unknown_decision_and_supersession_return_not_found(client: TestClient) -> None:
    """Commands targeting an absent predecessor return the contracted 404."""
    assertion_id = str(uuid4())
    reviewer_token = _token("admin")
    reviewer_headers = _headers(reviewer_token)

    decision = client.post(
        f"/api/assertions/{assertion_id}/decisions",
        json=_decision_payload("Accepted", 1, "accept"),
        headers=reviewer_headers,
    )
    supersession = client.post(
        f"/api/assertions/{assertion_id}/supersessions",
        json={
            "expected_sequence": 1,
            "rationale": "supersede predecessor",
            "accept_rationale": "accept successor",
            "successor_proposal": _proposal_payload(str(uuid4())),
        },
        headers=_supersession_headers(reviewer_token, _token("proposer_b")),
    )

    assert decision.status_code == 404
    assert supersession.status_code == 404


@pytest.mark.unit
def test_supersession_requires_header_proposal_credential(client: TestClient) -> None:
    """Supersession rejects missing, malformed, and body-carried proposer credentials."""
    predecessor_id = str(uuid4())
    reviewer_token = _token("admin")
    proposer_token = _token("proposer_b")
    payload = {
        "expected_sequence": 1,
        "rationale": "supersede predecessor",
        "accept_rationale": "accept successor",
        "successor_proposal": _proposal_payload(str(uuid4())),
    }

    missing = client.post(
        f"/api/assertions/{predecessor_id}/supersessions",
        json=payload,
        headers=_headers(reviewer_token),
    )
    malformed_headers = _headers(reviewer_token)
    malformed_headers["X-Proposal-Authorization"] = proposer_token
    malformed = client.post(
        f"/api/assertions/{predecessor_id}/supersessions",
        json=payload,
        headers=malformed_headers,
    )
    legacy_payload = dict(payload)
    legacy_payload["proposal_bearer_token"] = proposer_token
    body_credential = client.post(
        f"/api/assertions/{predecessor_id}/supersessions",
        json=legacy_payload,
        headers=_supersession_headers(reviewer_token, proposer_token),
    )

    assert missing.status_code == 401
    assert malformed.status_code == 401
    assert missing.headers["WWW-Authenticate"] == "Bearer"
    assert malformed.headers["WWW-Authenticate"] == "Bearer"
    assert body_credential.status_code == 422


@pytest.mark.unit
def test_invalid_proposal_contract_returns_unprocessable_entity(client: TestClient) -> None:
    """Request validation rejects values outside the frozen confidence vocabulary."""
    payload = _proposal_payload(str(uuid4()))
    payload["confidence_status"] = "unsupported"

    response = client.post(
        "/api/assertions",
        json=payload,
        headers=_headers(_token("proposer_a")),
    )

    assert response.status_code == 422


@pytest.mark.unit
def test_assertion_store_does_not_fall_back_in_development(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Development keeps requiring an explicit durable graph database URL."""
    settings = SimpleNamespace(
        asset_graph_database_url=None,
        database_url=os.environ["DATABASE_URL"],
        env="development",
        vercel_env="development",
    )
    monkeypatch.setattr(assertions_router, "get_graph_lifecycle_settings", lambda: settings)

    response = client.get(f"/api/assertions/{uuid4()}")

    _assert_error_response(response, 503, "Graph persistence database not configured")


@pytest.mark.unit
@pytest.mark.parametrize("deployment_env", ["preview", "staging"])
def test_assertion_store_uses_hosted_database_fallback(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    deployment_env: str,
) -> None:
    """Preview and staging use the supported durable application database fallback."""
    settings = SimpleNamespace(
        asset_graph_database_url=None,
        database_url=os.environ["DATABASE_URL"],
        env=deployment_env,
        vercel_env=deployment_env,
    )
    monkeypatch.setattr(assertions_router, "get_graph_lifecycle_settings", lambda: settings)

    response = client.get(f"/api/assertions/{uuid4()}")

    assert response.status_code == 404


@pytest.mark.unit
def test_invalid_assertion_persistence_url_maps_to_service_unavailable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed graph persistence configuration produces a bounded 503."""
    settings = SimpleNamespace(asset_graph_database_url="not a database url", database_url=None)
    monkeypatch.setattr(assertions_router, "get_graph_lifecycle_settings", lambda: settings)

    response = client.get(f"/api/assertions/{uuid4()}")

    _assert_error_response(response, 503, "Graph persistence database is misconfigured")


@pytest.mark.unit
def test_decision_operator_audit_receives_request(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reviewer authorization receives request metadata for security auditing."""
    assertion_id = str(uuid4())
    assert (
        client.post(
            "/api/assertions",
            json=_proposal_payload(assertion_id),
            headers=_headers(_token("proposer_a")),
        ).status_code
        == 200
    )
    audited_paths: list[str] = []

    def allow_operator(*, current_user: User, settings: object, request: Request) -> User:
        """Capture the request supplied to the operator authorization boundary."""
        audited_paths.append(request.url.path)
        return current_user

    monkeypatch.setattr(assertions_router, "get_current_rebuild_operator_user", allow_operator)
    response = client.post(
        f"/api/assertions/{assertion_id}/decisions",
        json=_decision_payload("Accepted", 1, "accept"),
        headers=_headers(_token("admin")),
    )

    assert response.status_code == 200
    assert audited_paths == [f"/api/assertions/{assertion_id}/decisions"]


@pytest.mark.unit
def test_get_published_edge_explanation_success(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exact publication-owned edge returns 200 with the correct envelope and bitemporal bounds."""
    from datetime import datetime, timezone

    from src.data.relationship_assertion_repository import PersistedProjectionRevision, PublishedProjectionRevision
    from src.governance.relationship_assertion import Assertion, AssertionAsOf, AssertionEvent
    from src.logic.relationship_projection import GovernedScope, ProjectionEdge, ProjectionRevision

    now = datetime.now(tz=timezone.utc)

    edge = ProjectionEdge(
        source_id="BOND",
        target_id="ISSUER",
        edge_type="corporate_link",
        strength="0.9",
        direction="canonical",
        assertion_id="assertion-test",
    )
    revision = ProjectionRevision(
        purpose="financial_graph_current_view",
        effective_at=now,
        known_at=now,
        contract_version="contract.v1",
        projector_version="projector.v1",
        edge_set_hash="0" * 64,
        projection_hash="1" * 64,
        edges=(edge,),
        governed_scopes=(
            GovernedScope(purpose="financial_graph_current_view", predicate_id="financial.bond.issuer_reference@1"),
        ),
    )
    persisted = PersistedProjectionRevision(
        revision_id="revision-test",
        created_at=now,
        revision=revision,
        edge_ids=("projection-edge-test",),
    )
    published = PublishedProjectionRevision(
        persisted=persisted,
        publication_id="pub-test",
        rebuild_job_id="job-test",
        execution_id="exec-test",
        published_at=now,
    )

    get_as_of_calls = 0
    assertion_obj = Assertion(
        assertion_id="assertion-test",
        predicate_id="financial.bond.issuer_reference@1",
        subject_id="BOND",
        object_id="ISSUER",
        method_id="bond.issuer_id.resolution@1",
        proposition="test",
        confidence_status="assessed",
        confidence_bp=100,
        confidence_type="type",
        confidence_method="method",
        effective_from=now,
        effective_to=None,
        recorded_at=now,
    )
    event_obj = AssertionEvent(
        event_id="event-test",
        assertion_id="assertion-test",
        sequence=1,
        from_state=None,
        to_state="Accepted",
        authority="acceptor",
        actor_id="admin",
        rationale="test",
        policy_version="contract.v1",
        recorded_at=now,
    )
    as_of = AssertionAsOf(
        assertion=assertion_obj,
        state="Accepted",
        events=(event_obj,),
        evidence_links=(),
        known_at=now,
        effective_at=now,
    )

    def mock_get_published_edge(
        _self: object, pub_id: str, edge_id: str
    ) -> tuple[PublishedProjectionRevision, ProjectionEdge] | None:
        """Return the published projection revision and edge for a given publication and edge ID.

        Returns a tuple of PublishedProjectionRevision and ProjectionEdge if the publication ID and edge ID match the test values, otherwise returns None.
        """
        if pub_id == "pub-test" and edge_id == "projection-edge-test":
            return published, edge
        return None

    def mock_get_as_of(
        _self: object, assertion_id: str, known_at: datetime, effective_at: datetime | None
    ) -> AssertionAsOf | None:
        """Retrieve the assertion state as of the specified known and effective timestamps.

        Increments the get_as_of_calls counter, validates parameters against the expected 'now' timestamp, and returns the predefined AssertionAsOf object.
        """
        nonlocal get_as_of_calls
        get_as_of_calls += 1
        assert known_at == now
        assert effective_at == now
        return as_of

    monkeypatch.setattr(RelationshipAssertionRepository, "get_published_edge", mock_get_published_edge)
    monkeypatch.setattr(RelationshipAssertionRepository, "get_as_of", mock_get_as_of)
    response = client.get("/api/publications/pub-test/edges/projection-edge-test/explanation")
    assert response.status_code == 200
    data = response.json()
    assert data["publication"]["publication_id"] == "pub-test"
    assert data["edge"]["projection_edge_id"] == "projection-edge-test"
    assert data["assertion"]["explanation"]["assertion_id"] == "assertion-test"
    assert get_as_of_calls == 1


@pytest.mark.unit
def test_get_published_edge_explanation_unknown_publication_returns_404(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown publication returns bounded 404."""
    monkeypatch.setattr(RelationshipAssertionRepository, "get_published_edge", lambda _self, pub_id, edge_id: None)
    response = client.get("/api/publications/unknown-pub/edges/edge-1/explanation")
    assert response.status_code == 404
    assert response.json()["detail"] == "unknown publication_id or projection_edge_id"


@pytest.mark.unit
def test_get_published_edge_explanation_wrong_edge_returns_404(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Edge belonging to another publication returns indistinguishable 404."""
    from datetime import datetime, timezone

    from src.data.relationship_assertion_repository import PersistedProjectionRevision, PublishedProjectionRevision
    from src.logic.relationship_projection import ProjectionEdge, ProjectionRevision

    now = datetime.now(tz=timezone.utc)
    edge = ProjectionEdge(
        source_id="BOND",
        target_id="ISSUER",
        edge_type="corporate_link",
        strength="0.9",
        direction="canonical",
        assertion_id="assertion-test",
    )


"""Test module for relationship assertion API, verifying published edge retrieval and explanation endpoints."""
    revision = ProjectionRevision(
        purpose="financial_graph_current_view",
        effective_at=now,
        known_at=now,
        contract_version="contract.v1",
        projector_version="projector.v1",
        edge_set_hash="0" * 64,
        projection_hash="1" * 64,
        edges=(edge,),
        governed_scopes=(),
    )
    persisted = PersistedProjectionRevision(
        revision_id="revision-test",
        created_at=now,
        revision=revision,
        edge_ids=("projection-edge-test",),
    )
    published = PublishedProjectionRevision(
        persisted=persisted,
        publication_id="pub-test",
        rebuild_job_id="job-test",
        execution_id="exec-test",
        published_at=now,
    )

    def mock_get_published_edge(
        _self: object, pub_id: str, edge_id: str
    ) -> tuple[PublishedProjectionRevision, ProjectionEdge] | None:
        """Mock get_published_edge to return the expected published projection revision and edge when provided correct IDs."""
        if pub_id == "pub-test" and edge_id == "projection-edge-test":
            return published, edge
        return None

    monkeypatch.setattr(RelationshipAssertionRepository, "get_published_edge", mock_get_published_edge)

    response = client.get("/api/publications/pub-test/edges/wrong-edge-id/explanation")
    assert response.status_code == 404
    assert response.json()["detail"] == "unknown publication_id or projection_edge_id"


@pytest.mark.unit
 def test_get_published_edge_explanation_strict_zip_mismatch_returns_503(
     client: TestClient,
     monkeypatch: pytest.MonkeyPatch,
 ) -> None:
     """Strict-zip mismatch (edge_ids and revision.edges mismatch) returns 503."""
     from datetime import datetime, timezone

     from src.data.relationship_assertion_repository import PersistedProjectionRevision, PublishedProjectionRevision
     from src.logic.relationship_projection import ProjectionEdge, ProjectionRevision

     now = datetime.now(tz=timezone.utc)
    edge = ProjectionEdge(
        source_id="BOND",
        target_id="ISSUER",
        edge_type="corporate_link",
        strength="0.9",
        direction="canonical",
        assertion_id="assertion-test",
    )
    revision = ProjectionRevision(
        purpose="financial_graph_current_view",
        effective_at=now,
        known_at=now,
        contract_version="contract.v1",
        projector_version="projector.v1",
        edge_set_hash="0" * 64,
        projection_hash="1" * 64,
        edges=(edge,),
        governed_scopes=(),
    )
    # Mismatch: edge_ids has length 2, edges has length 1
    persisted = PersistedProjectionRevision(
        revision_id="revision-test",
        created_at=now,
        revision=revision,
        edge_ids=("projection-edge-test", "another-edge-id"),
    )
    published = PublishedProjectionRevision(
        persisted=persisted,
        publication_id="pub-test",
        rebuild_job_id="job-test",
        execution_id="exec-test",
        published_at=now,
    )
    monkeypatch.setattr(
        RelationshipAssertionRepository, "get_published_edge", lambda _self, pub_id, edge_id: (published, edge)
    )

    response = client.get("/api/publications/pub-test/edges/projection-edge-test/explanation")
    assert response.status_code == 503
    assert response.json()["detail"] == "Graph publication metadata is inconsistent"
