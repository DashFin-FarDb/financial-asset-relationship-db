from __future__ import annotations

from typing import Any

import numpy as np

from src.models.financial_models import Asset, Bond, RegulatoryEvent

Relationship = tuple[str, str, float]
TopRelationship = tuple[str, str, str, float]


class AssetRelationshipGraph:
    """Graph of assets, relationships, and regulatory events for API and UI use."""

    def __init__(self, database_url: str | None = None) -> None:
        self.assets: dict[str, Asset] = {}
        self.relationships: dict[str, list[Relationship]] = {}
        self.regulatory_events: list[RegulatoryEvent] = []
        self.database_url = database_url

    def add_asset(self, asset: Asset) -> None:
        """Add or update an asset in the graph by id."""
        self.assets[asset.id] = asset

    def add_regulatory_event(self, event: RegulatoryEvent) -> None:
        """Append a regulatory event to the graph."""
        self.regulatory_events.append(event)

    def build_relationships(self) -> None:
        """Build relationships using sector, issuer linkage, and event impacts."""
        self.relationships = {}

        asset_ids = list(self.assets.keys())
        for idx, source_id in enumerate(asset_ids):
            for target_id in asset_ids[idx + 1 :]:
                asset1 = self.assets[source_id]
                asset2 = self.assets[target_id]

                if self._should_link_same_sector(asset1, asset2):
                    self.add_relationship(
                        source_id,
                        target_id,
                        "same_sector",
                        0.7,
                        bidirectional=True,
                    )

                issuer_link = self._issuer_link(asset1, asset2, source_id, target_id)
                if issuer_link is not None:
                    bond_id, issuer_id = issuer_link
                    self.add_relationship(
                        bond_id,
                        issuer_id,
                        "corporate_link",
                        0.9,
                        bidirectional=False,
                    )

        self._apply_event_impacts()

    def add_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        strength: float,
        bidirectional: bool = False,
    ) -> None:
        """Add a relationship, skipping duplicates and optionally adding its reverse."""
        self._append_relationship(source_id, target_id, rel_type, strength)
        if bidirectional:
            self._append_relationship(target_id, rel_type, source_id, strength)

    @staticmethod
    def _clamp01(value: float) -> float:
        """Clamp a float to the inclusive range [0.0, 1.0]."""
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value

    @staticmethod
    def _saturating_norm(count: int, k: float) -> float:
        """Map a non-negative count to (0, 1) using a saturating curve."""
        if count <= 0:
            return 0.0
        return count / (count + k)

    def calculate_metrics(self) -> dict[str, Any]:
        """Compute network metrics, distributions, and a simple quality score."""
        all_ids = self._collect_participating_asset_ids()
        effective_assets_count = len(all_ids)

        rel_dist: dict[str, int] = {}
        all_rels: list[TopRelationship] = []
        total_relationships = 0
        strength_sum = 0.0
        strength_count = 0

        for src, rels in self.relationships.items():
            total_relationships += len(rels)
            for target, rtype, strength in rels:
                rel_dist[rtype] = rel_dist.get(rtype, 0) + 1
                strength_f = float(strength)
                all_rels.append((src, target, rtype, strength_f))
                strength_sum += strength_f
                strength_count += 1

        avg_strength = (strength_sum / strength_count) if strength_count else 0.0
        density = self._relationship_density(effective_assets_count, total_relationships)

        all_rels.sort(key=lambda x: x[3], reverse=True)
        top_relationships = all_rels[:10]

        asset_class_dist = self._asset_class_distribution()
        reg_events = len(self.regulatory_events)

        k = 10.0
        w_strength = 0.7
        w_events = 0.3
        avg_strength_n = self._clamp01(avg_strength)
        reg_events_norm = self._saturating_norm(reg_events, k)
        quality_score = self._clamp01((w_strength * avg_strength_n) + (w_events * reg_events_norm))

        return {
            "total_assets": effective_assets_count,
            "total_relationships": total_relationships,
            "average_relationship_strength": avg_strength,
            "relationship_density": density,
            "relationship_distribution": rel_dist,
            "asset_class_distribution": asset_class_dist,
            "top_relationships": top_relationships,
            "regulatory_event_count": reg_events,
            "regulatory_event_norm": reg_events_norm,
            "quality_score": quality_score,
        }

    def get_3d_visualization_data_enhanced(
        self,
    ) -> tuple[np.ndarray, list[str], list[str], list[str]]:
        """Return positions, ids, colours, and hover text for 3D visualisation."""
        asset_ids = sorted(self._collect_participating_asset_ids())
        if not asset_ids:
            positions = np.zeros((1, 3))
            return positions, ["A"], ["#888888"], ["Asset A"]

        n = len(asset_ids)
        theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
        positions = np.stack((np.cos(theta), np.sin(theta), np.zeros_like(theta)), axis=1)

        colors = ["#4ECDC4"] * n
        hover = [f"Asset: {aid}" for aid in asset_ids]
        return positions, asset_ids, colors, hover

    @staticmethod
    def _should_link_same_sector(asset1: Asset, asset2: Asset) -> bool:
        """Return True when both assets share a meaningful sector."""
        return asset1.sector == asset2.sector and asset1.sector != "Unknown"

    @staticmethod
    def _issuer_link(asset1: Asset, asset2: Asset, id1: str, id2: str) -> tuple[str, str] | None:
        """Return (bond_id, issuer_id) if a bond-to-issuer link exists."""
        if isinstance(asset1, Bond) and asset1.issuer_id == id2:
            return (id1, id2)
        if isinstance(asset2, Bond) and asset2.issuer_id == id1:
            return (id2, id1)
        return None

    def _apply_event_impacts(self) -> None:
        """Add event-driven relationships from events to their related assets."""
        for event in self.regulatory_events:
            source_id = event.asset_id
            if source_id not in self.assets:
                continue
            for target_id in event.related_assets:
                if target_id not in self.assets:
                    continue
                self.add_relationship(
                    source_id,
                    target_id,
                    "event_impact",
                    abs(event.impact_score),
                    bidirectional=False,
                )

    def _append_relationship(self, source_id: str, target_id: str, rel_type: str, strength: float) -> None:
        """Append a relationship to a source list if not already present."""
        rels = self.relationships.setdefault(source_id, [])
        if any(t == target_id and rt == rel_type for t, rt, _ in rels):
            return
        rels.append((target_id, rel_type, strength))

    def _collect_participating_asset_ids(self) -> set[str]:
        """Return ids from assets plus relationship targets."""
        all_ids = set(self.assets.keys())
        for rels in self.relationships.values():
            for target_id, _, _ in rels:
                all_ids.add(target_id)
        return all_ids

    def _asset_class_distribution(self) -> dict[str, int]:
        """Return a distribution of asset_class.value across stored assets."""
        dist: dict[str, int] = {}
        for asset in self.assets.values():
            key = asset.asset_class.value
            dist[key] = dist.get(key, 0) + 1
        return dist

    @staticmethod
    def _relationship_density(asset_count: int, rel_count: int) -> float:
        """Return relationship density as a percentage of max directed edges."""
        if asset_count <= 1:
            return 0.0
        max_possible = asset_count * (asset_count - 1)
        return (rel_count / max_possible) * 100.0
