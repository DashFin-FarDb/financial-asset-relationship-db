"""Human Resources reference domain adapter proving zero-core-change domain generality."""

from __future__ import annotations

from collections.abc import Sequence

from src.logic.asset_graph import AssetRelationshipGraph
from src.models.financial_models import Asset, AssetClass

from .protocol import DomainEdge, DomainEntity

_HR_ENTITY_TYPE_TO_CANONICAL_CLASS: dict[str, AssetClass] = {
    "employee": AssetClass.EQUITY,
    "department": AssetClass.FIXED_INCOME,
    "role": AssetClass.COMMODITY,
    "skill": AssetClass.CURRENCY,
}

_NON_MEANINGFUL_GROUPS = frozenset({"", "other", "unknown", "none", "n/a"})


class HumanResourcesDomainAdapter:
    """Non-financial DomainAdapter for workforce, org hierarchy, roles, and skills."""

    @property
    def domain_id(self) -> str:
        """Return the human_resources domain identifier."""
        return "human_resources"

    @property
    def entity_types(self) -> frozenset[str]:
        """Return supported Human Resources entity types."""
        return frozenset(_HR_ENTITY_TYPE_TO_CANONICAL_CLASS.keys())

    @property
    def predicate_ids(self) -> frozenset[str]:
        """Return supported Human Resources relationship predicates."""
        return frozenset(
            {
                "reports_to",
                "assigned_to_department",
                "holds_role",
                "has_skill",
                "successor_for",
                "same_department",
            }
        )

    def validate_entity(self, entity: DomainEntity) -> None:
        """Validate a Human Resources DomainEntity."""
        if not isinstance(entity.id, str) or not entity.id.strip():
            raise ValueError("Entity id must be a non-empty string")
        if not isinstance(entity.symbol, str) or not entity.symbol.strip():
            raise ValueError("Entity symbol must be a non-empty string")
        if not isinstance(entity.name, str) or not entity.name.strip():
            raise ValueError("Entity name must be a non-empty string")
        if entity.entity_type not in self.entity_types:
            raise ValueError(f"Unsupported human_resources entity_type: {entity.entity_type!r}")
        if not isinstance(entity.value, (int, float)) or isinstance(entity.value, bool) or entity.value < 0:
            raise ValueError("Entity value must be a non-negative number")

        for ref_key in ("manager_id", "department_id", "role_id", "successor_for_id"):
            if ref_key in entity.attributes:
                ref_val = entity.attributes[ref_key]
                if not isinstance(ref_val, str) or not ref_val.strip():
                    raise ValueError(f"Attribute '{ref_key}' must be a non-empty string")

        if "skill_ids" in entity.attributes:
            skill_ids = entity.attributes["skill_ids"]
            if not isinstance(skill_ids, (list, tuple)) or any(
                not isinstance(item, str) or not item.strip() for item in skill_ids
            ):
                raise ValueError("Attribute 'skill_ids' must be a list of non-empty strings")

    def build_edges(self, entities: Sequence[DomainEntity]) -> list[DomainEdge]:
        """Deterministically emit reporting, department, role, skill, and succession edges."""
        for entity in entities:
            self.validate_entity(entity)

        ordered = sorted(entities, key=lambda item: item.id)
        ids = {entity.id for entity in ordered}
        edges: list[DomainEdge] = []

        self._append_peer_department_edges(ordered, edges)
        for entity in ordered:
            self._append_reference_edges(entity, ids, edges)

        return edges

    @staticmethod
    def _append_peer_department_edges(ordered: Sequence[DomainEntity], edges: list[DomainEdge]) -> None:
        """Link employees in the same meaningful department group."""
        employees = [entity for entity in ordered if entity.entity_type == "employee"]
        for idx, left in enumerate(employees):
            left_group = left.group.strip().lower()
            if not left_group or left_group in _NON_MEANINGFUL_GROUPS:
                continue
            for right in employees[idx + 1 :]:
                if right.group.strip().lower() == left_group:
                    edges.append(
                        DomainEdge(
                            source_id=left.id,
                            target_id=right.id,
                            predicate_id="same_department",
                            strength=0.4,
                            bidirectional=True,
                        )
                    )

    @staticmethod
    def _append_reference_edges(entity: DomainEntity, ids: set[str], edges: list[DomainEdge]) -> None:
        """Emit directed reference edges declared in entity.attributes."""
        direct_mappings = (
            ("manager_id", "reports_to", 0.95),
            ("department_id", "assigned_to_department", 0.85),
            ("role_id", "holds_role", 0.90),
            ("successor_for_id", "successor_for", 0.80),
        )
        for attr_key, predicate_id, strength in direct_mappings:
            target_id = entity.attributes.get(attr_key)
            if isinstance(target_id, str) and target_id in ids and target_id != entity.id:
                edges.append(
                    DomainEdge(
                        source_id=entity.id,
                        target_id=target_id,
                        predicate_id=predicate_id,
                        strength=strength,
                        bidirectional=False,
                    )
                )

        skill_ids = entity.attributes.get("skill_ids", ())
        for skill_id in sorted(set(skill_ids)):
            if skill_id in ids and skill_id != entity.id:
                edges.append(
                    DomainEdge(
                        source_id=entity.id,
                        target_id=skill_id,
                        predicate_id="has_skill",
                        strength=0.75,
                        bidirectional=False,
                    )
                )

    def to_canonical_graph(self, entities: Sequence[DomainEntity]) -> AssetRelationshipGraph:
        """Project validated Human Resources entities into an AssetRelationshipGraph."""
        edges = self.build_edges(entities)
        graph = AssetRelationshipGraph()

        for entity in entities:
            asset = Asset(
                id=entity.id,
                symbol=entity.symbol,
                name=entity.name,
                asset_class=_HR_ENTITY_TYPE_TO_CANONICAL_CLASS[entity.entity_type],
                sector=entity.group or entity.entity_type,
                price=float(entity.value),
                currency="USD",
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
        """Return a deterministic Human Resources workforce graph sample."""
        return [
            DomainEntity(
                id="DEPT_ENG",
                symbol="ENG",
                name="Engineering",
                entity_type="department",
                group="Engineering",
                value=120.0,
            ),
            DomainEntity(
                id="ROLE_VP_ENG",
                symbol="VPENG",
                name="VP of Engineering",
                entity_type="role",
                group="Engineering",
                value=9.0,
                attributes={"department_id": "DEPT_ENG"},
            ),
            DomainEntity(
                id="ROLE_STAFF_ENG",
                symbol="STFENG",
                name="Staff Software Engineer",
                entity_type="role",
                group="Engineering",
                value=7.0,
                attributes={"department_id": "DEPT_ENG"},
            ),
            DomainEntity(
                id="SKILL_DIST_SYS",
                symbol="DISTSYS",
                name="Distributed Systems",
                entity_type="skill",
                group="Technical",
                value=1.0,
            ),
            DomainEntity(
                id="EMP_ALICE",
                symbol="ALICE",
                name="Alice Rivera",
                entity_type="employee",
                group="Engineering",
                value=1.0,
                attributes={
                    "department_id": "DEPT_ENG",
                    "role_id": "ROLE_VP_ENG",
                    "skill_ids": ["SKILL_DIST_SYS"],
                },
            ),
            DomainEntity(
                id="EMP_BOB",
                symbol="BOB",
                name="Bob Chen",
                entity_type="employee",
                group="Engineering",
                value=1.0,
                attributes={
                    "manager_id": "EMP_ALICE",
                    "department_id": "DEPT_ENG",
                    "role_id": "ROLE_STAFF_ENG",
                    "successor_for_id": "EMP_ALICE",
                    "skill_ids": ["SKILL_DIST_SYS"],
                },
            ),
        ]
