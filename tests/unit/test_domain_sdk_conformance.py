"""Unit tests for the canonical DomainAdapter protocol, registry, and conformance suite."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from src.domain_sdk import (
    DomainConformanceSuite,
    DomainEdge,
    DomainEntity,
    DomainRegistry,
    FinancialDomainAdapter,
    create_default_registry,
)
from src.logic.asset_graph import AssetRelationshipGraph


def test_financial_adapter_passes_conformance_suite() -> None:
    """FinancialDomainAdapter satisfies every DomainConformanceSuite invariant."""
    adapter = FinancialDomainAdapter()
    result = DomainConformanceSuite().run(adapter)

    assert result.domain_id == "financial"
    assert result.passed is True
    assert result.failures == ()
    assert result.checks_run >= 10


def test_default_registry_registers_financial_and_rejects_duplicates() -> None:
    """DomainRegistry registers financial by default and rejects duplicate or unknown IDs."""
    registry = create_default_registry()
    assert registry.contains("financial") is True
    assert registry.list_domains() == ("financial",)
    assert isinstance(registry.get("financial"), FinancialDomainAdapter)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(FinancialDomainAdapter())

    with pytest.raises(KeyError, match="Unknown domain adapter"):
        registry.get("nonexistent")


def test_registry_rejects_non_adapter_objects() -> None:
    """DomainRegistry raises TypeError when registering objects outside DomainAdapter."""
    registry = DomainRegistry()
    with pytest.raises(TypeError, match="DomainAdapter"):
        registry.register(object())  # type: ignore[arg-type]


def test_conformance_suite_detects_broken_adapter() -> None:
    """DomainConformanceSuite reports explicit failures for a non-conforming adapter."""

    class _BrokenAdapter:
        @property
        def domain_id(self) -> str:
            return "BrokenUpper"

        @property
        def entity_types(self) -> frozenset[str]:
            return frozenset({"node"})

        @property
        def predicate_ids(self) -> frozenset[str]:
            return frozenset({"links_to"})

        def validate_entity(self, entity: DomainEntity) -> None:
            # Intentionally fails to reject invalid entities.
            return None

        def build_edges(self, entities: Sequence[DomainEntity]) -> list[DomainEdge]:
            return [
                DomainEdge(
                    source_id="ghost-a",
                    target_id="ghost-b",
                    predicate_id="undeclared_predicate",
                    strength=2.5,
                )
            ]

        def to_canonical_graph(self, entities: Sequence[DomainEntity]) -> AssetRelationshipGraph:
            return AssetRelationshipGraph()

        def sample_entities(self) -> list[DomainEntity]:
            return [
                DomainEntity(id="n1", symbol="N1", name="Node 1", entity_type="node", group="g"),
                DomainEntity(id="n2", symbol="N2", name="Node 2", entity_type="node", group="g"),
            ]

    result = DomainConformanceSuite().run(_BrokenAdapter())
    assert result.passed is False
    assert len(result.failures) >= 5
