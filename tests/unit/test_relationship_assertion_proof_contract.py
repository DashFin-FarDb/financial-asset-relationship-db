"""Unit tests for check_relationship_assertion_proof.py staging proof check script."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.check_relationship_assertion_proof import (
    ProofValidator,
    check_postgresql_proof,
    check_schema_authz_evidence,
    verify_deployed_sha,
)


def test_verify_deployed_sha_valid() -> None:
    """Test that a valid deployed SHA matching git HEAD verification succeeds."""
    with patch("subprocess.check_output") as mock_run:
        mock_run.return_value = b"a" * 40
        verify_deployed_sha("a" * 40)
        mock_run.assert_called_once()


def test_verify_deployed_sha_invalid() -> None:
    """Test that checking an invalid SHA format fails with ValueError."""
    with pytest.raises(ValueError, match="Invalid deployed SHA"):
        verify_deployed_sha("short")


def test_verify_deployed_sha_mismatch() -> None:
    """Test that verification fails if the deployed SHA differs from git HEAD."""
    with patch("subprocess.check_output") as mock_run:
        mock_run.return_value = b"b" * 40
        with pytest.raises(ValueError, match="Deployed SHA mismatch"):
            verify_deployed_sha("a" * 40)


def test_check_postgresql_proof_success() -> None:
    """Test that valid postgresql and postgres database URLs pass validation."""
    check_postgresql_proof("postgresql://user:pass@localhost:5432/db")
    check_postgresql_proof("postgres://user:pass@localhost:5432/db")


def test_check_postgresql_proof_failure() -> None:
    """Test that a non-postgresql URL (like sqlite) fails proof checks."""
    with pytest.raises(ValueError, match="PostgreSQL proof was skipped"):
        check_postgresql_proof("sqlite:///:memory:")


def test_check_schema_authz_evidence_not_found(tmp_path: Path) -> None:
    """Test that authorization evidence check fails if evidence file is missing."""
    with patch("scripts.check_relationship_assertion_proof.REPO_ROOT", tmp_path):
        evidence_dir = tmp_path / "docs" / "evidence-records"
        evidence_dir.mkdir(parents=True)
        with pytest.raises(ValueError, match="is missing or mismatched"):
            check_schema_authz_evidence("a" * 40)


def test_check_schema_authz_evidence_success(tmp_path: Path) -> None:
    """Test that authorization evidence validation succeeds when the correct file and SHA are present."""
    with patch("scripts.check_relationship_assertion_proof.REPO_ROOT", tmp_path):
        evidence_dir = tmp_path / "docs" / "evidence-records"
        evidence_dir.mkdir(parents=True)
        evidence_file = evidence_dir / "hp004-db-authz-pass.md"
        evidence_file.write_text("db_authz: PASS\ncommit: a" + "a" * 39, encoding="utf-8")
        check_schema_authz_evidence("a" * 40)


def test_publication_validation_cardinality() -> None:
    """Publication validation must require exactly 1 publication."""
    validator = ProofValidator({})

    # 0 publications
    assert validator.publication_is_correct(0, "owner-1", None) is False
    assert "Invalid publication count: 0 (need exactly 1)" in validator.errors

    # 1 publication
    validator.errors.clear()
    assert validator.publication_is_correct(1, "owner-1", None) is True
    assert len(validator.errors) == 0

    # 2 publications
    validator.errors.clear()
    assert validator.publication_is_correct(2, "owner-1", None) is False
    assert "Invalid publication count: 2 (need exactly 1)" in validator.errors


def test_publication_validation_fails_closed_without_owner() -> None:
    """Publication correlation must not be accepted as ownership evidence."""
    validator = ProofValidator({})

    assert validator.publication_is_correct(1, "", None) is False
    assert "Publication owner missing" in validator.errors


def test_scopes_are_consistent_invalid_types() -> None:
    """Test that scopes_are_consistent handles non-list or unhashable inputs gracefully."""
    validator = ProofValidator({})
    # Test non-list inputs
    assert validator.scopes_are_consistent("not-a-list", ["scope1"], enforce_no_loss=True) is False  # type: ignore[arg-type]
    assert "Scopes must be lists" in validator.errors

    # Test non-string inputs (unhashable)
    validator.errors.clear()
    assert validator.scopes_are_consistent([{"unhashable": "dict"}], ["scope1"], enforce_no_loss=True) is False  # type: ignore[list-item]
    assert "Scopes must be lists of strings" in validator.errors
