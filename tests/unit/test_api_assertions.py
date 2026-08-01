"""Focused tests for protected assertion command and explanation APIs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from api.auth import User, UserRepository, create_access_token, get_password_hash
from api.main import app
from api.routers import assertions as assertions_router
from api.routers import relationships as relationships_router
from api.routers import visualization as visualization_router
from api.routers.assertions import _assertion_repository_session
from src.data.database import create_engine_from_url, init_db
from src.data.relationship_assertion_repository import RegisterEvidenceRequest, RelationshipAssertionRepository
from src.data.relationship_projection_persistence import PersistedProjectionRevision
from src.governance.relationship_assertion import AuthorityContext, EvidenceRecord
from src.governance.relationship_assertion_contract import PredicatesDocument

UTC = timezone.utc


@dataclass(frozen=True)
class _DecisionAuthorizationCase:
    """One protected decision authorization expectation."""

    proposer: str
    actor: str
    to_state: str
    expected_status: int


@dataclass(frozen=True)
class _GovernanceRouteCase:
    """One public route that consumes governed relationship metadata."""

    route_module: object
    path: str


def _iso_now() -> str:
    """Return a current UTC instant in API-compatible form."""
    return datetime.now(tz=UTC).isoformat()


def _token(username: str) -> str:
    """Create a bearer token for a seeded test principal."""
    return create_access_token({"sub": username})


def _headers(token: str) -> dict[str, str]:
    """Build authorization headers for one API request."""
    return {"Authorization": f"Bearer {token}"}


def _proposal_payload(assertion_id: str) -> dict[str, object]:
    """Build a valid governed assertion proposal payload."""
    return {
        "assertion_id": assertion_id,
        "predicate_id": "financial.bond.issuer_reference@1",
        "subject_id": "AAPL_BOND_2030",
        "object_id": "AAPL",
        "method_id": "bond.issuer_id.resolution@1",
        "proposition": "Bond issuer_id references AAPL",
        "effective_from": _iso_now(),
    }


def _decision_payload(to_state: str, expected_sequence: int, rationale: str) -> dict[str, object]:
    """Build a lifecycle decision payload."""
    return {"to_state": to_state, "expected_sequence": expected_sequence, "rationale": rationale}


@pytest.fixture(scope="module", autouse=True)
def initialize_assertion_store() -> None:
    """Initialize the assertion schema once, matching application startup."""
    engine = create_engine_from_url(os.environ["DATABASE_URL"])
    try:
        init_db(engine)
    finally:
        engine.dispose()


@pytest.fixture(autouse=True)
def configure_graph_persistence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bind focused API tests to the durable test graph database."""
    database_url = os.environ["DATABASE_URL"]
    settings = SimpleNamespace(
        asset_graph_database_url=database_url,
        database_url=database_url,
        env="development",
        vercel_env=None,
    )
    monkeypatch.setattr(assertions_router, "get_graph_lifecycle_settings", lambda: settings)
    monkeypatch.setattr(relationships_router, "get_graph_lifecycle_settings", lambda: settings)


@pytest.fixture()
def client() -> TestClient:
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def seed_users() -> None:
    """Create the principals used by protected assertion API tests."""
    repository = UserRepository()
    for username in ("admin", "proposer_a", "proposer_b"):
        repository.create_or_update_user(
            username=username,
            hashed_password=get_password_hash(f"{username}-pw"),
            user_profile={"is_disabled": False},
        )


@pytest.mark.unit
def test_assertion_proposal_requires_authentication(client: TestClient) -> None:
    """Proposal commands reject anonymous callers."""
    assertion_id = str(uuid4())
    response = client.post("/api/assertions", json=_proposal_payload(assertion_id))
    assert response.status_code == 401


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
    reviewer_headers = _headers(_token("admin"))

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
            "proposal_bearer_token": _token("proposer_b"),
            "successor_proposal": _proposal_payload(successor_id),
        },
        headers=reviewer_headers,
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
    reviewer_headers = _headers(_token("admin"))
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
            "proposal_bearer_token": _token("proposer_b"),
            "successor_proposal": _proposal_payload(assertion_id),
        },
        headers=reviewer_headers,
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

    assert response.status_code == 500
    assert response.json() == {"detail": "An internal error occurred. Please try again later."}


@pytest.mark.unit
def test_assertion_store_does_not_fall_back_to_application_database(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Modern settings never write governed assertions to the auth database fallback."""
    settings = SimpleNamespace(
        asset_graph_database_url=None,
        database_url=os.environ["DATABASE_URL"],
        env="development",
        vercel_env=None,
    )
    monkeypatch.setattr(assertions_router, "get_graph_lifecycle_settings", lambda: settings)

    response = client.get(f"/api/assertions/{uuid4()}")

    assert response.status_code == 503
    assert response.json() == {"detail": "Graph persistence database not configured"}


@pytest.mark.unit
def test_invalid_assertion_persistence_url_maps_to_service_unavailable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Malformed graph persistence configuration produces a bounded 503."""
    settings = SimpleNamespace(asset_graph_database_url="not a database url", database_url=None)
    monkeypatch.setattr(assertions_router, "get_graph_lifecycle_settings", lambda: settings)

    response = client.get(f"/api/assertions/{uuid4()}")

    assert response.status_code == 503
    assert response.json() == {"detail": "Graph persistence database not configured"}


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
        del settings
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
def test_history_is_monotonic_and_redacted_reads_hide_non_public_evidence(client: TestClient) -> None:
    """History remains ordered and explanation reads redact restricted evidence."""
    assertion_id = str(uuid4())
    owner_headers = _headers(_token("proposer_a"))
    reviewer_headers = _headers(_token("admin"))

    create = client.post("/api/assertions", json=_proposal_payload(assertion_id), headers=owner_headers)
    assert create.status_code == 200
    accept = client.post(
        f"/api/assertions/{assertion_id}/decisions",
        json=_decision_payload("Accepted", 1, "accept"),
        headers=reviewer_headers,
    )
    assert accept.status_code == 200
    dispute = client.post(
        f"/api/assertions/{assertion_id}/decisions",
        json=_decision_payload("Disputed", 2, "dispute"),
        headers=reviewer_headers,
    )
    assert dispute.status_code == 200

    with _assertion_repository_session() as session:
        repository = RelationshipAssertionRepository(session)
        repository.register_evidence(
            RegisterEvidenceRequest(
                assertion_id=assertion_id,
                polarity="supporting",
                ctx=AuthorityContext(
                    actor_id="proposer_a",
                    roles=frozenset({"proposer"}),
                    policy_version="grac.v1",
                    correlation_id="corr-test",
                ),
                evidence=EvidenceRecord(
                    evidence_id=str(uuid4()),
                    source_ref="s3://restricted-bucket/proof.json",
                    content_sha256="a" * 64,
                    media_type="application/json",
                    visibility="restricted",
                    custody_id="custody-test",
                    recorded_at=datetime.now(tz=UTC),
                ),
            )
        )
        session.commit()

    history = client.get(f"/api/assertions/{assertion_id}/history")
    assert history.status_code == 200
    events = history.json()["events"]
    assert [row["sequence"] for row in events] == [1, 2, 3]
    assert [row["recorded_at"] for row in events] == sorted(row["recorded_at"] for row in events)

    read = client.get(f"/api/assertions/{assertion_id}")
    assert read.status_code == 200
    evidence_rows = read.json()["evidence"]
    assert len(evidence_rows) == 1
    assert evidence_rows[0]["redacted"] is True
    assert evidence_rows[0].get("source_ref") is None


@pytest.mark.unit
def test_explanation_loads_only_linked_evidence(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Explanation reads avoid the full projection-source snapshot."""
    assertion_id = str(uuid4())
    evidence_id = str(uuid4())
    owner_headers = _headers(_token("proposer_a"))
    create = client.post("/api/assertions", json=_proposal_payload(assertion_id), headers=owner_headers)
    assert create.status_code == 200

    with _assertion_repository_session() as session:
        repository = RelationshipAssertionRepository(session)
        repository.register_evidence(
            RegisterEvidenceRequest(
                assertion_id=assertion_id,
                polarity="supporting",
                ctx=AuthorityContext(
                    actor_id="proposer_a",
                    roles=frozenset({"proposer"}),
                    policy_version="grac.v1",
                ),
                evidence=EvidenceRecord(
                    evidence_id=evidence_id,
                    source_ref="https://example.test/public-proof.json",
                    content_sha256="b" * 64,
                    media_type="application/json",
                    visibility="public",
                    custody_id="custody-test",
                    recorded_at=datetime.now(tz=UTC),
                ),
            )
        )
        session.commit()

    monkeypatch.setattr(
        RelationshipAssertionRepository,
        "load_projection_source_snapshot",
        lambda _repository: pytest.fail("explanation must not load the full projection snapshot"),
    )

    read = client.get(f"/api/assertions/{assertion_id}")

    assert read.status_code == 200
    assert [row["evidence_id"] for row in read.json()["evidence"]] == [evidence_id]


@pytest.mark.unit
def test_governance_contract_failure_propagates_from_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unexpected contract failures propagate instead of producing legacy metadata."""
    published = SimpleNamespace(
        revision=SimpleNamespace(governed_scopes=(), edges=()),
        revision_id="revision-test",
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
        relationships_router.load_governed_relationship_index()


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

    def fail_governance_load() -> None:
        """Simulate a governance persistence or contract outage."""
        raise RuntimeError("governance load failed")

    monkeypatch.setattr(case.route_module, "load_governed_relationship_index", fail_governance_load)

    response = client.get(case.path)
    assert response.status_code == 500
    assert response.json() == {"detail": "An internal error occurred. Please try again later."}


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
