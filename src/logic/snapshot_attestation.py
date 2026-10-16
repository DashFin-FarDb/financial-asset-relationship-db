"""Snapshot Attestation: Deterministic Canonicalization and Digest Verification.

This module implements the pure, versioned canonicalization and SHA-256 attestation
primitives defined in FARDB's persisted-graph provenance gate specification.
It complies strictly with RFC 8785 (JSON Canonicalization Scheme - JCS).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from enum import Enum
from typing import Any, Final

ATTESTATION_VERSION_V1: Final[str] = "v1"
CONTRACT_VERSION_GRAC_V1: Final[str] = "grac-v1"
CANONICAL_DECIMAL_PLACES: Final[Decimal] = Decimal("0.000001")


class CanonicalizationValidationError(ValueError):
    """Raised when domain entities or values violate canonical snapshot invariants."""


def normalize_decimal_string(
    value: float | int | Decimal | str | None,
    *,
    field_name: str = "number",
    allow_none: bool = True,
) -> str | None:
    """Normalize a numeric value to a strict 6-decimal string representation.

    Parameters:
        value: Numeric value (float, int, Decimal, str) or None.
        field_name: Name of the field for error diagnostics.
        allow_none: Whether None is permitted as a valid input.

    Returns:
        Exact string representation quantized to 6 decimal places (e.g. '180.500000'),
        or None if value is None and allow_none is True.

    Raises:
        CanonicalizationValidationError: If value is non-finite, invalid, or unexpectedly None.
    """
    if value is None:
        if allow_none:
            return None
        raise CanonicalizationValidationError(f"Field '{field_name}' cannot be None")

    if isinstance(value, str) and not value.strip():
        raise CanonicalizationValidationError(f"Field '{field_name}' cannot be an empty string")

    try:
        dec = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise CanonicalizationValidationError(f"Invalid decimal value for '{field_name}': {value!r}") from exc

    if dec.is_nan() or dec.is_infinite():
        raise CanonicalizationValidationError(f"Non-finite numeric value rejected for '{field_name}': {value!r}")

    quantized = dec.quantize(CANONICAL_DECIMAL_PLACES, rounding=ROUND_HALF_EVEN)
    return f"{quantized:.6f}"


def _normalize_string(
    value: Any,
    field_name: str,
    *,
    allow_none: bool = False,
) -> str | None:
    """Validate and normalize a string field."""
    if value is None:
        if allow_none:
            return None
        raise CanonicalizationValidationError(f"Field '{field_name}' cannot be None")
    if not isinstance(value, str):
        raise CanonicalizationValidationError(f"Field '{field_name}' must be a string, got {type(value).__name__}")
    stripped = value.strip()
    if not stripped and not allow_none:
        raise CanonicalizationValidationError(f"Field '{field_name}' cannot be empty")
    return stripped if stripped or not allow_none else None


def _extract_attr_or_key(obj: Any, key: str, default: Any = None) -> Any:
    """Extract an attribute from an object or dictionary."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def canonicalize_asset(asset: Any) -> dict[str, Any]:
    """Canonicalize a single Asset entity into a deterministic 23-property dictionary.

    Parameters:
        asset: Domain Asset instance, ORM model, or dictionary.

    Returns:
        Canonicalized dictionary with exactly 23 sorted keys.

    Raises:
        CanonicalizationValidationError: If any required attribute is missing or invalid.
    """
    asset_id = _normalize_string(_extract_attr_or_key(asset, "id"), "id")
    symbol = _normalize_string(_extract_attr_or_key(asset, "symbol"), "symbol")
    name = _normalize_string(_extract_attr_or_key(asset, "name"), "name")

    raw_asset_class = _extract_attr_or_key(asset, "asset_class")
    if isinstance(raw_asset_class, Enum):
        asset_class_str = raw_asset_class.value
    else:
        asset_class_str = _normalize_string(raw_asset_class, "asset_class")

    sector = _normalize_string(_extract_attr_or_key(asset, "sector"), "sector")
    currency = _normalize_string(_extract_attr_or_key(asset, "currency", "USD"), "currency")

    price_str = normalize_decimal_string(
        _extract_attr_or_key(asset, "price"),
        field_name="price",
        allow_none=False,
    )
    market_cap_str = normalize_decimal_string(
        _extract_attr_or_key(asset, "market_cap"),
        field_name="market_cap",
        allow_none=True,
    )

    pe_ratio_str = normalize_decimal_string(
        _extract_attr_or_key(asset, "pe_ratio"),
        field_name="pe_ratio",
        allow_none=True,
    )
    dividend_yield_str = normalize_decimal_string(
        _extract_attr_or_key(asset, "dividend_yield"),
        field_name="dividend_yield",
        allow_none=True,
    )
    earnings_per_share_str = normalize_decimal_string(
        _extract_attr_or_key(asset, "earnings_per_share"),
        field_name="earnings_per_share",
        allow_none=True,
    )
    book_value_str = normalize_decimal_string(
        _extract_attr_or_key(asset, "book_value"),
        field_name="book_value",
        allow_none=True,
    )

    yield_to_maturity_str = normalize_decimal_string(
        _extract_attr_or_key(asset, "yield_to_maturity"),
        field_name="yield_to_maturity",
        allow_none=True,
    )
    coupon_rate_str = normalize_decimal_string(
        _extract_attr_or_key(asset, "coupon_rate"),
        field_name="coupon_rate",
        allow_none=True,
    )
    maturity_date = _normalize_string(_extract_attr_or_key(asset, "maturity_date"), "maturity_date", allow_none=True)
    credit_rating = _normalize_string(_extract_attr_or_key(asset, "credit_rating"), "credit_rating", allow_none=True)
    issuer_id = _normalize_string(_extract_attr_or_key(asset, "issuer_id"), "issuer_id", allow_none=True)

    contract_size_val = _extract_attr_or_key(asset, "contract_size")
    if contract_size_val is not None and not isinstance(contract_size_val, (int, float, Decimal)):
        raise CanonicalizationValidationError(f"Invalid contract_size: {contract_size_val!r}")
    contract_size = int(contract_size_val) if contract_size_val is not None else None

    delivery_date = _normalize_string(_extract_attr_or_key(asset, "delivery_date"), "delivery_date", allow_none=True)
    volatility_str = normalize_decimal_string(
        _extract_attr_or_key(asset, "volatility"),
        field_name="volatility",
        allow_none=True,
    )

    exchange_rate_str = normalize_decimal_string(
        _extract_attr_or_key(asset, "exchange_rate"),
        field_name="exchange_rate",
        allow_none=True,
    )
    country = _normalize_string(_extract_attr_or_key(asset, "country"), "country", allow_none=True)
    central_bank_rate_str = normalize_decimal_string(
        _extract_attr_or_key(asset, "central_bank_rate"),
        field_name="central_bank_rate",
        allow_none=True,
    )

    return {
        "asset_class": asset_class_str,
        "book_value": book_value_str,
        "central_bank_rate": central_bank_rate_str,
        "contract_size": contract_size,
        "country": country,
        "coupon_rate": coupon_rate_str,
        "credit_rating": credit_rating,
        "currency": currency,
        "delivery_date": delivery_date,
        "dividend_yield": dividend_yield_str,
        "earnings_per_share": earnings_per_share_str,
        "exchange_rate": exchange_rate_str,
        "id": asset_id,
        "issuer_id": issuer_id,
        "market_cap": market_cap_str,
        "maturity_date": maturity_date,
        "name": name,
        "pe_ratio": pe_ratio_str,
        "price": price_str,
        "sector": sector,
        "symbol": symbol,
        "volatility": volatility_str,
        "yield_to_maturity": yield_to_maturity_str,
    }


def canonicalize_relationship(relationship: Any, *, source_id: str | None = None) -> dict[str, Any]:
    """Canonicalize a single relationship edge into a deterministic 5-property dictionary.

    Parameters:
        relationship: Edge tuple, dict, or ORM model.
        source_id: Optional source asset ID when relationship is passed as a (target, type, strength) tuple.

    Returns:
        Canonicalized dictionary with keys: bidirectional, relationship_type, source_id, strength, target_id.
    """
    if isinstance(relationship, tuple):
        if len(relationship) == 4:
            src, tgt, rel_type, strength = relationship
            bidirectional = True
        elif len(relationship) == 3:
            if source_id is None:
                raise CanonicalizationValidationError("source_id required for 3-tuple relationship")
            src = source_id
            tgt, rel_type, strength = relationship
            bidirectional = False
        elif len(relationship) == 5:
            src, tgt, rel_type, strength, bidirectional = relationship
        else:
            raise CanonicalizationValidationError(f"Invalid relationship tuple length: {len(relationship)}")
    else:
        src = _extract_attr_or_key(relationship, "source_id") or _extract_attr_or_key(relationship, "source_asset_id")
        tgt = _extract_attr_or_key(relationship, "target_id") or _extract_attr_or_key(relationship, "target_asset_id")
        rel_type = _extract_attr_or_key(relationship, "relationship_type")
        strength = _extract_attr_or_key(relationship, "strength")
        bidirectional = bool(_extract_attr_or_key(relationship, "bidirectional", False))

    source_clean = _normalize_string(src, "source_id")
    target_clean = _normalize_string(tgt, "target_id")
    rel_type_clean = _normalize_string(rel_type, "relationship_type")

    try:
        dec_strength = Decimal(str(strength))
    except (InvalidOperation, TypeError) as exc:
        raise CanonicalizationValidationError(f"Invalid strength value: {strength!r}") from exc

    if not Decimal("0.0") <= dec_strength <= Decimal("1.0"):
        raise CanonicalizationValidationError(f"Relationship strength must be between 0.0 and 1.0, got {strength}")

    strength_clean = normalize_decimal_string(dec_strength, field_name="strength", allow_none=False)

    return {
        "bidirectional": bool(bidirectional),
        "relationship_type": rel_type_clean,
        "source_id": source_clean,
        "strength": strength_clean,
        "target_id": target_clean,
    }


def canonicalize_regulatory_event(event: Any) -> dict[str, Any]:
    """Canonicalize a single regulatory event into a deterministic dictionary."""
    event_id = _normalize_string(_extract_attr_or_key(event, "id"), "id")
    description = _normalize_string(_extract_attr_or_key(event, "description"), "description")
    date_val = _normalize_string(_extract_attr_or_key(event, "date"), "date")

    raw_event_type = _extract_attr_or_key(event, "event_type")
    if isinstance(raw_event_type, Enum):
        event_type_str = raw_event_type.value
    else:
        event_type_str = _normalize_string(raw_event_type, "event_type")

    impact_score_val = _extract_attr_or_key(event, "impact_score")
    try:
        dec_impact = Decimal(str(impact_score_val))
    except (InvalidOperation, TypeError) as exc:
        raise CanonicalizationValidationError(f"Invalid impact_score value: {impact_score_val!r}") from exc

    if not Decimal("-1.0") <= dec_impact <= Decimal("1.0"):
        raise CanonicalizationValidationError(f"Impact score must be between -1.0 and 1.0, got {impact_score_val}")

    impact_score_str = normalize_decimal_string(dec_impact, field_name="impact_score", allow_none=False)

    title_val = _extract_attr_or_key(event, "title")
    title = _normalize_string(title_val, "title", allow_none=True)

    raw_affected = (
        _extract_attr_or_key(event, "affected_asset_ids") or _extract_attr_or_key(event, "related_assets") or []
    )
    affected_asset_ids: list[str] = []
    for item in raw_affected:
        if isinstance(item, str):
            clean_item = _normalize_string(item, "affected_asset_id")
            if clean_item is not None:
                affected_asset_ids.append(clean_item)
        elif hasattr(item, "asset_id"):
            clean_item = _normalize_string(getattr(item, "asset_id"), "affected_asset_id")
            if clean_item is not None:
                affected_asset_ids.append(clean_item)
    affected_asset_ids.sort()

    res: dict[str, Any] = {
        "affected_asset_ids": affected_asset_ids,
        "date": date_val,
        "description": description,
        "event_type": event_type_str,
        "id": event_id,
        "impact_score": impact_score_str,
    }
    if title is not None:
        res["title"] = title
    return res


def canonical_json_dumps(payload: Any) -> tuple[str, bytes]:
    """Serialize a payload to RFC 8785 canonical JSON string and UTF-8 bytes.

    Parameters:
        payload: Python dictionary or list structured for canonical serialization.

    Returns:
        tuple[str, bytes]: Canonical JSON string and exact UTF-8 encoded bytes.
    """
    canonical_str = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return canonical_str, canonical_str.encode("utf-8")


def generate_snapshot_canonical_payload(
    *,
    assets: Iterable[Any],
    relationships: Iterable[Any],
    regulatory_events: Iterable[Any],
    attestation_version: str = ATTESTATION_VERSION_V1,
    contract_version: str = CONTRACT_VERSION_GRAC_V1,
) -> tuple[str, bytes]:
    """Produce the canonical JSON string and bytes for a complete graph snapshot.

    Raises:
        CanonicalizationValidationError: On duplicate IDs, unsupported versions, or invalid values.
    """
    if attestation_version != ATTESTATION_VERSION_V1:
        raise CanonicalizationValidationError(f"Unsupported attestation_version: {attestation_version!r}")
    if contract_version != CONTRACT_VERSION_GRAC_V1:
        raise CanonicalizationValidationError(f"Unsupported contract_version: {contract_version!r}")

    # Canonicalize and sort assets by id; detect duplicates
    canonical_assets: list[dict[str, Any]] = []
    seen_asset_ids: set[str] = set()
    for raw_asset in assets:
        canonical_item = canonicalize_asset(raw_asset)
        asset_id = canonical_item["id"]
        if asset_id in seen_asset_ids:
            raise CanonicalizationValidationError(f"Duplicate asset id in snapshot: {asset_id}")
        seen_asset_ids.add(asset_id)
        canonical_assets.append(canonical_item)
    canonical_assets.sort(key=lambda a: a["id"])

    # Canonicalize and sort relationships; detect duplicates
    canonical_rels: list[dict[str, Any]] = []
    seen_rel_keys: set[tuple[str, str, str]] = set()
    for raw_rel in relationships:
        canonical_rel = canonicalize_relationship(raw_rel)
        rel_key = (canonical_rel["source_id"], canonical_rel["target_id"], canonical_rel["relationship_type"])
        if rel_key in seen_rel_keys:
            raise CanonicalizationValidationError(f"Duplicate relationship edge in snapshot: {rel_key}")
        seen_rel_keys.add(rel_key)
        canonical_rels.append(canonical_rel)
    canonical_rels.sort(key=lambda r: (r["source_id"], r["target_id"], r["relationship_type"]))

    # Canonicalize and sort regulatory events; detect duplicates
    canonical_events: list[dict[str, Any]] = []
    seen_event_ids: set[str] = set()
    for raw_event in regulatory_events:
        canonical_event = canonicalize_regulatory_event(raw_event)
        event_id = canonical_event["id"]
        if event_id in seen_event_ids:
            raise CanonicalizationValidationError(f"Duplicate regulatory event id in snapshot: {event_id}")
        seen_event_ids.add(event_id)
        canonical_events.append(canonical_event)
    canonical_events.sort(key=lambda e: e["id"])

    top_level_dict: dict[str, Any] = {
        "assets": canonical_assets,
        "attestation_version": attestation_version,
        "contract_version": contract_version,
        "regulatory_events": canonical_events,
        "relationships": canonical_rels,
    }

    return canonical_json_dumps(top_level_dict)


def compute_snapshot_attestation_hash(
    *,
    assets: Iterable[Any],
    relationships: Iterable[Any],
    regulatory_events: Iterable[Any],
    attestation_version: str = ATTESTATION_VERSION_V1,
    contract_version: str = CONTRACT_VERSION_GRAC_V1,
) -> str:
    """Compute the SHA-256 hex digest of the canonical snapshot payload."""
    _, payload_bytes = generate_snapshot_canonical_payload(
        assets=assets,
        relationships=relationships,
        regulatory_events=regulatory_events,
        attestation_version=attestation_version,
        contract_version=contract_version,
    )
    return hashlib.sha256(payload_bytes).hexdigest()
