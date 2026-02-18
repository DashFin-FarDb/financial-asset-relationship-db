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
        Initialize an AssetRelationshipGraph and its internal state.

        Parameters:
            database_url (str | None): Optional database connection URL used
                for external persistence;
                stored but not connected to during initialization.

        Attributes initialized:
            assets: Mapping of asset_id to Asset.
            relationships: Mapping of source asset_id to a list of relationship tuples.
            regulatory_events: List of RegulatoryEvent instances.
        """
        self.assets: dict[str, Asset] = {}
        self.relationships: dict[str, list[Relationship]] = {}
        self.regulatory_events: list[RegulatoryEvent] = []
        self.database_url = database_url

    def add_asset(self, asset: Asset) -> None:
        """Add or update an asset in the graph by id."""
        self.assets[asset.id] = asset

    def add_regulatory_event(self, event: RegulatoryEvent) -> None:
        """
        Record a regulatory event in the graph's internal event list.

        Parameters:
            event (RegulatoryEvent): The regulatory event to record; it will be
                retained for subsequent processing of event-driven impacts.
        """
        self.regulatory_events.append(event)

    def build_relationships(self) -> None:
        """
        Build or rebuild the relationship graph based on current assets and
        recorded regulatory events.

        This method:
            * Clears existing relationships.
            * Links assets that share sectors.
            * Links bonds to issuers where applicable.
            * Applies the impact of any recorded regulatory events.
        """
        # Reset existing relationships before rebuilding.
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
        Add a relationship from one asset to another and optionally
        add the reverse relationship.

        Duplicates are ignored for the same (target_id, rel_type) pair
        so existing identical relationships are not added again.

        Parameters:
            source_id (str): ID of the source asset.
            target_id (str): ID of the target asset.
            rel_type (str): Relationship type label.
            strength (float): Relationship strength (expected on a 0.0–1 scale).
            bidirectional (bool): If True, also add the same relationship from
                `target_id` back to `source_id`.
        """
        self._append_relationship(source_id, target_id, strength, rel_type)
        if bidirectional:
            self._append_relationship(target_id, source_id, strength, rel_type)

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
        """
        Convert a non-negative count into a normalized value between 0 and 1
        using a saturating curve.

        Parameters:
            count (int): Non-negative integer count. If count <= 0, the function
                returns 0.0.
            k (float): Saturation constant that controls how quickly the value
                approaches 1.0.

        Returns:
            float: A normalized value in [0.0, 1.0]. Computed as count /
                (count + k). Returns 0.0 when count <= 0.
        """
        if count <= 0:
            return 0.0
        return count / (count + k)

    def calculate_metrics(self) -> dict[str, Any]:
        """
        Compute network and quality metrics for the current asset graph.

        Returns:
            metrics (dict[str, Any]): A dictionary containing:
                - total_assets: number of participating assets (assets plus
                  relationship targets).
                - total_relationships: total count of stored relationships
                  (directed).
                - average_relationship_strength: mean strength across all
                  relationships (0.0 if none).
                - relationship_density: network density as a percentage of
                  possible directed edges.
                - relationship_distribution: mapping from relationship type to
                  occurrence count.
                - asset_class_distribution: mapping from asset class value to
                  count of assets.
                - top_relationships: list of up to 10 strongest relationships
                  as tuples (source_id, target_id, relationship_type, strength)
                  sorted by strength desc.
                - regulatory_event_count: number of stored regulatory events.
                - regulatory_event_norm: normalized regulatory event score in
                  (0,1) via a saturating curve.
                - quality_score: aggregated quality metric in [0.0, 1.0]
                  combining normalized average strength and regulatory events.
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
        Produce 3D positions, identifiers, colors, and hover labels
        for visualization.

        If no participating assets exist, returns a single origin position
        with a placeholder id, color, and label.

        Returns:
            positions (np.ndarray): An N x 3 array of XYZ
            coordinates for each asset (N >= 1).
            asset_ids (list[str]): Ordered list of asset identifiers
            corresponding to rows in `positions`.
            colors (list[str]): Hex color strings for each asset.
            hover_text (list[str]): Hover labels for each asset.
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
        Determine whether two assets share the same sector other than "Unknown".

        Returns:
            True if both assets have the same sector and that sector is not "Unknown",
            False otherwise.
        """
        return asset1.sector == asset2.sector and asset1.sector != "Unknown"

    @staticmethod
    def _issuer_link(
        asset1: Asset, asset2: Asset, id1: str, id2: str
    ) -> tuple[str, str] | None:
        """
        Identify a bond-to-issuer relationship between two assets.

        Returns:
            tuple[str, str] | None:
            `(bond_id, issuer_id)` if one asset is a `Bond` whose
            `issuer_id` equals the other's id, `None` otherwise.
        """
        if isinstance(asset1, Bond) and asset1.issuer_id == id2:
            return (id1, id2)
        if isinstance(asset2, Bond) and asset2.issuer_id == id1:
            return (id2, id1)
        return None

    def _apply_event_impacts(self) -> None:
        """
        Add non-bidirectional "event_impact" relationships from each regulatory
        event's asset to its related assets.

        For each RegulatoryEvent in self.regulatory_events, if the event's
        asset_id and a related asset_id both exist in self.assets, add a
        relationship of type "event_impact" from the event asset to the related
        asset with strength equal to the absolute value of
        event.impact_score.
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
        Add a relationship from source_id to target_id if a relationship with the same
            target and type does not already exist.

        Parameters:
            source_id (str): ID of the source asset whose relationship list will
                be updated.
            target_id (str): ID of the target asset for the relationship.
            rel_type (str): Relationship type label.
            strength (float): Strength value for the relationship (0.0 to 1.0).
        """
        rels = self.relationships.setdefault(source_id, [])
        if any(t == target_id and rt == rel_type for t, rt, _ in rels):
            return
        rels.append((target_id, rel_type, strength))

    def _collect_participating_asset_ids(self) -> set[str]:
        """
        Collect all asset IDs present in the graph, including assets stored in the
        graph and any target IDs referenced by relationships.

        Returns:
            set[str]: A set of asset IDs that appear either as keys in `self.assets`
                or as target IDs in `self.relationships`.
        """
        all_ids = set(self.assets.keys())
        for rels in self.relationships.values():
            for target_id, _, _ in rels:
                all_ids.add(target_id)
        return all_ids

    def _asset_class_distribution(self) -> dict[str, int]:
        """
        Compute the distribution of asset classes among stored assets.

        Returns:
            dict[str, int]: Mapping from each `asset_class.value` to the count of assets
                with that class.
        """
        dist: dict[str, int] = {}
        for asset in self.assets.values():
            key = asset.asset_class.value
            dist[key] = dist.get(key, 0) + 1
        return dist

    @staticmethod
    def _relationship_density(asset_count: int, rel_count: int) -> float:
        """
        Compute the relationship density as the percentage of existing relationships
        versus the maximum possible directed edges between assets.

        Returns:
            float: Percentage of existing relationships relative to
                   the maximum possible directed edges (0.0–100.0).
        """
        if asset_count <= 1:
            return 0.0
        max_possible = asset_count * (asset_count - 1)
        return (rel_count / max_possible) * 100.0
