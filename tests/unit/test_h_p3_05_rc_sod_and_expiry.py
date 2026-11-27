"""Unit tests for H-P3-05: separation of duties (SoD) and evidence expiry on RC packets."""

from __future__ import annotations

from datetime import datetime, timezone

from scripts.verify_staging_promotion import (
    check_evidence_expiry,
    check_separation_of_duties,
)

UTC = timezone.utc


def test_separation_of_duties_allows_distinct_operators_and_rejects_self_approval() -> None:
    """Distinct Deploy operator and Promotion approver pass; identical owners fail SoD."""
    distinct_doc = """
    | Role | Named owner | Sign-off status | Notes |
    | --- | --- | --- | --- |
    | Deploy operator | @alice | Approved | |
    | Promotion approver | @bob | Approved | |
    """
    missing: list[str] = []
    check_separation_of_duties(distinct_doc, missing, require_explicit=True)
    assert missing == []

    same_doc = """
    | Role | Named owner | Sign-off status | Notes |
    | --- | --- | --- | --- |
    | Deploy operator | @alice | Approved | |
    | Promotion approver | @alice | Approved | |
    """
    missing_same: list[str] = []
    check_separation_of_duties(same_doc, missing_same, require_explicit=True)
    assert any("distinct individuals" in item for item in missing_same)

    missing_implicit: list[str] = []
    check_separation_of_duties(same_doc, missing_implicit, require_explicit=False)
    assert any("distinct individuals" in item for item in missing_implicit)


def test_separation_of_duties_requires_named_non_placeholder_owners_when_enforced() -> None:
    """Placeholder or blank operator entries fail when require_explicit=True."""
    placeholder_doc = """
    | Role | Named owner | Sign-off status | Notes |
    | --- | --- | --- | --- |
    | Deploy operator | TBD | Pending | |
    | Promotion approver | | Pending | |
    """
    missing: list[str] = []
    check_separation_of_duties(placeholder_doc, missing, require_explicit=True)
    assert len(missing) == 2


def test_evidence_expiry_enforces_explicit_expiry_and_max_age() -> None:
    """Fresh evidence passes; expired or overly stale evidence is rejected."""
    now = datetime(2026, 11, 27, 12, 0, 0, tzinfo=UTC)

    fresh_doc = """
    **Evidence capture date:** 2026-11-25
    **Evidence expiry date (UTC):** 2026-12-09
    """
    missing_fresh: list[str] = []
    check_evidence_expiry(fresh_doc, missing_fresh, require_explicit=True, max_age_days=14, now=now)
    assert missing_fresh == []

    expired_doc = """
    **Evidence capture date:** 2026-11-20
    **Evidence expiry date (UTC):** 2026-11-26
    """
    missing_expired: list[str] = []
    check_evidence_expiry(expired_doc, missing_expired, require_explicit=True, max_age_days=14, now=now)
    assert any("expired" in item for item in missing_expired)

    stale_doc = """
    **Evidence capture date:** 2026-11-01
    """
    missing_stale: list[str] = []
    check_evidence_expiry(stale_doc, missing_stale, require_explicit=True, max_age_days=14, now=now)
    assert any("exceeds maximum age" in item for item in missing_stale)

    undated_doc = "No dates here."
    missing_undated: list[str] = []
    check_evidence_expiry(undated_doc, missing_undated, require_explicit=True, max_age_days=14, now=now)
    assert any("is required" in item for item in missing_undated)
