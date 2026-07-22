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
    assert 'db_authz_status" != "passed"' in release_evidence_raw or (
        '[ "$db_authz_status" != "passed" ]' in release_evidence_raw
    )
    assert "Strict RC promotion requires database authorization to pass" in release_evidence_raw
    assert "hardening_tier=none" in release_evidence_raw


def test_release_evidence_unsets_empty_untrusted_roles(release_evidence_raw: str) -> None:
    """Empty FARDB_UNTRUSTED_DATABASE_ROLES must not block default roles."""
    assert "unset FARDB_UNTRUSTED_DATABASE_ROLES" in release_evidence_raw
    assert 'if [ -z "$FARDB_UNTRUSTED_DATABASE_ROLES" ]' in release_evidence_raw


def test_staging_promotion_fails_closed_without_db_secrets(staging_promotion_raw: str) -> None:
    """Staging promotion must not soft-skip H-P0-04 when secrets are missing."""
    assert "no_database_url_configured" in staging_promotion_raw
    assert '"status":"failed","reason":"no_database_url_configured"' in staging_promotion_raw
    assert "H-P0-04 requires live database authorization secrets" in staging_promotion_raw
    assert "check_database_authorization.py" in staging_promotion_raw


def test_staging_promotion_unsets_empty_untrusted_roles(staging_promotion_raw: str) -> None:
    """Staging must match production unset behavior for empty untrusted-roles secret."""
    assert "unset FARDB_UNTRUSTED_DATABASE_ROLES" in staging_promotion_raw
    assert 'if [ -z "$FARDB_UNTRUSTED_DATABASE_ROLES" ]' in staging_promotion_raw


def test_production_promotion_still_enforces_db_authz() -> None:
    """Production twin must keep H-P0-04 fail-closed wiring."""
    text = PRODUCTION_PROMOTION_PATH.read_text(encoding="utf-8")
    assert "check_database_authorization.py" in text
    assert "unset FARDB_UNTRUSTED_DATABASE_ROLES" in text
    assert "Database authorization gate failed (H-P0-04)" in text


def test_release_evidence_parses_as_workflow() -> None:
    """release-evidence-verify.yml must remain valid YAML for Actions."""
    with open(RELEASE_EVIDENCE_PATH, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert isinstance(data, dict)
    if True in data and "on" not in data:
        data["on"] = data.pop(True)
    assert "jobs" in data
