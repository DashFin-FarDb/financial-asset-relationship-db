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
from .api_assertion_test_support import configure_graph_persistence  # noqa: F401
from .api_assertion_test_support import initialize_assertion_store  # noqa: F401
from .api_assertion_test_support import seed_users  # noqa: F401
from .api_assertion_test_support import (
    _assert_error_response,
    _decision_payload,
    _headers,
    _proposal_payload,
    _supersession_headers,
    _token,
)


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
