from collections import defaultdict

# Color mapping for relationship types; unknown types fall back to gray.
REL_TYPE_COLORS = defaultdict(
    lambda: "#888888",
    {
        "same_sector": "#FF6B6B",
        "market_cap_similar": "#4ECDC4",
        "correlation": "#45B7D1",
        "corporate_bond_to_equity": "#96CEB4",
        "commodity_currency": "#FFEAA7",
        "income_comparison": "#DDA0DD",
        "regulatory_impact": "#FFA07A",
    },
)
