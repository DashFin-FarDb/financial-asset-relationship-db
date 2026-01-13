from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np

from src.models.financial_models import Asset, Bond, RegulatoryEvent


class AssetRelationshipGraph:
    """Interface used by visualization and reporting code.

    Attributes:
        assets: Dict[str, Asset] mapping asset IDs to Asset objects.
        relationships: Dict[source_id, List[(target_id, rel_type, strength)]]
        regulatory_events: List[RegulatoryEvent]
    """

    def __init__(self, database_url: str | None = None) -> None:
        self.assets: Dict[str, Asset] = {}
        self.relationships: Dict[str, List[Tuple[str, str, float]]] = {}
        self.regulatory_events: List[RegulatoryEvent] = []
        self.database_url = database_url

    def add_asset(self, asset: Asset) -> None:
        """Add an asset to the graph."""
        self.assets[asset.id] = asset

    def add_regulatory_event(self, event: RegulatoryEvent) -> None:
        """Add a regulatory event to the graph."""
        self.regulatory_events.append(event)

    def build_relationships(self) -> None:
        """Automatically discover relationships between assets based on business rules."""
        self.relationships = {}

        asset_ids = list(self.assets.keys())
        for i, id1 in enumerate(asset_ids):
            for id2 in asset_ids[i + 1 :]:
                asset1 = self.assets[id1]
                asset2 = self.assets[id2]

                # Rule 2: Sector Affinity
                if asset1.sector == asset2.sector and asset1.sector != "Unknown":
                    self.add_relationship(id1, id2, "same_sector", 0.7, bidirectional=True)

                # Rule 1: Corporate Bond Linkage
                if isinstance(asset1, Bond) and asset1.issuer_id == id2:
                    self.add_relationship(id1, id2, "corporate_link", 0.9, bidirectional=False)
                elif isinstance(asset2, Bond) and asset2.issuer_id == id1:
                    self.add_relationship(id2, id1, "corporate_link", 0.9, bidirectional=False)

        # Rule: Event Impact
        for event in self.regulatory_events:
            source_id = event.asset_id
            if source_id in self.assets:
                for target_id in event.related_assets:
                    if target_id in self.assets:
                        self.add_relationship(
                            source_id, target_id, "event_impact", abs(event.impact_score), bidirectional=False
                        )

    def add_relationship(
        self, source_id: str, target_id: str, rel_type: str, strength: float, bidirectional: bool = False
    ) -> None:
        """Manually add a relationship to the graph."""
        if source_id not in self.relationships:
            self.relationships[source_id] = []

        # Avoid duplicates
        if not any(r[0] == target_id and r[1] == rel_type for r in self.relationships[source_id]):
            self.relationships[source_id].append((target_id, rel_type, strength))

        if bidirectional:
            if target_id not in self.relationships:
                self.relationships[target_id] = []
            if not any(r[0] == source_id and r[1] == rel_type for r in self.relationships[target_id]):
                self.relationships[target_id].append((source_id, rel_type, strength))

    def calculate_metrics(self) -> Dict[str, Any]:
        """Calculate network statistics and distributions."""
        total_assets = len(self.assets)
        # For total_assets if no assets were explicitly added but exist in relationships
        all_ids = set(self.assets.keys())
        for rels in self.relationships.values():
            for target_id, _, _ in rels:
                all_ids.add(target_id)

        effective_assets_count = max(total_assets, len(all_ids))

        total_relationships = sum(len(rels) for rels in self.relationships.values())

        strengths = [r[2] for rels in self.relationships.values() for r in rels]
        avg_strength = sum(strengths) / len(strengths) if strengths else 0.0

        density = (
            (total_relationships / (effective_assets_count * (effective_assets_count - 1)) * 100)
            if effective_assets_count > 1
            else 0.0
        )

        rel_dist = {}
        all_rels = []
        for src, rels in self.relationships.items():
            for target, rtype, strength in rels:
                rel_dist[rtype] = rel_dist.get(rtype, 0) + 1
                all_rels.append((src, target, rtype, strength))

        all_rels.sort(key=lambda x: x[3], reverse=True)
        top_relationships = all_rels[:10]

        asset_class_dist = {}
        for asset in self.assets.values():
            ac = asset.asset_class.value
            asset_class_dist[ac] = asset_class_dist.get(ac, 0) + 1

        return {
            "total_assets": effective_assets_count,
            "total_relationships": total_relationships,
            "average_relationship_strength": avg_strength,
            "relationship_density": density,
            "relationship_distribution": rel_dist,
            "asset_class_distribution": asset_class_dist,
            "top_relationships": top_relationships,
            "regulatory_event_count": len(self.regulatory_events),
        }

    def get_3d_visualization_data_enhanced(self) -> Tuple[np.ndarray, List[str], List[str], List[str]]:
        """Return positions, asset_ids, colors, hover_texts for visualization."""
        all_ids = set(self.assets.keys())
        for rels in self.relationships.values():
            for target_id, _, _ in rels:
                all_ids.add(target_id)

        if not all_ids:
            positions = np.zeros((1, 3))
            return positions, ["A"], ["#888888"], ["Asset A"]

        asset_ids = sorted(all_ids)
        n = len(asset_ids)
        theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
        positions = np.stack([np.cos(theta), np.sin(theta), np.zeros_like(theta)], axis=1)
        colors = ["#4ECDC4"] * n
        hover = [f"Asset: {aid}" for aid in asset_ids]
        return positions, asset_ids, colors, hover
