from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np

from src.models.financial_models import Asset, Bond, RegulatoryEvent


class AssetRelationshipGraph:
    """
    Interface used by visualization and reporting code.



    Attributes:
        assets: dict[str, Asset] mapping asset IDs to Asset objects.
        relationships: dict[source_id, List[(target_id, rel_type, strength)]]
        regulatory_events: List[RegulatoryEvent]
    """

    def __init__(self, database_url: str | None = None) -> None:
        self.assets: dict[str, Asset] = {}
        self.relationships: dict[str, List[Tuple[str, str, float]]] = {}
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
        Discover and populate asset relationships using built-in business rules.

        This clears existing relationships and adds edges between assets present
        in the graph according to three rules:
        - Same-sector: adds a bidirectional "same_sector" relationship with
          strength 0.7 for assets that share the same sector (excluding
          "Unknown").
        - Corporate bond linkage: when a Bond's issuer_id matches another
          asset's id, adds a unidirectional "corporate_link" from the bond to
          its issuer with strength 0.9.
        - Regulatory event impact: for each RegulatoryEvent whose source asset
          and related assets exist in the graph, adds a unidirectional
          "event_impact" relationship from the event's asset to each related
          asset with strength equal to the absolute value of the event's
          impact_score.

        Only relationships between assets present in self.assets are created.
        """
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
        Add a relationship from source_id to target_id in the graph.

        Parameters:
            source_id (str): ID of the source asset.
            target_id (str): ID of the target asset.
            rel_type (str): Relationship type label. For example,
                "same_sector", "corporate_link", "event_impact".
            strength (float): Numeric strength for the relationship; stored as
                provided.
            bidirectional (bool): If True, also adds the same relationship from
                target_id back to source_id.

        Notes:
            Duplicate entries with the same source, target, and rel_type are
            ignored.
        """
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

    def calculate_metrics(self) -> dict[str, Any]:
        """
        Compute network-level metrics and distributions
        for the asset relationship graph.

        Returns:
            metrics (dict): A dictionary containing:
                total_assets (int): Effective number of assets. This is the max of
                    explicitly added assets and any asset IDs appearing in
                    relationships.
                total_relationships (int): Total number of relationship entries
                    across all sources.
                average_relationship_strength (float): Mean strength of all
                    relationships (0.0 if none).
                relationship_density (float): Percentage (0-100) of actual
                    relationships relative to possible directed edges among
                    effective assets.
                relationship_distribution (dict[str, int]): Counts of
                    relationships keyed by relationship type.
                asset_class_distribution (dict[str, int]): Counts of assets
                    keyed by their asset_class value.
                top_relationships (List[Tuple[str, str, str, float]]): Up to 10
                    relationships sorted by strength descending; each tuple is
                    (source_id, target_id, rel_type, strength).
                regulatory_event_count (int): Number of stored regulatory events.
        """
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

    def get_3d_visualization_data_enhanced(
        self,
    ) -> Tuple[np.ndarray, List[str], List[str], List[str]]:
        """
        Prepare 3D layout data for visualizing assets and their relationships.

        Returns:
            positions (np.ndarray): Array of shape (n, 3) containing XYZ
                coordinates for each asset. Positions lie on the unit circle
                in the XY plane (z = 0). If there are no assets, returns an
                array with a single zeroed position of shape (1, 3).
            asset_ids (List[str]): Sorted list of asset IDs included in the
                layout. Includes assets that appear only as relationship
                targets. If there are no assets, returns ["A"].
            colors (List[str]): Hex color string for each asset, one-to-one
                with `asset_ids`. Defaults to "#4ECDC4" for normal assets;
                in the no-assets case returns ["#888888"].
            hover_texts (List[str]): Hover label for each asset in the form
                "Asset: <asset_id>". In the no-assets case returns ["Asset A"].
        """
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
