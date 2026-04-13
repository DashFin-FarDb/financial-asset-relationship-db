"""Core in-memory asset graph used by API and data workflows."""

from __future__ import annotations

from typing import Any

import numpy as np

from src.models.financial_models import Asset, Bond, RegulatoryEvent

Relationship = tuple[str, str, float]
TopRelationship = tuple[str, str, str, float]


class AssetRelationshipGraph:
    """Graph of assets, relationships, and regulatory events."""

    def __init__(self, database_url: str | None = None) -> None:
        """
        Initialize the AssetRelationshipGraph with empty internal stores and an
        optional database URL.

        Parameters:
            database_url (str | None): Optional database connection URL to
                persist or load graph data; stored on the instance as
                `database_url`.

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
        Rebuild the internal relationships mapping based on sector membership,
        issuer links, and regulatory events.

        This clears the existing relationships and repopulates them by:
        - Adding a bidirectional "same_sector" relationship (strength 0.7) between
          assets that share a meaningful sector.
        - Adding a unidirectional "corporate_link" (strength 0.9) from a bond to
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
        rel_type, strength, bidirectional = self._parse_relationship_args(
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
    def _parse_relationship_args(
        relationship_args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> tuple[str, float, bool]:
        """
        Parse flexible add_relationship arguments into a normalized (rel_type, strength, bidirectional) tuple.

        Parameters:
            relationship_args (tuple[Any, ...]): Positional arguments passed to add_relationship; supports either a single tuple of (rel_type, strength) or two/three positional values (rel_type, strength[, bidirectional]).
            kwargs (dict[str, Any]): Keyword arguments passed to add_relationship; may include `bidirectional` and must not contain unknown keys.

        Returns:
            tuple[str, float, bool]: A triple where `rel_type` is the relationship type as a string, `strength` is the relationship strength as a float, and `bidirectional` is a bool indicating whether the relationship should be added in both directions.
        """
        (
            rel_type,
            strength,
            bidirectional,
        ) = AssetRelationshipGraph._dispatch_relationship_parser(
            relationship_args,
            kwargs,
        )
        AssetRelationshipGraph._ensure_no_unknown_kwargs(kwargs)
        return AssetRelationshipGraph._finalize_relationship_args(
            rel_type,
            strength,
            bidirectional,
        )

    @staticmethod
    def _dispatch_relationship_parser(
        relationship_args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> tuple[Any, Any, bool]:
        """
        Choose and run the parser corresponding to the provided relationship argument shape.

        Parameters:
            relationship_args (tuple[Any, ...]): Positional arguments forwarded from add_relationship; expected shapes are either a single tuple of (rel_type, strength) or two/three positional values (rel_type, strength[, bidirectional]).
            kwargs (dict[str, Any]): Keyword arguments forwarded from add_relationship; may contain `bidirectional` for the two-argument form or be inspected/consumed by tuple form parsers.

        Returns:
            tuple[Any, Any, bool]: A tuple (rel_type, strength, bidirectional) where `rel_type` is the relationship type, `strength` is the relationship strength, and `bidirectional` indicates whether the relationship should be added in both directions.

        Raises:
            TypeError: If `relationship_args` does not match any supported shape.
        """
        args_count = len(relationship_args)
        if args_count == 1:
            return AssetRelationshipGraph._parse_single_relationship_arg(
                relationship_args[0],
                kwargs,
            )
        if args_count in {2, 3}:
            return AssetRelationshipGraph._parse_positional_relationship(
                relationship_args,
                kwargs,
            )
        raise TypeError(
            "add_relationship expects (rel_type, strength[, bidirectional]) or ((rel_type, strength), [bidirectional])."
        )

    @staticmethod
    def _parse_single_relationship_arg(
        relationship_arg: Any,
        kwargs: dict[str, Any],
    ) -> tuple[Any, Any, bool]:
        """
        Parse a single positional relationship argument expressed as a (rel_type, strength) tuple.

        Parameters:
            relationship_arg (Any): Expected to be a 2-tuple containing (rel_type, strength).
            kwargs (dict[str, Any]): Keyword arguments that may include optional flags (e.g., "bidirectional").

        Returns:
            tuple[Any, Any, bool]: A tuple of (rel_type, strength, bidirectional).

        Raises:
            TypeError: If `relationship_arg` is not a tuple.
        """
        if not isinstance(relationship_arg, tuple):
            raise TypeError("Single relationship argument must be a tuple of (rel_type, strength).")
        return AssetRelationshipGraph._parse_tuple_relationship(relationship_arg, kwargs)

    @staticmethod
    def _ensure_no_unknown_kwargs(kwargs: dict[str, Any]) -> None:
        """
        Validate that no unexpected keyword arguments remain after parsing.

        Parameters:
            kwargs (dict[str, Any]): Remaining keyword arguments to check.

        Raises:
            TypeError: If `kwargs` is not empty; the exception message lists the unexpected keys.
        """
        if kwargs:
            unknown = ", ".join(sorted(kwargs.keys()))
            raise TypeError(f"Unexpected keyword arguments: {unknown}")

    @staticmethod
    def _finalize_relationship_args(
        rel_type: Any,
        strength: Any,
        bidirectional: bool,
    ) -> tuple[str, float, bool]:
        """
        Validate and coerce relationship arguments into their final types.

        Parameters:
            rel_type (Any): Relationship type; must be a string and will be returned as `str`.
            strength (Any): Numeric strength value; will be coerced to `float`.
            bidirectional (bool): Bidirectionality flag; will be coerced to `bool`.

        Returns:
            tuple[str, float, bool]: A tuple (rel_type, strength, bidirectional) with types (str, float, bool).

        Raises:
            TypeError: If `rel_type` is not a `str`.
        """
        if not isinstance(rel_type, str):
            raise TypeError("rel_type must be a string.")
        return rel_type, float(strength), bool(bidirectional)

    @staticmethod
    def _parse_tuple_relationship(
        relationship_tuple: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> tuple[Any, Any, bool]:
        """
        Parse a two-element relationship tuple into (rel_type, strength) and an explicit bidirectional flag.

        Parameters:
            relationship_tuple (tuple[Any, ...]): A 2-tuple of (rel_type, strength).
            kwargs (dict[str, Any]): May contain a 'bidirectional' key; its value will be used and removed from this dict.

        Returns:
            tuple[Any, Any, bool]: A tuple of (rel_type, strength, bidirectional).

        Raises:
            ValueError: If `relationship_tuple` does not contain exactly two elements.
        """
        if len(relationship_tuple) != 2:
            raise ValueError("Relationship tuple must contain (rel_type, strength).")
        rel_type, strength = relationship_tuple
        bidirectional = bool(kwargs.pop("bidirectional", False))
        return rel_type, strength, bidirectional

    @staticmethod
    def _parse_positional_relationship(
        relationship_args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> tuple[Any, Any, bool]:
        """
        Parse legacy positional relationship arguments and return (rel_type, strength, bidirectional).

        Accepts either a 2- or 3-element positional form:
        - If three positional elements are provided, the third element is used as the bidirectional flag.
        - If two positional elements are provided, the `bidirectional` value is taken from `kwargs.pop("bidirectional", False)`.

        Raises:
            TypeError: If `bidirectional` is supplied both positionally (third positional element) and via `kwargs`.

        Returns:
            tuple: `(rel_type, strength, bidirectional)` where `rel_type` is the relationship type, `strength` is the relationship strength, and `bidirectional` is `True` if the relationship should be added bidirectionally, `False` otherwise.
        """
        rel_type, strength = relationship_args[0], relationship_args[1]
        if len(relationship_args) == 3:
            if "bidirectional" in kwargs:
                raise TypeError("bidirectional specified both positionally and by keyword.")
            return rel_type, strength, bool(relationship_args[2])
        bidirectional_flag = kwargs.pop("bidirectional", False)
        return rel_type, strength, bool(bidirectional_flag)

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
                - relationship_density (float): Percentage of possible directed links present (0.0–100.0).
                - relationship_distribution (dict[str, int]): Counts of relationships grouped by relationship type.
                - asset_class_distribution (dict[str, int]): Counts of assets grouped by asset class value.
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
        density = self._relationship_density(
            effective_assets_count,
            total_relationships,
        )
        asset_class_dist = self._asset_class_distribution()
        reg_events = len(self.regulatory_events)
        reg_events_norm, quality_score = self._quality_metrics(avg_strength, reg_events)

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

    def _summarize_relationships(
        self,
    ) -> tuple[dict[str, int], list[TopRelationship], int, float]:
        """
        Produce relationship-type counts, the top relationships by strength, the total relationship count, and the average relationship strength.

        Returns:
            rel_dist (dict[str, int]): Mapping from relationship type to its occurrence count.
            top_relationships (list[TopRelationship]): Up to 10 relationships sorted by strength descending; each item is (source_id, target_id, relationship_type, strength).
            total_relationships (int): Total number of relationships processed.
            average_strength (float): Mean strength across all relationships, or 0.0 if no relationships exist.
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
        Generate node positions, identifiers, colors, and hover
        labels for 3D visualization.

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
        Identify a bond-to-issuer relationship between two assets.

        Returns:
            (bond_id, issuer_id) if one asset is a Bond whose issuer_id matches the other asset's id, `None` otherwise.
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
        Selects related asset IDs that exist in the graph when the source asset is present.

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
        Builds a count distribution of asset_class.value among stored assets.

        Returns:
            dist (dict[str, int]): Mapping from asset_class.value to the number of
                assets with that class.
        """
        dist: dict[str, int] = {}
        for asset in self.assets.values():
            key = asset.asset_class.value
            dist[key] = dist.get(key, 0) + 1
        return dist

    @staticmethod
    def _relationship_density(asset_count: int, rel_count: int) -> float:
        """
        Compute relationship density as the percentage of possible directed
        edges among assets.

        Parameters:
            asset_count (int): Number of assets in the graph.
            rel_count (int): Count of directed relationships present.

        Returns:
            float: Percentage of possible directed edges that are present
                   (0.0–100.0). Returns 0.0 when `asset_count` is less than or
                   equal to 1.
        """
        if asset_count <= 1:
            return 0.0
        max_possible = asset_count * (asset_count - 1)
        return (rel_count / max_possible) * 100.0
