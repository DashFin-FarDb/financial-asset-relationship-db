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
        Create a new AssetRelationshipGraph and initialize its in-memory stores and optional persistence URL.

        Initializes:
        - assets: mapping of asset id to Asset instances.
        - relationships: adjacency mapping from source asset id to a list of Relationship tuples (target_id, rel_type, strength).
        - regulatory_events: list of RegulatoryEvent objects affecting relationships and metrics.
        - database_url: optional connection string used for external persistence or integration.

        Parameters:
            database_url (str | None): Optional database connection URL or None if no persistence is configured.
        """
        self.assets: dict[str, Asset] = {}
        self.relationships: dict[str, list[Relationship]] = {}
        self.regulatory_events: list[RegulatoryEvent] = []
        self.database_url = database_url

    def add_asset(self, asset: Asset) -> None:
        """
        Add or update an asset in the graph keyed by the asset's `id`.

        Parameters:
            asset (Asset): The asset to store; saved under `asset.id`, replacing any existing asset with the same id.
        """
        self.assets[asset.id] = asset

    def add_regulatory_event(self, event: RegulatoryEvent) -> None:
        """
        Add a regulatory event to the graph's stored events.

        Parameters:
            event (RegulatoryEvent): The regulatory event to record; it is stored in the graph's internal regulatory_events list.
        """
        self.regulatory_events.append(event)

    def build_relationships(self) -> None:
        """
        Rebuild the internal relationships map between stored assets based on sector membership, issuer links, and regulatory events.

        This resets the graph's relationships, then:
        - adds bidirectional "same_sector" relationships (strength 0.7) for assets that share a known sector;
        - adds a directed "corporate_link" (strength 0.9) from a bond to its issuer when applicable;
        - applies stored regulatory events to add directed "event_impact" relationships whose strength equals the absolute value of each event's impact_score.
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
        Add a relationship between two assets, avoiding duplicate entries and optionally adding the reverse link.

        Parameters:
            source_id (str): ID of the source asset.
            target_id (str): ID of the target asset.
            rel_type (str): Relationship type label (e.g., "same_sector", "corporate_link", "event_impact").
            strength (float): Relationship strength; expected on a 0.0–1.0 scale.
            bidirectional (bool): If True, also add the same relationship from target to source.
        """
        self._append_relationship(source_id, target_id, rel_type, strength)
        if bidirectional:
            self._append_relationship(target_id, source_id, rel_type, strength)

    @staticmethod
    def _clamp01(value: float) -> float:
        """
        Clamp value to the inclusive range 0.0 to 1.0.

        Returns:
            float: The input value constrained to be between 0.0 and 1.0 (inclusive).
        """
        if value < 0.0:
            return 0.0
        if value > 1.0:
            return 1.0
        return value

    @staticmethod
    def _saturating_norm(count: int, k: float) -> float:
        """
        Map a non-negative count to a normalized value that saturates below 1.

        Parameters:
            count (int): The integer count to normalize; non-positive values yield 0.0.
            k (float): Positive smoothing constant controlling the saturation rate; larger k slows the approach to 1.

        Returns:
            float: `0.0` if count <= 0; otherwise a value greater than 0.0 and strictly less than 1.0 given by count / (count + k).
        """
        if count <= 0:
            return 0.0
        return count / (count + k)

    def calculate_metrics(self) -> dict[str, Any]:
        """
        Compute summary network metrics for the current asset graph, including distributions and a composite quality score.

        Returns:
            metrics (dict[str, Any]): A dictionary with the following keys:
                - total_assets (int): Number of distinct assets participating in the graph (nodes).
                - total_relationships (int): Total count of directed relationships (edges).
                - average_relationship_strength (float): Mean strength across all recorded relationships.
                - relationship_density (float): Directed edge density as a fraction of the maximum possible (0.0–1.0).
                - relationship_distribution (dict[str, int]): Mapping from relationship type to its occurrence count.
                - asset_class_distribution (dict[str, int]): Mapping from asset class name to its count among stored assets.
                - top_relationships (list[tuple[str, str, str, float]]): Up to 10 relationships sorted by strength descending; each tuple is (source_id, target_id, relationship_type, strength).
                - regulatory_event_count (int): Number of stored regulatory events.
                - regulatory_event_norm (float): Normalized regulatory event metric in (0.0–1.0) computed with a saturating curve.
                - quality_score (float): Composite quality score in [0.0, 1.0] combining normalized average strength and regulatory event norm.
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
        """
        Provide node positions and labels for 3D visualization of the asset graph.

        Positions are laid out on a circle in the XY plane (z = 0). If there are no participating assets, returns a single zero position and placeholder labels.

        Returns:
            positions (np.ndarray): Array of shape (n, 3) with 3D coordinates for n nodes.
            asset_ids (list[str]): Ordered list of asset IDs corresponding to positions.
            colors (list[str]): Hex color strings for each node.
            hover (list[str]): Hover text labels for each node.
        """
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
        """
        Determine whether two assets share the same meaningful sector.

        Returns:
            `true` if both assets have the same sector and that sector is not "Unknown", `false` otherwise.
        """
        return asset1.sector == asset2.sector and asset1.sector != "Unknown"

    @staticmethod
    def _issuer_link(asset1: Asset, asset2: Asset, id1: str, id2: str) -> tuple[str, str] | None:
        """
        Identify a bond-to-issuer relationship between two assets.

        @returns `(bond_id, issuer_id)` if one asset is a `Bond` whose `issuer_id` matches the other's id, `None` otherwise.
        """
        if isinstance(asset1, Bond) and asset1.issuer_id == id2:
            return (id1, id2)
        if isinstance(asset2, Bond) and asset2.issuer_id == id1:
            return (id2, id1)
        return None

    def _apply_event_impacts(self) -> None:
        """
        Create `event_impact` relationships from stored regulatory events to their related assets.

        For each regulatory event whose `asset_id` and each `related_assets` entry are present in the graph, add a one-way relationship of type `"event_impact"` with strength equal to the absolute value of `event.impact_score`. Events referencing missing source or target assets are skipped.
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

    def _append_relationship(self, source_id: str, target_id: str, rel_type: str, strength: float) -> None:
        """
        Add a relationship from source_id to target_id unless a relationship with the same target and type already exists.

        If the source has no relationships yet, a list is created and the new relationship is appended. The function mutates the graph's internal relationships mapping and does not add duplicate entries where both the target_id and rel_type match an existing relationship.

        Parameters:
            source_id (str): ID of the source asset.
            target_id (str): ID of the target asset.
            rel_type (str): Relationship type label.
            strength (float): Numeric strength of the relationship.
        """
        rels = self.relationships.setdefault(source_id, [])
        if any(t == target_id and rt == rel_type for t, rt, _ in rels):
            return
        rels.append((target_id, rel_type, strength))

    def _collect_participating_asset_ids(self) -> set[str]:
        """
        Collect all asset IDs referenced by the graph, including stored assets and relationship targets.

        Returns:
            ids (set[str]): Set of asset IDs present as keys in `self.assets` or appearing as targets in any relationship.
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
            dict[str, int]: Mapping from each asset_class.value (string) to the number of assets with that class.
        """
        dist: dict[str, int] = {}
        for asset in self.assets.values():
            key = asset.asset_class.value
            dist[key] = dist.get(key, 0) + 1
        return dist

    @staticmethod
    def _relationship_density(asset_count: int, rel_count: int) -> float:
        """
        Compute the relationship density as a percentage of the maximum possible directed edges.

        Parameters:
            asset_count (int): Number of distinct assets in the graph.
            rel_count (int): Number of directed relationships present.

        Returns:
            float: Percentage in the range 0.0–100.0 representing directed edges divided by the maximum possible (asset_count * (asset_count - 1)). Returns 0.0 when asset_count is 1 or less.
        """
        if asset_count <= 1:
            return 0.0
        max_possible = asset_count * (asset_count - 1)
        return (rel_count / max_possible) * 100.0
