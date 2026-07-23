"""Contract tests for H-P0-04 database authorization gate wiring."""

from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_EVIDENCE_PATH = REPO_ROOT / ".github" / "workflows" / "release-evidence-verify.yml"
STAGING_PROMOTION_PATH = REPO_ROOT / ".github" / "workflows" / "staging-promotion.yml"
PRODUCTION_PROMOTION_PATH = REPO_ROOT / ".github" / "workflows" / "production-promotion.yml"


@pytest.fixture(name="release_evidence_raw")
def release_evidence_raw_fixture() -> str:
    """Return raw release-evidence-verify.yml text."""
    return RELEASE_EVIDENCE_PATH.read_text(encoding="utf-8")


@pytest.fixture(name="staging_promotion_raw")
def staging_promotion_raw_fixture() -> str:
    """Return raw staging-promotion.yml text."""
    return STAGING_PROMOTION_PATH.read_text(encoding="utf-8")


def test_release_evidence_workflow_exists() -> None:
    """H-P0-04 requires the release-evidence Assert path workflow."""
    assert RELEASE_EVIDENCE_PATH.is_file()


def test_release_evidence_invokes_database_authorization_checker(release_evidence_raw: str) -> None:
    """Release-evidence must run the ADR 0007 bounded checker."""
    assert "check_database_authorization.py" in release_evidence_raw
    assert "gate_db_authz" in release_evidence_raw
    assert "db-authz-output.json" in release_evidence_raw


def test_release_evidence_p0_fails_closed_on_skipped_db_authz(release_evidence_raw: str) -> None:
    """hardening_tier=P0 must require db_authz status=passed (H-P0-04)."""
    assert '[ "$db_authz_status" != "passed" ]' in release_evidence_raw
    assert "database authorization (H-P0-04)" in release_evidence_raw
    assert "hardening_tier=none" in release_evidence_raw


def test_release_evidence_aggregates_strict_gate_failures(release_evidence_raw: str) -> None:
    """Strict Assert path must report readiness, docs, and db_authz failures together."""
    assert 'FAILURES=""' in release_evidence_raw
    assert "hosted readiness" in release_evidence_raw
    assert "docs readiness" in release_evidence_raw
    assert "Strict RC promotion requires the following to pass:" in release_evidence_raw


def test_release_evidence_requires_all_db_boundaries(release_evidence_raw: str) -> None:
    """Partial URL secret sets must not produce db_authz passed (production parity)."""
    assert "missing_asset_graph_database_url" in release_evidence_raw
    assert "missing_auth_database_url" in release_evidence_raw
    assert "missing_coordination_database_url" in release_evidence_raw
    assert 'if [ -z "$ASSET_GRAPH_DATABASE_URL" ]' in release_evidence_raw
    assert 'if [ -z "$COORDINATION_DATABASE_URL" ]' in release_evidence_raw
    assert 'if [ -z "${DATABASE_URL}${POSTGRES_URL}" ]' in release_evidence_raw


def test_release_evidence_unsets_empty_untrusted_roles(release_evidence_raw: str) -> None:
    """Empty FARDB_UNTRUSTED_DATABASE_ROLES must not block default roles."""
    assert "unset FARDB_UNTRUSTED_DATABASE_ROLES" in release_evidence_raw
    assert 'if [ -z "$FARDB_UNTRUSTED_DATABASE_ROLES" ]' in release_evidence_raw


def test_release_evidence_wires_exposed_schemas_env(release_evidence_raw: str) -> None:
    """Release-evidence must pass global and per-boundary schema secrets into the checker."""
    assert "FARDB_EXPOSED_DATABASE_SCHEMAS: ${{ secrets.FARDB_EXPOSED_DATABASE_SCHEMAS }}" in release_evidence_raw
    assert "FARDB_EXPOSED_DATABASE_SCHEMAS_ASSET_GRAPH" in release_evidence_raw
    assert "FARDB_EXPOSED_DATABASE_SCHEMAS_COORDINATION" in release_evidence_raw
    assert "FARDB_EXPOSED_DATABASE_SCHEMAS_DATABASE" in release_evidence_raw
    assert "FARDB_EXPOSED_DATABASE_SCHEMAS_POSTGRES" in release_evidence_raw
    assert 'unset "$schema_secret"' in release_evidence_raw


def test_release_evidence_uses_hosted_readiness_cold_start_timeout(release_evidence_raw: str) -> None:
    """Release-evidence readiness must pin --timeout 30 for Vercel Python cold starts."""
    assert "check_hosted_readiness.py" in release_evidence_raw
    assert "--timeout 30" in release_evidence_raw


def test_staging_promotion_fails_closed_without_db_secrets(staging_promotion_raw: str) -> None:
    """Staging promotion must fail closed on missing required H-P0-04 boundaries."""
    assert "missing_asset_graph_database_url" in staging_promotion_raw
    assert "missing_auth_database_url" in staging_promotion_raw
    assert "missing_coordination_database_url" in staging_promotion_raw
    assert "no_database_url_configured" not in staging_promotion_raw
    assert "check_database_authorization.py" in staging_promotion_raw


def test_staging_promotion_uses_hosted_readiness_cold_start_timeout(staging_promotion_raw: str) -> None:
    """Staging promotion readiness must pin --timeout 30 for Vercel Python cold starts."""
    assert "check_hosted_readiness.py" in staging_promotion_raw
    assert "--timeout 30" in staging_promotion_raw
    assert "--require-persistence" in staging_promotion_raw


def test_staging_promotion_unsets_empty_untrusted_roles(staging_promotion_raw: str) -> None:
    """Staging must match production unset behavior for empty untrusted-roles secret."""
    assert "unset FARDB_UNTRUSTED_DATABASE_ROLES" in staging_promotion_raw
    assert 'if [ -z "$FARDB_UNTRUSTED_DATABASE_ROLES" ]' in staging_promotion_raw
    assert "FARDB_EXPOSED_DATABASE_SCHEMAS_ASSET_GRAPH" in staging_promotion_raw
    assert 'unset "$schema_secret"' in staging_promotion_raw


def test_production_promotion_still_enforces_db_authz() -> None:
    """Production twin must keep H-P0-04 fail-closed wiring."""
    text = PRODUCTION_PROMOTION_PATH.read_text(encoding="utf-8")
    assert "check_database_authorization.py" in text
    assert "unset FARDB_UNTRUSTED_DATABASE_ROLES" in text
    assert "FARDB_EXPOSED_DATABASE_SCHEMAS" in text
    assert "FARDB_EXPOSED_DATABASE_SCHEMAS_COORDINATION" in text
    assert 'unset "$schema_secret"' in text
    assert "Database authorization gate failed (H-P0-04)" in text


def test_release_evidence_parses_as_workflow(release_evidence_raw: str) -> None:
    """release-evidence-verify.yml must remain valid YAML for Actions."""
    data = yaml.safe_load(release_evidence_raw)
    assert isinstance(data, dict)
    assert "jobs" in data
