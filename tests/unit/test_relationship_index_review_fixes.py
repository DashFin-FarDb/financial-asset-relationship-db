"""Focused regression tests for governed relationship-index review fixes."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest
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
def test_latest_revision_probe_is_cached_for_short_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    """Repeated hot-path reads reuse one revision probe until its TTL expires."""
    current_time = 10.0
    session = Mock(spec=Session)
    execution = Mock()
    execution.scalar_one_or_none.return_value = "revision-test"
    session.execute.return_value = execution

    @contextmanager
    def fake_session_scope(_session_factory: object) -> Iterator[Session]:
        """Yield the test session without opening a persistence connection."""
        yield session

    monkeypatch.setattr(relationship_index, "session_scope", fake_session_scope)
    monkeypatch.setattr(relationship_index, "_governance_session_factory", object)
    monkeypatch.setattr(relationship_index, "monotonic", lambda: current_time)
    relationship_index._latest_published_revision_id_for_bucket.cache_clear()

    assert relationship_index._latest_published_revision_id_from_persistence() == "revision-test"
    assert relationship_index._latest_published_revision_id_from_persistence() == "revision-test"
    assert session.execute.call_count == 1

    current_time += relationship_index._PUBLISHED_REVISION_PROBE_TTL_SECONDS
    assert relationship_index._latest_published_revision_id_from_persistence() == "revision-test"
    assert session.execute.call_count == 2

    relationship_index._latest_published_revision_id_for_bucket.cache_clear()
