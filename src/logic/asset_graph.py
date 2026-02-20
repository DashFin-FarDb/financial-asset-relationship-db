from __future__ import annotations

from typing import Any

import numpy as np

from src.models.financial_models import Asset, Bond, RegulatoryEvent

Relationship = tuple[str, str, float]
TopRelationship = tuple[str, str, str, float]


class AssetRelationshipGraph:
    """Graph of assets, relationships, and regulatory events for API and UI use."""

    def __init__(self, database_url: str | None = None) -> None:
        """
        Initialize AssetRelationshipGraph internal state.
        
        Sets up empty containers for assets, relationships, and regulatory events, and stores the optional database connection URL.
        
        Parameters:
            database_url (str | None): Optional database connection URL associated with the graph.
        """
        self.assets: dict[str, Asset] = {}
        self.relationships: dict[str, list[Relationship]] = {}
        self.regulatory_events: list[RegulatoryEvent] = []
        self.database_url = database_url

    def add_asset(self, asset: Asset) -> None:
        """
        Add or update an asset in the graph using the asset's id as the key.
        
        Parameters:
            asset (Asset): The asset to store; it will be indexed in the graph by asset.id.
        """
        self.assets[asset.id] = asset

    def add_regulatory_event(self, event: RegulatoryEvent) -> None:
        """
        Record a regulatory event in the graph's event list.
        
        Parameters:
            event (RegulatoryEvent): The regulatory event to append; it will be stored for later impact processing.
        """
        self.regulatory_events.append(event)

    def build_relationships(self) -> None:
        """
        Rebuilds the graph's relationships from current assets and regulatory events.
        
        Clears existing relationships, then for each unordered pair of assets:
        - Adds a bidirectional "same_sector" relationship with strength 0.7 if both assets share a known sector.
        - Adds a one-way "corporate_link" relationship with strength 0.9 from a bond to its issuer when an issuer linkage is detected.
        
        After pairwise processing, applies regulatory event impacts which may add "event_impact" relationships for affected assets.
        """
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
        """
        Add a relationship from one asset to another.
        
        Skips adding a duplicate relationship that has the same target and type. If `bidirectional` is True, also adds the reverse relationship.
        
        Parameters:
            source_id (str): ID of the source asset.
            target_id (str): ID of the target asset.
            rel_type (str): Relationship type label.
            strength (float): Relationship strength (expected in the range 0.0–1.0).
            bidirectional (bool): If True, add the same relationship in the opposite direction.
        """
        self._append_relationship(source_id, target_id, rel_type, strength)
        if bidirectional:
            self._append_relationship(target_id, source_id, rel_type, strength)

    @staticmethod
    def _clamp01(value: float) -> float:
        """
        Clamp a float to the inclusive range 0.0 to 1.0.
        
        Returns:
            float: The input value constrained to the range 0.0 through 1.0.
        """
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value

    @staticmethod
    def _saturating_norm(count: int, k: float) -> float:
        """
        Convert a non-negative count to a bounded score using a saturating curve.
        
        Parameters:
            count (int): The non-negative count to normalize. Values <= 0 produce 0.0.
            k (float): Saturation constant that controls the curve; larger values reduce the normalized result.
        
        Returns:
            float: A normalized score in [0.0, 1.0). Returns `0.0` if `count <= 0`, otherwise `count / (count + k)`.
        """
        if count <= 0:
            return 0.0
        return count / (count + k)

    def calculate_metrics(self) -> dict[str, Any]:
        """
        Compute aggregate network metrics, distributions, and a composite quality score for the asset graph.
        
        Returns:
            metrics (dict[str, Any]): Dictionary containing computed metrics:
                - total_assets: Number of participating assets (including targets referenced by relationships).
                - total_relationships: Total number of directed relationships stored.
                - average_relationship_strength: Mean strength value across all relationships (0.0 if none).
                - relationship_density: Density percentage of directed relationships relative to the maximum possible.
                - relationship_distribution: Mapping from relationship type to its count.
                - asset_class_distribution: Mapping from asset class value to the count of assets in that class.
                - top_relationships: List of up to 10 top relationships sorted by strength; each item is a tuple
                  (source_id, target_id, relationship_type, strength).
                - regulatory_event_count: Count of regulatory events stored.
                - regulatory_event_norm: Normalized regulatory event score produced by a saturating function.
                - quality_score: Combined quality score (clamped to [0.0, 1.0]) that weights average relationship
                  strength and normalized regulatory event impact.
        """
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
        density = self._relationship_density(
            effective_assets_count, total_relationships
        )

        all_rels.sort(key=lambda x: x[3], reverse=True)
        top_relationships = all_rels[:10]

        asset_class_dist = self._asset_class_distribution()
        reg_events = len(self.regulatory_events)

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
    ) -> tuple[np.ndarray, list[str], list[str], list[str]]:
        """
        Produce positions, asset ids, colors, and hover labels for 3D visualization.
        
        Returns:
            tuple: A 4-tuple containing:
                - positions (numpy.ndarray): An N×3 array of XYZ coordinates for N assets (z=0 for all points).
                - ids (list[str]): Asset ids in the same order as `positions`.
                - colors (list[str]): Hex color strings for each asset, same length as `ids`.
                - hover (list[str]): Hover text labels for each asset, same length as `ids`.
        
            If there are no participating assets, returns a default single position with:
                - positions shape (1, 3), ids ["A"], colors ["#888888"], hover ["Asset A"].
        """
        asset_ids = sorted(self._collect_participating_asset_ids())
        if not asset_ids:
            positions = np.zeros((1, 3))
            return positions, ["A"], ["#888888"], ["Asset A"]

        n = len(asset_ids)
        theta = np.linspace(0, 2 * np.pi, n, endpoint=False)
        positions = np.stack(
            (np.cos(theta), np.sin(theta), np.zeros_like(theta)), axis=1
        )

        colors = ["#4ECDC4"] * n
        hover = [f"Asset: {aid}" for aid in asset_ids]
        return positions, asset_ids, colors, hover

    @staticmethod
    def _should_link_same_sector(asset1: Asset, asset2: Asset) -> bool:
        """
        Determine whether two assets belong to the same known sector.
        
        Parameters:
            asset1 (Asset): First asset to compare.
            asset2 (Asset): Second asset to compare.
        
        Returns:
            bool: `True` if both assets have the same sector string and that sector is not "Unknown", `False` otherwise.
        """
        return asset1.sector == asset2.sector and asset1.sector != "Unknown"

    @staticmethod
    def _issuer_link(
        asset1: Asset, asset2: Asset, id1: str, id2: str
    ) -> tuple[str, str] | None:
        """
        Detects a bond-to-issuer linkage between two assets.
        
        Returns:
            tuple[str, str]: `(bond_id, issuer_id)` when one asset is a Bond whose `issuer_id` equals the other's id, `None` otherwise.
        """
        if isinstance(asset1, Bond) and asset1.issuer_id == id2:
            return (id1, id2)
        if isinstance(asset2, Bond) and asset2.issuer_id == id1:
            return (id2, id1)
        return None

    def _apply_event_impacts(self) -> None:
        """
        Add relationships representing regulatory event impacts between assets.
        
        For each regulatory event, if the event's asset_id and each related asset exist in the graph, add a one-way relationship from the event's asset to the related asset of type "event_impact" with strength equal to the absolute value of the event's impact_score. Events referencing missing assets are ignored.
        """
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

    def _append_relationship(
        self, source_id: str, target_id: str, rel_type: str, strength: float
    ) -> None:
        """
        Ensure a relationship from source to target is recorded in the graph if an identical relationship does not already exist.
        
        Parameters:
            source_id (str): ID of the source asset whose relationship list will be updated.
            target_id (str): ID of the target asset for the relationship.
            rel_type (str): Relationship type label (e.g., "same_sector", "corporate_link", "event_impact").
            strength (float): Numeric strength of the relationship; stored as provided.
        
        Notes:
            The relationship is stored as a tuple (target_id, rel_type, strength). If a relationship with the same target_id and rel_type already exists for the source, this call has no effect.
        """
        rels = self.relationships.setdefault(source_id, [])
        if any(t == target_id and rt == rel_type for t, rt, _ in rels):
            return
        rels.append((target_id, rel_type, strength))

    def _collect_participating_asset_ids(self) -> set[str]:
        """
        Collect participating asset IDs from stored assets and relationship targets.
        
        Returns:
            ids (set[str]): Asset IDs present as keys in `self.assets` or as target IDs referenced in `self.relationships`.
        """
        all_ids = set(self.assets.keys())
        for rels in self.relationships.values():
            for target_id, _, _ in rels:
                all_ids.add(target_id)
        return all_ids

    def _asset_class_distribution(self) -> dict[str, int]:
        """
        Count assets grouped by their asset_class value.
        
        Returns:
            distribution (dict[str, int]): Mapping from each `asset_class.value` to the number of assets with that class.
        """
        dist: dict[str, int] = {}
        for asset in self.assets.values():
            key = asset.asset_class.value
            dist[key] = dist.get(key, 0) + 1
        return dist

    @staticmethod
    def _relationship_density(asset_count: int, rel_count: int) -> float:
        """
        Compute the relationship density as the percentage of possible directed edges present.
        
        Parameters:
            asset_count (int): Number of distinct assets in the graph.
            rel_count (int): Number of directed relationships currently present.
        
        Returns:
            float: Percentage (0.0 to 100.0) of actual directed relationships relative to the maximum possible directed edges. Returns 0.0 if `asset_count` is 1 or less.
        """
        if asset_count <= 1:
            return 0.0
        max_possible = asset_count * (asset_count - 1)
        return (rel_count / max_possible) * 100.0