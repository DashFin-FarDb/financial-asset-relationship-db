"""Focused regression tests for governed relationship-index review fixes."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.services import relationship_index
from src.data.relationship_projection_persistence import PersistedProjectionRevision


@pytest.mark.unit
def test_assertion_predicate_lookup_chunks_large_revisions() -> None:
    """Assertion ownership queries stay below the bounded IN-clause chunk size."""
    assertion_ids = [f"assertion-{index:04d}" for index in range(801)]
    published = cast(
        PersistedProjectionRevision,
        SimpleNamespace(
            revision=SimpleNamespace(
                edges=tuple(SimpleNamespace(assertion_id=assertion_id) for assertion_id in assertion_ids)
            )
        ),
    )
    session = Mock(spec=Session)
    query_results: list[Mock] = []
    for start in range(0, len(assertion_ids), relationship_index._IN_CLAUSE_CHUNK_SIZE):
        result = Mock()
        result.tuples.return_value.all.return_value = [
            (assertion_id, "predicate-test")
            for assertion_id in assertion_ids[start : start + relationship_index._IN_CLAUSE_CHUNK_SIZE]
        ]
        query_results.append(result)
    session.execute.side_effect = query_results

    assertion_predicates = relationship_index._assertion_predicates_for_edges(session, published)

    assert assertion_predicates == dict.fromkeys(assertion_ids, "predicate-test")
    assert session.execute.call_count == 3


@pytest.mark.unit
def test_relationship_index_persistence_sqlalchemy_errors_are_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Persistence outages fail closed with a bounded 503 instead of leaking ORM details."""
    session = Mock(spec=Session)

    @contextmanager
    def fake_session_scope(_session_factory: object) -> Iterator[Session]:
        """Yield the test session without opening a persistence connection."""
        yield session

    class FailingRepository:
        """Repository double that raises a low-level persistence failure."""

        def __init__(self, repository_session: Session) -> None:
            """Retain the supplied session so the double matches production construction."""
            self.session = repository_session

        def latest_published_projection(self, _purpose: str) -> PersistedProjectionRevision | None:
            """Raise the simulated SQLAlchemy outage under test."""
            raise SQLAlchemyError("connection refused with internal host details")

    monkeypatch.setattr(relationship_index, "RelationshipAssertionRepository", FailingRepository)
    monkeypatch.setattr(relationship_index, "session_scope", fake_session_scope)
    monkeypatch.setattr(relationship_index, "_governance_session_factory", object)

    with pytest.raises(HTTPException) as exc_info:
        relationship_index._load_governed_relationship_index_from_persistence()

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Graph persistence database is unavailable"
