"""Focused tests for public governed assertion explanation and history APIs."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from api.routers.assertions import _assertion_repository_session
from src.data.relationship_assertion_repository import RegisterEvidenceRequest, RelationshipAssertionRepository
from src.governance.relationship_assertion import AssertionAsOf, AuthorityContext, EvidenceRecord

from .api_assertion_test_support import (
    UTC,
    _assert_error_response,
    _decision_payload,
    _headers,
    _proposal_payload,
    _token,
)

pytest_plugins = ("tests.unit.api_assertion_test_support",)


@pytest.mark.unit
@pytest.mark.parametrize("path_suffix", ["", "/history"], ids=["explanation", "history"])
def test_unexpected_public_read_failure_is_sanitized(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    path_suffix: str,
) -> None:
    """Unexpected explanation persistence failures become generic JSON 500 responses."""

    def fail_read(*_args: object, **_kwargs: object) -> None:
        """Simulate an unexpected persistence failure containing private detail."""
        raise RuntimeError("private persistence detail")

    monkeypatch.setattr(RelationshipAssertionRepository, "get_as_of", fail_read)

    response = client.get(f"/api/assertions/{uuid4()}{path_suffix}")

    _assert_error_response(response, 500, "An internal error occurred. Please try again later.")


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
    sensitive_event_fields = {"actor_id", "rationale", "policy_version", "correlation_id"}
    assert all(sensitive_event_fields.isdisjoint(row) for row in events)

    read = client.get(f"/api/assertions/{assertion_id}")
    assert read.status_code == 200
    read_payload = read.json()
    assert "proposer_actor_id" not in read_payload
    evidence_rows = read_payload["evidence"]
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
def test_empty_repository_event_view_fails_closed(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An invalid eventless repository view produces a bounded internal error."""
    empty_view = cast(AssertionAsOf, SimpleNamespace(events=()))

    def get_empty_view(
        _repository: RelationshipAssertionRepository,
        _assertion_id: str,
        *,
        known_at: datetime,
        effective_at: datetime | None = None,
    ) -> AssertionAsOf:
        """Return an invalid view to exercise the API boundary guard."""
        return empty_view

    monkeypatch.setattr(RelationshipAssertionRepository, "get_as_of", get_empty_view)

    response = client.get(f"/api/assertions/{uuid4()}")

    _assert_error_response(response, 500, "An internal error occurred. Please try again later.")
