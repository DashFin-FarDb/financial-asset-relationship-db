from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np

from src.models.financial_models import Asset, Bond, RegulatoryEvent


class AssetRelationshipGraph:
    """
    Interface used by visualization and reporting code.

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
        """
        Automatically discover relationships between assets
        based on business rules.
        """
        self.relationships = {}

        asset_ids = list(self.assets.keys())
        for i, id1 in enumerate(asset_ids):
            for id2 in asset_ids[i + 1 :]:
                asset1 = self.assets[id1]
                asset2 = self.assets[id2]

                # Rule 2: Sector Affinity
                if asset1.sector == asset2.sector and asset1.sector != "Unknown":
                    self.add_relationship(
                        id1,
                        id2,
                        "same_sector",
                        0.7,
                        bidirectional=True,
                    )

                # Rule 1: Corporate Bond Linkage
                if isinstance(asset1, Bond) and asset1.issuer_id == id2:
                    self.add_relationship(
                        id1,
                        id2,
                        "corporate_link",
                        0.9,
                        bidirectional=False,
                    )
                elif isinstance(asset2, Bond) and asset2.issuer_id == id1:
                    self.add_relationship(
                        id2,
                        id1,
                        "corporate_link",
                        0.9,
                        bidirectional=False,
                    )

        # Rule: Event Impact
        for event in self.regulatory_events:
            source_id = event.asset_id
            if source_id in self.assets:
                for target_id in event.related_assets:
                    if target_id in self.assets:
                        self.add_relationship(
                            source_id,
                            target_id,
                            "event_impact",
                            abs(event.impact_score),
                            bidirectional=False,
                        )

    def add_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        strength: float,
        bidirectional: bool = False,
    ) -> None:
        """
        Add a directed relationship from source_id to target_id in the graph.

        This mutates the instance's relationships mapping by appending a
        (target_id, rel_type, strength) entry for source_id if an entry
        with the same target and relation type does not already exist.

        If bidirectional is True, the mirror relationship
        (source_id, rel_type, strength) is added for target_id using the
        same duplicate check.

        Parameters:
            source_id (str): ID of the source asset.
            target_id (str): ID of the target asset.
            rel_type (str): Relationship type label.
            strength (float): Numeric strength of the relationship,
                normalised to the range 0.0–1.0.
            bidirectional (bool): If True, also add the reverse
                relationship with the same type and strength.
        """
        if source_id not in self.relationships:
            self.relationships[source_id] = []

        # Avoid duplicates
        if not any(
            r[0] == target_id and r[1] == rel_type
            for r in self.relationships[source_id]
        ):
            self.relationships[source_id].append((target_id, rel_type, strength))

        if bidirectional:
            if target_id not in self.relationships:
                self.relationships[target_id] = []
            if not any(
                r[0] == source_id and r[1] == rel_type
                for r in self.relationships[target_id]
            ):
                self.relationships[target_id].append((source_id, rel_type, strength))

    @staticmethod
    def _clamp01(value: float) -> float:
        """Clamp a float to the [0, 1] interval."""
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value

    @staticmethod
    def _saturating_norm(count: int, k: float) -> float:
        """Bounded monotone normalization for non-negative counts."""
        if count <= 0:
            return 0.0
        return count / (count + k)

    def calculate_metrics(self) -> Dict[str, Any]:
        """
        Compute network-wide metrics and distributions for the asset relationship graph.

        Returns:
            A mapping containing:
                total_assets (int): Number of distinct assets considered (includes assets
                    discovered from relationships).
                total_relationships (int): Total number of directed relationship entries.
                average_relationship_strength (float): Mean of all relationship strength values
                    (0.0 if none).
                relationship_density (float): Percentage (0–100) of existing relationships relative
                    to the maximum possible directed relationships between considered assets.
                relationship_distribution (Dict[str, int]): Counts of relationships grouped by type.
                asset_class_distribution (Dict[str, int]): Counts of assets grouped by asset_class.value.
                top_relationships (List[Tuple[str, str, str, float]]): Up to 10 relationships sorted by
                    descending strength: (source_id, target_id, relation_type, strength).
                regulatory_event_count (int): Number of regulatory events stored.
                regulatory_event_norm (float): Normalized regulatory event signal (0–1).
                quality_score (float): Overall data-quality score (0–1), computed in the metrics layer.
        """
        # Collect all asset IDs that participate in the graph (explicit assets + relationship targets).
        all_ids = set(self.assets.keys())
        for rels in self.relationships.values():
            for target_id, _, _ in rels:
                all_ids.add(target_id)

        effective_assets_count = len(all_ids)

        # Count relationships and gather strengths + relationship distribution + top relationships.
        total_relationships = 0
        strength_sum = 0.0
        strength_count = 0

        rel_dist: Dict[str, int] = {}
        all_rels: List[Tuple[str, str, str, float]] = []

        for src, rels in self.relationships.items():
            total_relationships += len(rels)
            for target, rtype, strength in rels:
                rel_dist[rtype] = rel_dist.get(rtype, 0) + 1
                all_rels.append((src, target, rtype, float(strength)))
                strength_sum += float(strength)
                strength_count += 1

        avg_strength = (strength_sum / strength_count) if strength_count else 0.0

        # Density as percentage (0–100) of the maximum possible directed edges (n*(n-1)).
        if effective_assets_count > 1:
            max_possible = effective_assets_count * (effective_assets_count - 1)
            density = (total_relationships / max_possible) * 100.0
        else:
            density = 0.0

        all_rels.sort(key=lambda x: x[3], reverse=True)
        top_relationships = all_rels[:10]

        # Asset class distribution uses explicitly stored assets only.
        asset_class_dist: Dict[str, int] = {}
        for asset in self.assets.values():
            ac = asset.asset_class.value
            asset_class_dist[ac] = asset_class_dist.get(ac, 0) + 1

        # Data-quality score: keep definition out of reports/UI.
        reg_events = len(self.regulatory_events)

        # Tunables: stable defaults; adjust later if you want.
        k = 10.0
        w_strength = 0.7
        w_events = 0.3

        avg_strength_n = self._clamp01(avg_strength)
        reg_events_norm = self._saturating_norm(reg_events, k)
        quality_score = self._clamp01(
            (w_strength * avg_strength_n) + (w_events * reg_events_norm)
        )

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
    ) -> Tuple[np.ndarray, List[str], List[str], List[str]]:
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
        positions = np.stack(
            [
                np.cos(theta),
                np.sin(theta),
                np.zeros_like(theta),
            ],
            axis=1,
        )
        colors = ["#4ECDC4"] * n
        hover = [f"Asset: {aid}" for aid in asset_ids]
        return positions, asset_ids, colors, hover
