"""Financial domain adapter wrapping FarDB's canonical financial models."""

from __future__ import annotations

from collections.abc import Sequence

from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import Asset, AssetClass, Bond, Commodity, Currency, Equity

from .protocol import DomainEdge, DomainEntity

_ENTITY_TYPE_TO_ASSET_CLASS: dict[str, AssetClass] = {
    "equity": AssetClass.EQUITY,
    "bond": AssetClass.FIXED_INCOME,
    "commodity": AssetClass.COMMODITY,
    "currency": AssetClass.CURRENCY,
    "derivative": AssetClass.DERIVATIVE,
}

_NON_MEANINGFUL_GROUPS = frozenset({"", "other", "unknown", "none", "n/a"})


class FinancialDomainAdapter:
    """Reference DomainAdapter for FarDB's financial asset domain."""

    @property
    def domain_id(self) -> str:
        """Return the financial domain identifier."""
        return "financial"

    @property
    def entity_types(self) -> frozenset[str]:
        """Return supported financial entity types."""
        return frozenset(_ENTITY_TYPE_TO_ASSET_CLASS.keys())

    @property
    def predicate_ids(self) -> frozenset[str]:
        """Return supported financial relationship predicates."""
        return frozenset({"same_sector", "corporate_link"})

    def validate_entity(self, entity: DomainEntity) -> None:
        """Validate a financial DomainEntity."""
        if not isinstance(entity.id, str) or not entity.id.strip():
            raise ValueError("Entity id must be a non-empty string")
        if not isinstance(entity.symbol, str) or not entity.symbol.strip():
            raise ValueError("Entity symbol must be a non-empty string")
        if not isinstance(entity.name, str) or not entity.name.strip():
            raise ValueError("Entity name must be a non-empty string")
        if entity.entity_type not in self.entity_types:
            raise ValueError(f"Unsupported financial entity_type: {entity.entity_type!r}")
        if not isinstance(entity.value, (int, float)) or isinstance(entity.value, bool) or entity.value < 0:
            raise ValueError("Entity value must be a non-negative number")
        if entity.entity_type == "bond" and "issuer_id" in entity.attributes:
            issuer_id = entity.attributes["issuer_id"]
            if not isinstance(issuer_id, str) or not issuer_id.strip():
                raise ValueError("Bond issuer_id attribute must be a non-empty string")

    def build_edges(self, entities: Sequence[DomainEntity]) -> list[DomainEdge]:
        """Build deterministic same_sector and corporate_link edges."""
        for entity in entities:
            self.validate_entity(entity)

        ordered = sorted(entities, key=lambda item: item.id)
        ids = {entity.id for entity in ordered}
        edges: list[DomainEdge] = []

        for idx, left in enumerate(ordered):
            left_group = left.group.strip().lower()
            for right in ordered[idx + 1 :]:
                right_group = right.group.strip().lower()
                if left_group and left_group == right_group and left_group not in _NON_MEANINGFUL_GROUPS:
                    edges.append(
                        DomainEdge(
                            source_id=left.id,
                            target_id=right.id,
                            predicate_id="same_sector",
                            strength=0.5,
                            bidirectional=True,
                        )
                    )

        for entity in ordered:
            if entity.entity_type == "bond":
                issuer_id = entity.attributes.get("issuer_id")
                if isinstance(issuer_id, str) and issuer_id in ids and issuer_id != entity.id:
                    edges.append(
                        DomainEdge(
                            source_id=entity.id,
                            target_id=issuer_id,
                            predicate_id="corporate_link",
                            strength=0.9,
                            bidirectional=False,
                        )
                    )

        return edges

    def to_canonical_graph(self, entities: Sequence[DomainEntity]) -> AssetRelationshipGraph:
        """Project financial entities and edges onto AssetRelationshipGraph."""
        edges = self.build_edges(entities)
        graph = AssetRelationshipGraph()

        for entity in entities:
            asset_class = _ENTITY_TYPE_TO_ASSET_CLASS[entity.entity_type]
            currency = str(entity.attributes.get("currency", "USD")).upper()
            asset: Asset
            if entity.entity_type == "equity":
                asset = Equity(
                    id=entity.id,
                    symbol=entity.symbol,
                    name=entity.name,
                    asset_class=asset_class,
                    sector=entity.group,
                    price=float(entity.value),
                    currency=currency,
                )
            elif entity.entity_type == "bond":
                asset = Bond(
                    id=entity.id,
                    symbol=entity.symbol,
                    name=entity.name,
                    asset_class=asset_class,
                    sector=entity.group,
                    price=float(entity.value),
                    currency=currency,
                    issuer_id=entity.attributes.get("issuer_id"),
                )
            elif entity.entity_type == "commodity":
                asset = Commodity(
                    id=entity.id,
                    symbol=entity.symbol,
                    name=entity.name,
                    asset_class=asset_class,
                    sector=entity.group,
                    price=float(entity.value),
                    currency=currency,
                )
            elif entity.entity_type == "currency":
                asset = Currency(
                    id=entity.id,
                    symbol=entity.symbol,
                    name=entity.name,
                    asset_class=asset_class,
                    sector=entity.group,
                    price=float(entity.value),
                    currency=currency,
                )
            else:
                asset = Asset(
                    id=entity.id,
                    symbol=entity.symbol,
                    name=entity.name,
                    asset_class=asset_class,
                    sector=entity.group,
                    price=float(entity.value),
                    currency=currency,
                )
            graph.add_asset(asset)

        for edge in edges:
            graph.add_relationship(
                edge.source_id,
                edge.target_id,
                edge.predicate_id,
                edge.strength,
                bidirectional=edge.bidirectional,
            )

        return graph

    def sample_entities(self) -> list[DomainEntity]:
        """Return deterministic sample financial entities for conformance checks."""
        return [
            DomainEntity(
                id="AAPL",
                symbol="AAPL",
                name="Apple Inc.",
                entity_type="equity",
                group="Technology",
                value=185.0,
            ),
            DomainEntity(
                id="MSFT",
                symbol="MSFT",
                name="Microsoft Corporation",
                entity_type="equity",
                group="Technology",
                value=410.0,
            ),
            DomainEntity(
                id="AAPL_BOND_2030",
                symbol="AAPL30",
                name="Apple 2030 Senior Note",
                entity_type="bond",
                group="Technology",
                value=99.5,
                attributes={"issuer_id": "AAPL"},
            ),
            DomainEntity(
                id="JPM",
                symbol="JPM",
                name="JPMorgan Chase & Co.",
                entity_type="equity",
                group="Financials",
                value=195.0,
            ),
        ]
