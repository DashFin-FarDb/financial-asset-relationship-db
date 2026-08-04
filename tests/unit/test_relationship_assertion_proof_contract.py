"""Unit tests for check_relationship_assertion_proof.py staging proof check script."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.check_relationship_assertion_proof import (
    check_postgresql_proof,
    check_schema_authz_evidence,
    verify_deployed_sha,
)


def test_verify_deployed_sha_valid() -> None:
    with patch("subprocess.check_output") as mock_run:
        mock_run.return_value = b"a" * 40
        verify_deployed_sha("a" * 40)
        mock_run.assert_called_once()


def test_verify_deployed_sha_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid deployed SHA"):
        verify_deployed_sha("short")


def test_verify_deployed_sha_mismatch() -> None:
    with patch("subprocess.check_output") as mock_run:
        mock_run.return_value = b"b" * 40
        with pytest.raises(ValueError, match="Deployed SHA mismatch"):
            verify_deployed_sha("a" * 40)


def test_check_postgresql_proof_success() -> None:
    check_postgresql_proof("postgresql://user:pass@localhost:5432/db")
    check_postgresql_proof("postgres://user:pass@localhost:5432/db")


def test_check_postgresql_proof_failure() -> None:
    with pytest.raises(ValueError, match="PostgreSQL proof was skipped"):
        check_postgresql_proof("sqlite:///:memory:")


def test_check_schema_authz_evidence_not_found(tmp_path: Path) -> None:
    with patch("scripts.check_relationship_assertion_proof.REPO_ROOT", tmp_path):
        evidence_dir = tmp_path / "docs" / "evidence-records"
        evidence_dir.mkdir(parents=True)
        with pytest.raises(ValueError, match="is missing or mismatched"):
            check_schema_authz_evidence("a" * 40)


def test_check_schema_authz_evidence_success(tmp_path: Path) -> None:
    with patch("scripts.check_relationship_assertion_proof.REPO_ROOT", tmp_path):
        evidence_dir = tmp_path / "docs" / "evidence-records"
        evidence_dir.mkdir(parents=True)
        evidence_file = evidence_dir / "hp004-db-authz-pass.md"
        evidence_file.write_text("db_authz: PASS\ncommit: a" + "a" * 39, encoding="utf-8")
        check_schema_authz_evidence("a" * 40)
