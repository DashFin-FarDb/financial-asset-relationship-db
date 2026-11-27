"""Unit tests for HumanResourcesDomainAdapter conformance and canonical persistence round-trip."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import sessionmaker

from src.data.database import create_engine_from_url, init_db
from src.data.repository import AssetGraphRepository
from src.domain_sdk import (
    DomainConformanceSuite,
    DomainEntity,
    HumanResourcesDomainAdapter,
    create_default_registry,
)


def test_human_resources_adapter_passes_conformance_and_registers_alongside_financial() -> None:
    """HumanResourcesDomainAdapter passes DomainConformanceSuite and coexists in DomainRegistry."""
    adapter = HumanResourcesDomainAdapter()
    result = DomainConformanceSuite().run(adapter)

    assert result.domain_id == "human_resources"
    assert result.passed is True
    assert result.failures == ()

    registry = create_default_registry()
    registry.register(adapter)
    assert registry.list_domains() == ("financial", "human_resources")
    assert registry.get("human_resources") is adapter


def test_human_resources_adapter_rejects_invalid_attributes() -> None:
    """Invalid reference or skill_ids attributes raise ValueError."""
    adapter = HumanResourcesDomainAdapter()

    with pytest.raises(ValueError, match="manager_id"):
        adapter.validate_entity(
            DomainEntity(
                id="EMP_1",
                symbol="E1",
                name="Bad Manager Ref",
                entity_type="employee",
                group="Engineering",
                attributes={"manager_id": "   "},
            )
        )

    with pytest.raises(ValueError, match="skill_ids"):
        adapter.validate_entity(
            DomainEntity(
                id="EMP_2",
                symbol="E2",
                name="Bad Skills",
                entity_type="employee",
                group="Engineering",
                attributes={"skill_ids": "not-a-list"},
            )
        )


def test_human_resources_graph_round_trips_through_canonical_repository() -> None:
    """Projected HR graph saves and reloads cleanly via AssetGraphRepository without core changes."""
    adapter = HumanResourcesDomainAdapter()
    graph = adapter.to_canonical_graph(adapter.sample_entities())

    engine = create_engine_from_url("sqlite:///:memory:")
    try:
        init_db(engine)
        session_factory = sessionmaker(bind=engine)
        with session_factory() as session:
            repo = AssetGraphRepository(session)
            repo.save_graph(graph)
            session.commit()

            reloaded = repo.load_graph()

        assert set(reloaded.assets.keys()) == set(graph.assets.keys())
        original_edges = {
            (src, dst, rel_type) for src, rels in graph.relationships.items() for dst, rel_type, _ in rels
        }
        reloaded_edges = {
            (src, dst, rel_type) for src, rels in reloaded.relationships.items() for dst, rel_type, _ in rels
        }
        assert original_edges == reloaded_edges
        assert ("EMP_BOB", "EMP_ALICE", "reports_to") in reloaded_edges
        assert ("EMP_BOB", "EMP_ALICE", "successor_for") in reloaded_edges
        assert ("EMP_BOB", "SKILL_DIST_SYS", "has_skill") in reloaded_edges
    finally:
        engine.dispose()
