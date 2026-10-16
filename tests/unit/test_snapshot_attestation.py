"""Deterministic unit tests for snapshot attestation canonicalizer and digest computation."""

from __future__ import annotations

import hashlib
from decimal import Decimal

import pytest

from src.logic.snapshot_attestation import (
    ATTESTATION_VERSION_V1,
    CanonicalizationValidationError,
    canonical_json_dumps,
    canonicalize_asset,
    canonicalize_regulatory_event,
    canonicalize_relationship,
    compute_snapshot_attestation_hash,
    generate_snapshot_canonical_payload,
    normalize_decimal_string,
)
from src.models.financial_models import AssetClass, Equity, RegulatoryActivity, RegulatoryEvent

VECTOR_1_CANONICAL_STR = (
    '{"assets":[],"attestation_version":"v1","contract_version":"grac-v1","regulatory_events":[],"relationships":[]}'
)
VECTOR_1_BYTE_LEN = 111
VECTOR_1_SHA256 = "834b5db2d6df9c98252318714d4088a5f875f83440548fd832840d54dbdf8d99"

VECTOR_2_CANONICAL_STR = (
    '{"assets":['
    '{"asset_class":"Equity","book_value":null,"central_bank_rate":null,"contract_size":null,"country":null,'
    '"coupon_rate":null,"credit_rating":null,"currency":"USD","delivery_date":null,"dividend_yield":"0.005500",'
    '"earnings_per_share":"6.420000","exchange_rate":null,"id":"AAPL","issuer_id":null,'
    '"market_cap":"3000000000000.000000","maturity_date":null,"name":"Apple Inc.","pe_ratio":"28.500000",'
    '"price":"180.500000","sector":"Technology","symbol":"AAPL","volatility":null,"yield_to_maturity":null},'
    '{"asset_class":"Equity","book_value":null,"central_bank_rate":null,"contract_size":null,"country":null,'
    '"coupon_rate":null,"credit_rating":null,"currency":"USD","delivery_date":null,"dividend_yield":"0.007200",'
    '"earnings_per_share":"11.050000","exchange_rate":null,"id":"MSFT","issuer_id":null,'
    '"market_cap":"3100000000000.000000","maturity_date":null,"name":"Microsoft Corporation","pe_ratio":"35.100000",'
    '"price":"420.100000","sector":"Technology","symbol":"MSFT","volatility":null,"yield_to_maturity":null}'
    '],"attestation_version":"v1","contract_version":"grac-v1","regulatory_events":[],'
    '"relationships":[{"bidirectional":true,"relationship_type":"same_sector","source_id":"AAPL","strength":"0.500000","target_id":"MSFT"}]}'
)
VECTOR_2_BYTE_LEN = 1226
VECTOR_2_SHA256 = "c5f111b206be321d66eefd338fa01728e0eb6d407bd1c9b00b31bcf8908f91f0"

VECTOR_3_CANONICAL_STR = (
    '{"assets":['
    '{"asset_class":"Equity","book_value":null,"central_bank_rate":null,"contract_size":null,"country":null,'
    '"coupon_rate":null,"credit_rating":null,"currency":"USD","delivery_date":null,"dividend_yield":"0.005500",'
    '"earnings_per_share":"6.420000","exchange_rate":null,"id":"AAPL","issuer_id":null,'
    '"market_cap":"3000000000000.000000","maturity_date":null,"name":"Apple Inc.","pe_ratio":"28.500000",'
    '"price":"180.500000","sector":"Technology","symbol":"AAPL","volatility":null,"yield_to_maturity":null}'
    '],"attestation_version":"v1","contract_version":"grac-v1",'
    '"regulatory_events":['
    '{"affected_asset_ids":["MSFT"],"asset_id":"AAPL","date":"2026-04-10",'
    '"description":"Annual 10-K filing","event_type":"Regulatory Filing","id":"REG-001","impact_score":"0.100000"}'
    "],"
    '"relationships":[{"bidirectional":false,"relationship_type":"supplier","source_id":"AAPL","strength":"-0.500000","target_id":"MSFT"}]}'
)
VECTOR_3_BYTE_LEN = 897
VECTOR_3_SHA256 = "fb0b7c8c5c70097ee9a64d5ef7bc71a0a5195090cb6282eb9d2660ade241884d"


def test_golden_vector_1_empty_snapshot() -> None:
    """Vector 1 (empty snapshot) produces exact canonical string, byte count, and digest."""
    canon_str, canon_bytes = generate_snapshot_canonical_payload(
        assets=[],
        relationships=[],
        regulatory_events=[],
    )
    assert canon_str == VECTOR_1_CANONICAL_STR
    assert len(canon_bytes) == VECTOR_1_BYTE_LEN
    assert hashlib.sha256(canon_bytes).hexdigest() == VECTOR_1_SHA256
    assert compute_snapshot_attestation_hash(assets=[], relationships=[], regulatory_events=[]) == VECTOR_1_SHA256


def test_golden_vector_2_two_asset_snapshot() -> None:
    """Vector 2 (AAPL + MSFT) produces exact canonical string, byte count, and digest."""
    aapl = Equity(
        id="AAPL",
        symbol="AAPL",
        name="Apple Inc.",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=180.50,
        market_cap=3000000000000.0,
        currency="USD",
        pe_ratio=28.5,
        dividend_yield=0.0055,
        earnings_per_share=6.42,
    )
    msft = Equity(
        id="MSFT",
        symbol="MSFT",
        name="Microsoft Corporation",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=420.10,
        market_cap=3100000000000.0,
        currency="USD",
        pe_ratio=35.1,
        dividend_yield=0.0072,
        earnings_per_share=11.05,
    )
    rel = {
        "source_id": "AAPL",
        "target_id": "MSFT",
        "relationship_type": "same_sector",
        "strength": 0.5,
        "bidirectional": True,
    }

    canon_str, canon_bytes = generate_snapshot_canonical_payload(
        assets=[aapl, msft],
        relationships=[rel],
        regulatory_events=[],
    )
    assert canon_str == VECTOR_2_CANONICAL_STR
    assert len(canon_bytes) == VECTOR_2_BYTE_LEN
    assert hashlib.sha256(canon_bytes).hexdigest() == VECTOR_2_SHA256
    assert (
        compute_snapshot_attestation_hash(assets=[aapl, msft], relationships=[rel], regulatory_events=[])
        == VECTOR_2_SHA256
    )


def test_golden_vector_3_regulatory_event_snapshot() -> None:
    """Vector 3 (Asset + Negative Relationship + Regulatory Event with owner) produces exact digest."""
    aapl = Equity(
        id="AAPL",
        symbol="AAPL",
        name="Apple Inc.",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=180.50,
        market_cap=3000000000000.0,
        currency="USD",
        pe_ratio=28.5,
        dividend_yield=0.0055,
        earnings_per_share=6.42,
    )
    rel = {
        "source_id": "AAPL",
        "target_id": "MSFT",
        "relationship_type": "supplier",
        "strength": -0.5,
        "bidirectional": False,
    }
    event = RegulatoryEvent(
        id="REG-001",
        asset_id="AAPL",
        event_type=RegulatoryActivity.REGULATORY_FILING,
        date="2026-04-10",
        description="Annual 10-K filing",
        impact_score=0.1,
        related_assets=["MSFT"],
    )
    canon_str, canon_bytes = generate_snapshot_canonical_payload(
        assets=[aapl],
        relationships=[rel],
        regulatory_events=[event],
    )
    assert canon_str == VECTOR_3_CANONICAL_STR
    assert len(canon_bytes) == VECTOR_3_BYTE_LEN
    assert hashlib.sha256(canon_bytes).hexdigest() == VECTOR_3_SHA256
    assert (
        compute_snapshot_attestation_hash(assets=[aapl], relationships=[rel], regulatory_events=[event])
        == VECTOR_3_SHA256
    )


def test_collection_ordering_invariance() -> None:
    """Assets and relationships passed in arbitrary order sort deterministically."""
    aapl = Equity(
        id="AAPL",
        symbol="AAPL",
        name="Apple Inc.",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=180.50,
        market_cap=3000000000000.0,
        currency="USD",
        pe_ratio=28.5,
        dividend_yield=0.0055,
        earnings_per_share=6.42,
    )
    msft = Equity(
        id="MSFT",
        symbol="MSFT",
        name="Microsoft Corporation",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=420.10,
        market_cap=3100000000000.0,
        currency="USD",
        pe_ratio=35.1,
        dividend_yield=0.0072,
        earnings_per_share=11.05,
    )
    rel1 = {"source_id": "AAPL", "target_id": "MSFT", "relationship_type": "same_sector", "strength": 0.5}
    rel2 = {"source_id": "AAPL", "target_id": "MSFT", "relationship_type": "supplier", "strength": 0.8}

    # Pass MSFT before AAPL, rel2 before rel1
    hash_rev = compute_snapshot_attestation_hash(
        assets=[msft, aapl],
        relationships=[rel2, rel1],
        regulatory_events=[],
    )
    # Pass AAPL before MSFT, rel1 before rel2
    hash_fwd = compute_snapshot_attestation_hash(
        assets=[aapl, msft],
        relationships=[rel1, rel2],
        regulatory_events=[],
    )
    assert hash_rev == hash_fwd


def test_field_modifications_change_digest() -> None:
    """Modifying any field (price, market cap, strength, event description) changes the digest."""
    base_aapl = Equity(
        id="AAPL",
        symbol="AAPL",
        name="Apple Inc.",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=180.50,
        market_cap=3000000000000.0,
    )
    base_rel = {"source_id": "AAPL", "target_id": "MSFT", "relationship_type": "same_sector", "strength": 0.5}
    base_hash = compute_snapshot_attestation_hash(assets=[base_aapl], relationships=[base_rel], regulatory_events=[])

    # Price change
    p_changed = Equity(
        id="AAPL",
        symbol="AAPL",
        name="Apple Inc.",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=180.51,
        market_cap=3000000000000.0,
    )
    assert (
        compute_snapshot_attestation_hash(assets=[p_changed], relationships=[base_rel], regulatory_events=[])
        != base_hash
    )

    # Market cap change
    mc_changed = Equity(
        id="AAPL",
        symbol="AAPL",
        name="Apple Inc.",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=180.50,
        market_cap=3000000000001.0,
    )
    assert (
        compute_snapshot_attestation_hash(assets=[mc_changed], relationships=[base_rel], regulatory_events=[])
        != base_hash
    )

    # Strength change
    s_changed = {"source_id": "AAPL", "target_id": "MSFT", "relationship_type": "same_sector", "strength": 0.500001}
    assert (
        compute_snapshot_attestation_hash(assets=[base_aapl], relationships=[s_changed], regulatory_events=[])
        != base_hash
    )

    # Event change
    ev = RegulatoryEvent(
        id="EVT1",
        asset_id="AAPL",
        event_type=RegulatoryActivity.EARNINGS_REPORT,
        date="2024-01-15T00:00:00Z",
        description="Original",
        impact_score=0.2,
    )
    ev_mod = RegulatoryEvent(
        id="EVT1",
        asset_id="AAPL",
        event_type=RegulatoryActivity.EARNINGS_REPORT,
        date="2024-01-15T00:00:00Z",
        description="Modified",
        impact_score=0.2,
    )
    hash_ev = compute_snapshot_attestation_hash(assets=[base_aapl], relationships=[], regulatory_events=[ev])
    hash_ev_mod = compute_snapshot_attestation_hash(assets=[base_aapl], relationships=[], regulatory_events=[ev_mod])
    assert hash_ev != hash_ev_mod

    # Event owner change
    ev_owner = RegulatoryEvent(
        id="EVT1",
        asset_id="MSFT",
        event_type=RegulatoryActivity.EARNINGS_REPORT,
        date="2024-01-15T00:00:00Z",
        description="Original",
        impact_score=0.2,
    )
    hash_ev_owner = compute_snapshot_attestation_hash(
        assets=[base_aapl], relationships=[], regulatory_events=[ev_owner]
    )
    assert hash_ev != hash_ev_owner


def test_decimal_precision_and_rounding() -> None:
    """Banker's rounding (ROUND_HALF_EVEN) and strict 6-decimal quantization."""
    # 2.5555555 rounds to 2.555556
    assert normalize_decimal_string(2.5555556) == "2.555556"
    assert normalize_decimal_string("180.5") == "180.500000"
    assert normalize_decimal_string(Decimal("100")) == "100.000000"
    assert normalize_decimal_string(None, allow_none=True) is None

    # Disallow None when allow_none is False
    with pytest.raises(CanonicalizationValidationError, match="cannot be None"):
        normalize_decimal_string(None, allow_none=False)


def test_invalid_values_rejection() -> None:
    """Non-finite values, out-of-range strengths, and empty identifiers are rejected."""
    # NaN
    with pytest.raises(CanonicalizationValidationError, match="Non-finite numeric value"):
        normalize_decimal_string(float("nan"))

    # Infinity
    with pytest.raises(CanonicalizationValidationError, match="Non-finite numeric value"):
        normalize_decimal_string(float("inf"))
    with pytest.raises(CanonicalizationValidationError, match="Non-finite numeric value"):
        normalize_decimal_string(float("-inf"))

    # Invalid strength range (must be [-1.0, 1.0])
    with pytest.raises(CanonicalizationValidationError, match="strength must be between -1.0 and 1.0"):
        canonicalize_relationship({"source_id": "A", "target_id": "B", "relationship_type": "T", "strength": 1.01})
    with pytest.raises(CanonicalizationValidationError, match="strength must be between -1.0 and 1.0"):
        canonicalize_relationship({"source_id": "A", "target_id": "B", "relationship_type": "T", "strength": -1.01})
    with pytest.raises(CanonicalizationValidationError, match="Non-finite numeric value"):
        canonicalize_relationship(
            {"source_id": "A", "target_id": "B", "relationship_type": "T", "strength": float("nan")}
        )
    with pytest.raises(CanonicalizationValidationError, match="Non-finite numeric value"):
        canonicalize_relationship(
            {"source_id": "A", "target_id": "B", "relationship_type": "T", "strength": float("inf")}
        )

    # Empty string identifier
    with pytest.raises(CanonicalizationValidationError, match="cannot be empty"):
        canonicalize_asset(
            {"id": "  ", "symbol": "AAPL", "name": "Apple", "asset_class": "Equity", "sector": "Tech", "price": 100}
        )


def test_relationship_strength_range_inclusive_bounds() -> None:
    """Accept finite relationship strengths across the inclusive interval [-1.0, 1.0]."""
    for val in [-1.0, -0.75, -0.000001, 0.0, 0.000001, 0.75, 1.0]:
        canon = canonicalize_relationship(
            {"source_id": "A", "target_id": "B", "relationship_type": "T", "strength": val}
        )
        assert Decimal(canon["strength"]) == Decimal(str(val)).quantize(Decimal("0.000001"))


def test_regulatory_event_ownership_validation() -> None:
    """Event ownership must be non-empty string and missing/ambiguous owners are rejected."""
    # Missing asset_id
    with pytest.raises(CanonicalizationValidationError, match="Field 'asset_id' cannot be None"):
        canonicalize_regulatory_event(
            {
                "id": "EVT1",
                "event_type": "earnings_report",
                "date": "2024-01-15",
                "description": "Test",
                "impact_score": 0.2,
            }
        )

    # Empty string asset_id
    with pytest.raises(CanonicalizationValidationError, match="Field 'asset_id' cannot be empty"):
        canonicalize_regulatory_event(
            {
                "id": "EVT1",
                "asset_id": "   ",
                "event_type": "earnings_report",
                "date": "2024-01-15",
                "description": "Test",
                "impact_score": 0.2,
            }
        )


def test_duplicate_identities_rejection() -> None:
    """Duplicate asset IDs, relationship edges, or event IDs raise validation errors."""
    aapl1 = Equity(id="AAPL", symbol="AAPL", name="Apple 1", asset_class=AssetClass.EQUITY, sector="Tech", price=100)
    aapl2 = Equity(id="AAPL", symbol="AAPL", name="Apple 2", asset_class=AssetClass.EQUITY, sector="Tech", price=100)

    with pytest.raises(CanonicalizationValidationError, match="Duplicate asset id"):
        generate_snapshot_canonical_payload(assets=[aapl1, aapl2], relationships=[], regulatory_events=[])

    rel1 = {"source_id": "A", "target_id": "B", "relationship_type": "T", "strength": 0.5}
    rel2 = {"source_id": "A", "target_id": "B", "relationship_type": "T", "strength": 0.8}
    with pytest.raises(CanonicalizationValidationError, match="Duplicate relationship edge"):
        generate_snapshot_canonical_payload(assets=[aapl1], relationships=[rel1, rel2], regulatory_events=[])

    ev1 = RegulatoryEvent(
        id="E1",
        asset_id="AAPL",
        event_type=RegulatoryActivity.ACQUISITION,
        date="2024-01-01",
        description="d1",
        impact_score=0.1,
    )
    ev2 = RegulatoryEvent(
        id="E1",
        asset_id="AAPL",
        event_type=RegulatoryActivity.ACQUISITION,
        date="2024-01-01",
        description="d2",
        impact_score=0.1,
    )
    with pytest.raises(CanonicalizationValidationError, match="Duplicate regulatory event id"):
        generate_snapshot_canonical_payload(assets=[aapl1], relationships=[], regulatory_events=[ev1, ev2])


def test_unsupported_versions_rejection() -> None:
    """Unsupported attestation or contract versions fail closed."""
    aapl = Equity(id="AAPL", symbol="AAPL", name="Apple", asset_class=AssetClass.EQUITY, sector="Tech", price=100)

    with pytest.raises(CanonicalizationValidationError, match="Unsupported attestation_version"):
        generate_snapshot_canonical_payload(
            assets=[aapl],
            relationships=[],
            regulatory_events=[],
            attestation_version="v2",
        )

    with pytest.raises(CanonicalizationValidationError, match="Unsupported contract_version"):
        generate_snapshot_canonical_payload(
            assets=[aapl],
            relationships=[],
            regulatory_events=[],
            contract_version="grac-v2",
        )


def test_explicit_null_serialization() -> None:
    """Optional attributes format as :null rather than omitted."""
    aapl = Equity(
        id="AAPL",
        symbol="AAPL",
        name="Apple Inc.",
        asset_class=AssetClass.EQUITY,
        sector="Technology",
        price=180.50,
        market_cap=None,
    )
    canon = canonicalize_asset(aapl)
    assert "market_cap" in canon
    assert canon["market_cap"] is None
    canon_str, _ = canonical_json_dumps(canon)
    assert '"market_cap":null' in canon_str
