"""Core in-memory asset graph used by API and data workflows."""

from __future__ import annotations

from typing import Any

import numpy as np

from src.logic.relationship_parser import parse_relationship_args
from src.models.financial_models import Asset, Bond, RegulatoryEvent

Relationship = tuple[str, str, float]
TopRelationship = tuple[str, str, str, float]


class AssetRelationshipGraph:
    """Graph of assets, relationships, and regulatory events."""

    def __init__(
        self,
        database_url: str | None = None,
        same_sector_strength: float | None = None,
        corporate_bond_strength: float | None = None,
    ) -> None:
        """
        Initialize the AssetRelationshipGraph with empty internal stores.

        Parameters:
            database_url (str | None): Optional database connection URL to
                persist or load graph data; stored on the instance as
                `database_url`.
            same_sector_strength (float | None): The default connection strength between
                assets in the same sector (must be in range [-1.0, 1.0]). Defaults to settings.
            corporate_bond_strength (float | None): The default connection strength from
                a corporate bond to its issuer (must be in range [-1.0, 1.0]). Defaults to settings.

        Attributes created:
            assets (dict[str, Asset]): Mapping of asset ID to Asset.
            relationships (dict[str, list[Relationship]]): Mapping of source asset
                ID to list of outgoing relationships.
            regulatory_events (list[RegulatoryEvent]): List of regulatory events
                associated with assets.
        """
        self.assets: dict[str, Asset] = {}
        self.relationships: dict[str, list[Relationship]] = {}
        self.regulatory_events: list[RegulatoryEvent] = []
        self.database_url = database_url

        from src.config.settings import get_settings

        settings = get_settings()

        if same_sector_strength is None:
            same_sector_strength = settings.same_sector_strength
        if corporate_bond_strength is None:
            corporate_bond_strength = settings.corporate_bond_strength

        if not -1.0 <= same_sector_strength <= 1.0:
            raise ValueError(f"same_sector_strength must be between -1.0 and 1.0, got {same_sector_strength}")
        if not -1.0 <= corporate_bond_strength <= 1.0:
            raise ValueError(f"corporate_bond_strength must be between -1.0 and 1.0, got {corporate_bond_strength}")

        self.same_sector_strength = same_sector_strength
        self.corporate_bond_strength = corporate_bond_strength

    def add_asset(self, asset: Asset) -> None:
        """
        Add or update an asset in the graph.

        Parameters:
            asset (Asset): Asset to store; placed in the graph keyed by its `id`.
            If an asset with the same `id` already exists it will be replaced.
        """
        self.assets[asset.id] = asset

    def add_regulatory_event(self, event: RegulatoryEvent) -> None:
        """Append a regulatory event to the graph."""
        self.regulatory_events.append(event)

    def build_relationships(self) -> None:
        """
        Rebuild the internal relationships mapping based on asset metrics.

        This clears the existing relationships and repopulates them by:
        - Adding a bidirectional "same_sector" relationship between
          assets that share a meaningful sector.
        - Adding a unidirectional "corporate_link" from a bond to
          its issuer when an issuer relationship exists.
        After pairwise processing, applies regulatory event impacts as
        event-driven relationships.
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
                        self.same_sector_strength,
                        bidirectional=True,
                    )

                issuer_link = self._issuer_link(asset1, asset2, source_id, target_id)
                if issuer_link is not None:
                    bond_id, issuer_id = issuer_link
                    self.add_relationship(
                        bond_id,
                        issuer_id,
                        "corporate_link",
                        self.corporate_bond_strength,
                        bidirectional=False,
                    )

        self._apply_event_impacts()

    def add_relationship(
        self,
        source_id: str,
        target_id: str,
        *relationship_args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Add a directed relationship from source_id to target_id and optionally add the reverse relationship.

        This skips adding a duplicate relationship with the same type between the same source and target.
        Accepts legacy and tuple argument shapes for relationship specification.

        Parameters:
            relationship_args: Either a two-tuple (rel_type, strength) or positional arguments
                rel_type, strength[, bidirectional_flag]. The optional bidirectional flag (positional)
                or keyword `bidirectional` controls whether the reverse relationship is also added.
            kwargs: May include `bidirectional` (bool) when not supplied positionally.
        """
        rel_type, strength, bidirectional = parse_relationship_args(
            relationship_args,
            kwargs,
        )
        self._append_relationship(
            source_id=source_id,
            target_id=target_id,
            rel_type=rel_type,
            strength=strength,
        )
        if bidirectional:
            self._append_relationship(
                source_id=target_id,
                target_id=source_id,
                rel_type=rel_type,
                strength=strength,
            )

    @staticmethod
    def _clamp01(value: float) -> float:
        """Clamp a float to the inclusive range [0.0, 1.0]."""
        return max(0.0, min(1.0, value))

    @staticmethod
    def _saturating_norm(count: int, k: float) -> float:
        """
        Map a non-negative integer count to a saturating value between 0 and 1.

        Parameters:
            count (int): Non-negative count; values <= 0 map to 0.0.
            k (float): Positive saturation constant that controls how quickly
                the value approaches 1.

        Returns:
            float: `0.0` if `count <= 0`, otherwise `count / (count + k)`
                (a value strictly between 0 and 1).
        """
        if count <= 0:
            return 0.0
        return count / (count + k)

    def calculate_metrics(self) -> dict[str, Any]:
        """
        Produce aggregated network metrics, distributions, and a composite quality score for the current asset graph.

        Returns:
            metrics (dict): Mapping of metric names to values with the following keys:
                - total_assets (int): Number of participating assets (present in assets or referenced by relationships).
                - total_relationships (int): Total number of relationships stored.
                - average_relationship_strength (float): Mean strength across all relationships (0.0 if none).
                - network_density (float): Normalized fraction of possible directed links present (0.0–1.0).
                - relationship_distribution (dict[str, int]): Counts of relationships grouped by relationship type.
                - asset_class_distribution (dict[str, int]): Counts of assets grouped by asset class value.
                - asset_classes (dict[str, int]): Public API alias for asset_class_distribution.
                - avg_degree (float): Mean outgoing relationship count for sources in the relationship map.
                  Zero-degree assets (those absent from ``relationships``) are excluded from this average.
                - max_degree (int): Maximum outgoing relationship count for sources in the relationship map.
                  Zero-degree assets (those absent from ``relationships``) are excluded from this maximum.
                - top_relationships (list[tuple[str, str, str, float]]): Up to 10 relationships sorted by strength as (source_id, target_id, rel_type, strength).
                - regulatory_event_count (int): Number of stored regulatory events.
                - regulatory_event_norm (float): Normalized regulatory event count in [0.0, 1.0) using a saturating mapping.
                - quality_score (float): Composite score in [0.0, 1.0] combining normalized average strength and regulatory-event influence.
        """
        effective_assets_count = len(self._collect_participating_asset_ids())
        (
            rel_dist,
            top_relationships,
            total_relationships,
            avg_strength,
        ) = self._summarize_relationships()
        network_density = calculate_graph_density(
            effective_assets_count,
            total_relationships,
        )
        asset_class_dist = self._asset_class_distribution()
        avg_degree, max_degree = self._degree_metrics()
        reg_events = len(self.regulatory_events)
        reg_events_norm, quality_score = self._quality_metrics(avg_strength, reg_events)

        return {
            "total_assets": effective_assets_count,
            "total_relationships": total_relationships,
            "average_relationship_strength": avg_strength,
            "network_density": network_density,
            "relationship_distribution": rel_dist,
            "asset_class_distribution": asset_class_dist,
            "asset_classes": dict(asset_class_dist),
            # avg_degree and max_degree are computed across sources present in
            # `relationships`, not all assets; zero-degree assets are excluded.
            "avg_degree": avg_degree,
            "max_degree": max_degree,
            "top_relationships": top_relationships,
            "regulatory_event_count": reg_events,
            "regulatory_event_norm": reg_events_norm,
            "quality_score": quality_score,
        }

    def _summarize_relationships(
        self,
    ) -> tuple[dict[str, int], list[TopRelationship], int, float]:
        """
        Summarize the graph's stored directed relationships by type, top strengths, total count, and average strength.

        Returns:
            rel_dist (dict[str, int]): Mapping from relationship type to its occurrence count.
            top_relationships (list[TopRelationship]): Up to 10 relationships sorted by descending strength; each is (source_id, target_id, relationship_type, strength).
            total_relationships (int): Total number of directed relationships.
            average_strength (float): Mean strength across all returned relationships, or 0.0 if there are none.
        """
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

        all_rels.sort(key=lambda relationship: relationship[3], reverse=True)
        avg_strength = (strength_sum / strength_count) if strength_count else 0.0
        return rel_dist, all_rels[:10], total_relationships, avg_strength

    def _quality_metrics(self, avg_strength: float, regulatory_event_count: int) -> tuple[float, float]:
        """
        Compute a normalized regulatory-event signal and a composite quality score.

        The returned quality score combines a clamped average relationship strength and a normalized regulatory-event count using fixed weights (strength: 0.7, events: 0.3).

        Returns:
            tuple:
                reg_events_norm (float): Normalized regulatory-event signal (0.0 to <1.0).
                quality_score (float): Composite quality score clamped to the range [0.0, 1.0].
        """
        k = 10.0
        w_strength = 0.7
        w_events = 0.3
        avg_strength_n = self._clamp01(avg_strength)
        reg_events_norm = self._saturating_norm(regulatory_event_count, k)
        quality_score = self._clamp01((w_strength * avg_strength_n) + (w_events * reg_events_norm))
        return reg_events_norm, quality_score

    def get_3d_visualization_data_enhanced(
        self,
    ) -> tuple[
        np.ndarray,
        list[str],
        list[str],
        list[str],
    ]:
        """
        Generate node positions, identifiers, colors, and hover labels for 3D visualization.

        Positions are arranged on a unit circle in the XY plane (z = 0).
        If there are no assets, returns a single placeholder point.

        Returns:
            positions (np.ndarray): Array of shape (N, 3) with XYZ
                coordinates for each node.
            asset_ids (list[str]): Ordered list of asset identifiers
                corresponding to rows in `positions`.
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
        Determine whether two assets belong to the same non-"Unknown" sector.

        Returns:
            `true` if both assets have the same sector value
            and that sector is not "Unknown", `false` otherwise.
        """
        return asset1.sector == asset2.sector and asset1.sector != "Unknown"

    @staticmethod
    def _issuer_link(
        asset1: Asset,
        asset2: Asset,
        id1: str,
        id2: str,
    ) -> tuple[str, str] | None:
        """
        Determine whether one asset is a Bond issued by the other and return the corresponding (bond_id, issuer_id).

        Returns:
            (bond_id, issuer_id) if a Bond's `issuer_id` equals the other asset's id, `None` otherwise.
        """
        if isinstance(asset1, Bond) and asset1.issuer_id == id2:
            return (id1, id2)
        if isinstance(asset2, Bond) and asset2.issuer_id == id1:
            return (id2, id1)
        return None

    def _apply_event_impacts(self) -> None:
        """
        Create relationships from regulatory events to their related assets.

        For each regulatory event, add a non-bidirectional "event_impact" relationship from the event's asset to each related asset with strength equal to the absolute value of the event's impact_score.
        """
        for event in self.regulatory_events:
            source_id = event.asset_id
            for target_id in self._iter_valid_event_targets(
                source_id,
                event.related_assets,
            ):
                self.add_relationship(
                    source_id,
                    target_id,
                    "event_impact",
                    abs(event.impact_score),
                    bidirectional=False,
                )

    def _iter_valid_event_targets(
        self,
        source_id: str,
        related_assets: list[str],
    ) -> list[str]:
        """
        Select related asset IDs that exist in the graph when the source asset is present.

        Parameters:
            source_id (str): ID of the event's source asset; if this asset is not stored in the graph no targets are considered.
            related_assets (list[str]): Candidate target asset IDs to validate against stored assets.

        Returns:
            list[str]: IDs from `related_assets` that are present in the graph; empty if `source_id` is not found.
        """
        if source_id not in self.assets:
            return []
        existing_asset_ids = set(self.assets.keys())
        return [target_id for target_id in related_assets if target_id in existing_asset_ids]

    def _append_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        strength: float,
    ) -> None:
        """
        Append a relationship from source_id to target_id if no relationship with the same target and type already exists.

        This creates the relationship list for source_id if absent and appends a tuple (target_id, rel_type, strength).
        Duplicate detection is based on (target_id, rel_type) only; an existing entry with the same target and type prevents appending even if strength differs.

        Parameters:
            source_id (str): ID of the source asset whose relationship list will be updated.
            target_id (str): ID of the target asset for the relationship.
            rel_type (str): Semantic type of the relationship (e.g., "same_sector", "corporate_link").
            strength (float): Numerical strength of the relationship, typically in [0.0, 1.0].
        """
        rels = self.relationships.setdefault(source_id, [])
        if any(t == target_id and rt == rel_type for t, rt, _ in rels):
            return
        rels.append((target_id, rel_type, strength))

    def _collect_participating_asset_ids(self) -> set[str]:
        """
        Collect the set of asset IDs that participate in the graph.

        Returns:
            set[str]: Unique asset IDs present as stored assets or referenced as
                relationship targets.
        """
        all_ids = set(self.assets.keys())
        all_ids.update(self.relationships.keys())
        for rels in self.relationships.values():
            for target_id, _, _ in rels:
                all_ids.add(target_id)
        return all_ids

    def _asset_class_distribution(self) -> dict[str, int]:
        """
        Build a count distribution of asset_class.value among stored assets.

        Returns:
            dist (dict[str, int]): Mapping from asset_class.value to the number of
                assets with that class.
        """
        dist: dict[str, int] = {}
        for asset in self.assets.values():
            key = asset.asset_class.value
            dist[key] = dist.get(key, 0) + 1
        return dist

    def _degree_metrics(self) -> tuple[float, int]:
        """
        Compute public outgoing-degree metrics from the relationship map.

        Returns:
            tuple[float, int]: Average and maximum outgoing relationship counts
                across sources present in `relationships`.
        """
        degrees = [len(rels) for rels in self.relationships.values()]
        if not degrees:
            return 0.0, 0
        return sum(degrees) / len(degrees), max(degrees)


def calculate_graph_density(asset_count: int, relationship_count: int) -> float:
    """
    Compute graph relationship network_density as a ratio (0.0 to 1.0).

    Formula for directed graph network_density is: E / (V * (V - 1))
    Returns 0.0 if asset_count <= 1.

    Note: For graphs with multiple relationship types between the same node pair,
    the raw ratio may exceed 1.0 and is clamped to preserve the [0, 1] contract.

    Parameters:
        asset_count (int): Number of assets (nodes) in the graph.
        relationship_count (int): Number of relationships (edges) in the graph.

    Returns:
        float: Graph network_density ratio between 0.0 and 1.0.
    """
    if asset_count <= 1:
        return 0.0
    possible_edges = asset_count * (asset_count - 1)
    return min(1.0, float(relationship_count) / possible_edges)
