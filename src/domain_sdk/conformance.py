"""Reusable conformance suite validating any DomainAdapter implementation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from src.logic.asset_graph import AssetRelationshipGraph

from .protocol import DomainAdapter, DomainEntity


@dataclass(frozen=True)
class ConformanceResult:
    """Structured outcome of running DomainConformanceSuite against an adapter."""

    domain_id: str
    passed: bool
    checks_run: int
    failures: tuple[str, ...] = ()


class DomainConformanceSuite:
    """Verifies protocol, validation, determinism, and canonical-graph projection invariants."""

    def run(self, adapter: DomainAdapter) -> ConformanceResult:
        """Execute all conformance checks against adapter and return a ConformanceResult."""
        if not isinstance(adapter, DomainAdapter):
            return ConformanceResult(
                domain_id=getattr(adapter, "domain_id", "unknown"),
                passed=False,
                checks_run=1,
                failures=("Adapter does not satisfy runtime_checkable DomainAdapter protocol",),
            )

        failures: list[str] = []
        checks_run = 1
        samples = adapter.sample_entities()

        checks_run += self._check_metadata(adapter, samples, failures)
        checks_run += self._check_validation(adapter, samples, failures)
        checks_run += self._check_edges(adapter, samples, failures)
        checks_run += self._check_canonical_graph(adapter, samples, failures)

        return ConformanceResult(
            domain_id=adapter.domain_id,
            passed=not failures,
            checks_run=checks_run,
            failures=tuple(failures),
        )

    @staticmethod
    def _check_metadata(
        adapter: DomainAdapter,
        samples: Sequence[DomainEntity],
        failures: list[str],
    ) -> int:
        """Verify non-empty lowercase domain_id, entity_types, predicate_ids, and sample size."""
        domain_id = adapter.domain_id
        if not isinstance(domain_id, str) or not domain_id.strip() or domain_id != domain_id.lower():
            failures.append(f"domain_id must be a non-empty lowercase string, got {domain_id!r}")
        if not adapter.entity_types:
            failures.append("entity_types must be non-empty")
        if not adapter.predicate_ids:
            failures.append("predicate_ids must be non-empty")
        if len(samples) < 2:
            failures.append("sample_entities() must return at least 2 entities")
        return 4

    @staticmethod
    def _check_validation(
        adapter: DomainAdapter,
        samples: Sequence[DomainEntity],
        failures: list[str],
    ) -> int:
        """Verify valid sample entities pass and malformed entities raise ValueError."""
        for entity in samples:
            try:
                adapter.validate_entity(entity)
            except Exception as exc:
                failures.append(f"sample entity {entity.id!r} failed validate_entity: {exc}")

        valid_type = next(iter(adapter.entity_types), "unknown")
        bad_entities = (
            ("empty_id", DomainEntity(id="", symbol="BAD", name="Bad", entity_type=valid_type, group="g", value=1.0)),
            (
                "unknown_entity_type",
                DomainEntity(
                    id="bad-type-1",
                    symbol="BAD",
                    name="Bad Type",
                    entity_type="__unsupported_entity_type__",
                    group="g",
                    value=1.0,
                ),
            ),
            (
                "negative_value",
                DomainEntity(id="bad-val-1", symbol="BAD", name="Neg", entity_type=valid_type, group="g", value=-1.0),
            ),
        )
        for label, bad in bad_entities:
            try:
                adapter.validate_entity(bad)
            except ValueError:
                pass
            else:
                failures.append(f"validate_entity() did not reject invalid case: {label}")
        return 1 + len(bad_entities)

    @staticmethod
    def _check_edges(
        adapter: DomainAdapter,
        samples: Sequence[DomainEntity],
        failures: list[str],
    ) -> int:
        """Verify build_edges() determinism, declared predicates, valid endpoints, and strength bounds."""
        edges_first = adapter.build_edges(samples)
        edges_second = adapter.build_edges(samples)
        if edges_first != edges_second:
            failures.append("build_edges() is not deterministic across repeated calls")
        if not edges_first:
            failures.append("build_edges(sample_entities()) must emit at least one edge")

        entity_ids = {entity.id for entity in samples}
        for edge in edges_first:
            if edge.predicate_id not in adapter.predicate_ids:
                failures.append(f"edge predicate {edge.predicate_id!r} not in declared predicate_ids")
            if edge.source_id not in entity_ids or edge.target_id not in entity_ids:
                failures.append(f"edge ({edge.source_id!r} -> {edge.target_id!r}) references unknown entity")
            if not -1.0 <= edge.strength <= 1.0:
                failures.append(f"edge strength {edge.strength} outside [-1.0, 1.0]")
        return 3

    @staticmethod
    def _check_canonical_graph(
        adapter: DomainAdapter,
        samples: Sequence[DomainEntity],
        failures: list[str],
    ) -> int:
        """Verify to_canonical_graph() projects all entities and emits canonical relationships."""
        graph = adapter.to_canonical_graph(samples)
        if not isinstance(graph, AssetRelationshipGraph):
            failures.append("to_canonical_graph() did not return an AssetRelationshipGraph")
            return 1

        entity_ids = {entity.id for entity in samples}
        missing_ids = entity_ids - set(graph.assets.keys())
        if missing_ids:
            failures.append(f"to_canonical_graph() missing projected entities: {sorted(missing_ids)}")
        if sum(len(rels) for rels in graph.relationships.values()) == 0:
            failures.append("to_canonical_graph() produced zero relationships")
        return 1
