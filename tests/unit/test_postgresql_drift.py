"""Unit contracts for the profile-aware PostgreSQL drift gate."""

from __future__ import annotations

import json

from scripts.postgresql_drift import (
    CHECK_DRIFT,
    CHECK_PASSED,
    DRIFT_DETECTED,
    EVALUATION_INCOMPLETE,
    HIGHER_PRIORITY_CHECK_NOT_EVALUATED,
    LEDGER_HISTORY_MISMATCH,
    NOT_EVALUATED,
    PASS,
    PROVIDER_SCHEMA_DRIFT,
    REQUIRED_CHECK_NOT_EVALUATED,
    RUNTIME_COMPATIBILITY_MISMATCH,
    CheckResult,
    canonical_catalog_bytes,
    catalog_digest,
    evaluate_profile_drift,
    expected_managed_tables,
    select_public_status,
)
from scripts.postgresql_ledger import load_and_validate_manifest


def _check(category: str, state: str, reason: str | None = None) -> CheckResult:
    return CheckResult(category.lower(), category, state, reason)


def test_catalog_serialization_is_key_order_and_whitespace_stable() -> None:
    """Equivalent deparsed whitespace and mapping order must produce one digest."""
    left = {"z": "CHECK  ( value > 0 )", "a": [{"roles": ["b", "a"]}]}
    right = {"a": [{"roles": ["a", "b"]}], "z": "CHECK ( value > 0 )"}

    assert canonical_catalog_bytes(left) == canonical_catalog_bytes(right)
    assert catalog_digest(left) == catalog_digest(right)


def test_expected_managed_tables_are_profile_scoped() -> None:
    """A component target must not silently inherit another component's tables."""
    assert expected_managed_tables("auth") == ("user_credentials",)
    assert "distributed_locks" not in expected_managed_tables("graph")
    assert set(expected_managed_tables("combined")) > set(expected_managed_tables("graph"))
    assert expected_managed_tables("unknown") == ()


def test_clean_required_checks_pass() -> None:
    """PASS requires every required check to complete without drift."""
    checks = tuple(
        _check(category, CHECK_PASSED)
        for category in (
            LEDGER_HISTORY_MISMATCH,
            PROVIDER_SCHEMA_DRIFT,
            RUNTIME_COMPATIBILITY_MISMATCH,
        )
    )
    assert select_public_status(checks) == (PASS, None, ())


def test_primary_category_uses_ratified_precedence() -> None:
    """Combined drift must publish only the earliest completed category."""
    checks = (
        _check(LEDGER_HISTORY_MISMATCH, CHECK_PASSED),
        _check(PROVIDER_SCHEMA_DRIFT, CHECK_DRIFT),
        _check(RUNTIME_COMPATIBILITY_MISMATCH, CHECK_DRIFT),
    )
    assert select_public_status(checks) == (DRIFT_DETECTED, PROVIDER_SCHEMA_DRIFT, ())


def test_unavailable_higher_priority_check_cannot_be_masked() -> None:
    """A detected lower category cannot replace unknown higher-priority state."""
    checks = (
        _check(LEDGER_HISTORY_MISMATCH, NOT_EVALUATED, REQUIRED_CHECK_NOT_EVALUATED),
        _check(PROVIDER_SCHEMA_DRIFT, CHECK_DRIFT),
        _check(RUNTIME_COMPATIBILITY_MISMATCH, CHECK_PASSED),
    )
    status, primary, reasons = select_public_status(checks)
    assert status == EVALUATION_INCOMPLETE
    assert primary is None
    assert reasons == (HIGHER_PRIORITY_CHECK_NOT_EVALUATED, REQUIRED_CHECK_NOT_EVALUATED)


def test_unavailable_lower_priority_check_does_not_hide_primary() -> None:
    """Checks downstream of a publishable primary may remain unavailable."""
    checks = (
        _check(LEDGER_HISTORY_MISMATCH, CHECK_DRIFT),
        _check(PROVIDER_SCHEMA_DRIFT, NOT_EVALUATED, REQUIRED_CHECK_NOT_EVALUATED),
        _check(RUNTIME_COMPATIBILITY_MISMATCH, NOT_EVALUATED, REQUIRED_CHECK_NOT_EVALUATED),
    )
    assert select_public_status(checks) == (
        DRIFT_DETECTED,
        LEDGER_HISTORY_MISMATCH,
        (REQUIRED_CHECK_NOT_EVALUATED,),
    )


def test_unknown_profile_fails_closed_without_connecting() -> None:
    """Unknown profile selection must produce bounded incomplete diagnostics."""

    class NoConnection:
        def cursor(self) -> object:
            raise AssertionError("unknown profile must fail before database access")

    report = evaluate_profile_drift(
        NoConnection(),  # type: ignore[arg-type]
        load_and_validate_manifest(),
        "unknown",
        "fresh-v1",
        "loopback",
        runtime_check=lambda: None,
    )
    assert report.status == EVALUATION_INCOMPLETE
    assert report.primary_category is None
    assert report.not_evaluated_count == 3
    assert report.reason_codes == (REQUIRED_CHECK_NOT_EVALUATED,)


def test_public_report_contains_no_restricted_details() -> None:
    """Public JSON must expose counts and digests, never object names or raw errors."""
    report = evaluate_profile_drift(
        object(),  # type: ignore[arg-type]
        load_and_validate_manifest(),
        "unknown",
        "hosted-legacy-v1",
        "hosted",
        runtime_check=None,
    )
    payload = json.dumps(report.as_public_dict(), sort_keys=True)
    assert "database_url" not in payload
    assert "raw_error" not in payload
    assert "object_names" not in payload


def test_manifest_records_versioned_profile_catalog_digests() -> None:
    """The immutable profile manifest must bind every expected catalog digest."""
    manifest = load_and_validate_manifest()
    for profile in ("auth", "graph", "coordination", "combined"):
        assert len(manifest.catalog_digest_for_profile(profile)) == 64
