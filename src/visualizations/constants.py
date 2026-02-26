"""Shared constants for visualization modules.

This module centralises constants that are used across 3D and 2D graph
visualisation modules so that there is a single source of truth.
"""

from collections import defaultdict

# Default fallback color for unknown relationship types
_REL_TYPE_DEFAULT_COLOR = "#888888"

# Color mapping for relationship types used by both 3D and 2D visualizations.
# Uses defaultdict so that unknown types automatically return the fallback gray
# without a KeyError.  Callers that previously used `.get(rel_type, "#888888")`
# are fully compatible because defaultdict also supports dict[key] access.
REL_TYPE_COLORS = defaultdict(
    lambda: _REL_TYPE_DEFAULT_COLOR,
    {
        "same_sector": "#FF6B6B",  # Red for sector relationships
        "market_cap_similar": "#4ECDC4",  # Teal for market cap
        "correlation": "#45B7D1",  # Blue for correlations
        "corporate_bond_to_equity": "#96CEB4",  # Green for corporate bonds
        "commodity_currency": "#FFEAA7",  # Yellow for commodity-currency
        "income_comparison": "#DDA0DD",  # Plum for income comparisons
        "regulatory_impact": "#FFA07A",  # Light salmon for regulatory
    },
)
