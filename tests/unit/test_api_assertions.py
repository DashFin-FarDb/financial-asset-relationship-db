"""Focused tests for protected assertion command and explanation APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.auth import UserRepository, create_access_token, get_password_hash
from api.main import app
from api.routers import relationships as relationships_router
from api.routers import visualization as visualization_router
from api.routers.assertions import _assertion_repository_session
from src.data.relationship_assertion_repository import RegisterEvidenceRequest, RelationshipAssertionRepository
from src.governance.relationship_assertion import AuthorityContext, EvidenceRecord

UTC = timezone.utc


def _iso_now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _token(username: str) -> str:
    return create_access_token({"sub": username})


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _proposal_payload(assertion_id: str) -> dict[str, object]:
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
    return {"to_state": to_state, "expected_sequence": expected_sequence, "rationale": rationale}


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
    assertion_id = str(uuid4())
    response = client.post("/api/assertions", json=_proposal_payload(assertion_id))
    assert response.status_code == 401


@pytest.mark.unit
def test_idempotent_reuse_and_foreign_reuse_rejection(client: TestClient) -> None:
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
def test_decision_enforces_reviewer_boundary(client: TestClient) -> None:
    assertion_id = str(uuid4())
    owner_headers = _headers(_token("proposer_a"))
    create = client.post("/api/assertions", json=_proposal_payload(assertion_id), headers=owner_headers)
    assert create.status_code == 200

    decision = client.post(
        f"/api/assertions/{assertion_id}/decisions",
        json=_decision_payload("Accepted", 1, "accept"),
        headers=owner_headers,
    )
    assert decision.status_code == 403


@pytest.mark.unit
def test_same_principal_determination_rejected_with_conflict(client: TestClient) -> None:
    assertion_id = str(uuid4())
    admin_headers = _headers(_token("admin"))
    create = client.post("/api/assertions", json=_proposal_payload(assertion_id), headers=admin_headers)
    assert create.status_code == 200

    decision = client.post(
        f"/api/assertions/{assertion_id}/decisions",
        json=_decision_payload("Accepted", 1, "accept"),
        headers=admin_headers,
    )
    assert decision.status_code == 409


@pytest.mark.unit
def test_foreign_withdrawal_rejected(client: TestClient) -> None:
    assertion_id = str(uuid4())
    owner_headers = _headers(_token("proposer_a"))
    create = client.post("/api/assertions", json=_proposal_payload(assertion_id), headers=owner_headers)
    assert create.status_code == 200

    withdraw = client.post(
        f"/api/assertions/{assertion_id}/decisions",
        json=_decision_payload("Withdrawn", 1, "withdraw"),
        headers=_headers(_token("proposer_b")),
    )
    assert withdraw.status_code == 409


@pytest.mark.unit
def test_supersession_conflict_rolls_back_successor_write(client: TestClient) -> None:
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
def test_history_is_monotonic_and_redacted_reads_hide_non_public_evidence(client: TestClient) -> None:
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
        _evidence, _link = repository.register_evidence(
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

    requested_ids: list[tuple[str, ...]] = []
    original = RelationshipAssertionRepository.load_evidence_by_ids

    def recording_load(
        repository: RelationshipAssertionRepository,
        evidence_ids: list[str],
    ) -> tuple[EvidenceRecord, ...]:
        requested_ids.append(tuple(evidence_ids))
        return original(repository, evidence_ids)

    monkeypatch.setattr(RelationshipAssertionRepository, "load_evidence_by_ids", recording_load)
    monkeypatch.setattr(
        RelationshipAssertionRepository,
        "load_projection_source_snapshot",
        lambda _repository: pytest.fail("explanation must not load the full projection snapshot"),
    )

    read = client.get(f"/api/assertions/{assertion_id}")

    assert read.status_code == 200
    assert requested_ids == [(evidence_id,)]
    assert [row["evidence_id"] for row in read.json()["evidence"]] == [evidence_id]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("route_module", "index_name", "path"),
    [
        (relationships_router, "_governed_relationship_index", "/api/relationships"),
        (visualization_router, "_governed_edge_index", "/api/visualization"),
    ],
)
def test_governance_contract_failure_reaches_route_error_handler(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    route_module: Any,
    index_name: str,
    path: str,
) -> None:
    published = SimpleNamespace(
        revision=SimpleNamespace(governed_scopes=(), edges=()),
        revision_id="revision-test",
    )
    monkeypatch.setattr(route_module, "get_graph_lifecycle_settings", lambda: SimpleNamespace(database_url="unused"))
    monkeypatch.setattr(route_module, "resolve_hosted_graph_database_url", lambda _settings: None)
    monkeypatch.setattr(route_module, "resolve_durable_graph_persistence_url", lambda _url: "sqlite:///:memory:")
    monkeypatch.setattr(
        route_module.RelationshipAssertionRepository,
        "latest_published_projection",
        lambda _repository, _purpose: published,
    )

    def fail_contract_load() -> None:
        raise RuntimeError("contract load failed")

    monkeypatch.setattr(route_module, "load_contract_bundle", fail_contract_load)

    with pytest.raises(RuntimeError, match="contract load failed"):
        getattr(route_module, index_name)()

    response = client.get(path)
    assert response.status_code == 500
    assert response.json() == {"detail": "An internal error occurred. Please try again later."}


@pytest.mark.unit
def test_legacy_relationship_and_visualization_payloads_omit_new_optional_fields(client: TestClient) -> None:
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
