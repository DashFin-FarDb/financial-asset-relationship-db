"""Shared fixtures and request builders for focused governed assertion API tests."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from api.auth import UserRepository, create_access_token, get_password_hash
from api.main import app
from api.routers import assertions as assertions_router
from api.services import relationship_index as relationship_index_service
from src.data.database import create_engine_from_url, init_db

UTC = timezone.utc


def _iso_now() -> str:
    """Return a current UTC instant in API-compatible form."""
    return datetime.now(tz=UTC).isoformat()


def _token(username: str) -> str:
    """Create a bearer token for a seeded test principal."""
    return create_access_token({"sub": username})


def _headers(token: str) -> dict[str, str]:
    """Build authorization headers for one API request."""
    return {"Authorization": f"Bearer {token}"}


def _supersession_headers(reviewer_token: str, proposer_token: str) -> dict[str, str]:
    """Build reviewer and distinct proposer authorization headers."""
    headers = _headers(reviewer_token)
    headers["X-Proposal-Authorization"] = f"Bearer {proposer_token}"
    return headers


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


def _assert_error_response(response: Response, status_code: int, detail: str) -> None:
    """Assert the bounded JSON error contract for one API response."""
    assert response.status_code == status_code
    assert response.json() == {"detail": detail}


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
    relationship_index_service._load_contract_predicates.cache_clear()
    relationship_index_service.invalidate_governed_relationship_index_cache()

    database_url = os.environ["DATABASE_URL"]
    settings = SimpleNamespace(
        asset_graph_database_url=database_url,
        database_url=None,
        vercel_env=None,
    )

    monkeypatch.setattr(
        assertions_router,
        "get_graph_lifecycle_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        relationship_index_service,
        "get_graph_lifecycle_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        relationship_index_service,
        "_latest_published_revision_id_from_persistence",
        lambda: None,
    )


@pytest.fixture
def client() -> TestClient:
    """Return a FastAPI test client."""
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