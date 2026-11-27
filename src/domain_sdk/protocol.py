"""Protocol and canonical data transfer types for FarDB domain adapters."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from src.logic.asset_graph import AssetRelationshipGraph


@dataclass(frozen=True)
class DomainEntity:
    """Domain-agnostic entity projected into the canonical graph."""

    id: str
    symbol: str
    name: str
    entity_type: str
    group: str
    value: float = 0.0
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DomainEdge:
    """Directed or bidirectional relationship emitted by a DomainAdapter."""

    source_id: str
    target_id: str
    predicate_id: str
    strength: float
    bidirectional: bool = False


@runtime_checkable
class DomainAdapter(Protocol):
    """Contract that every domain adapter must satisfy without mutating core graph logic."""

    @property
    def domain_id(self) -> str:
        """Return the stable lowercase identifier for this domain."""
        ...

    @property
    def entity_types(self) -> frozenset[str]:
        """Return the set of supported entity type identifiers."""
        ...

    @property
    def predicate_ids(self) -> frozenset[str]:
        """Return the set of supported relationship predicate identifiers."""
        ...

    def validate_entity(self, entity: DomainEntity) -> None:
        """Validate a domain entity, raising ValueError on any contract violation."""
        ...

    def build_edges(self, entities: Sequence[DomainEntity]) -> list[DomainEdge]:
        """Deterministically derive domain relationships from a sequence of entities."""
        ...

    def to_canonical_graph(self, entities: Sequence[DomainEntity]) -> AssetRelationshipGraph:
        """Project validated domain entities and edges into an AssetRelationshipGraph."""
        ...

    def sample_entities(self) -> list[DomainEntity]:
        """Return a representative, deterministic set of entities for conformance testing."""
        ...
