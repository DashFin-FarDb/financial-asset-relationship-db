"""Unit tests for check_relationship_assertion_proof.py staging proof check script."""

from __future__ import annotations

from argparse import Namespace
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
    assert any("must be a non-empty list" in err for err in validator.errors)
    validator.errors.clear()

    # Test lists containing non-strings
    assert validator.scopes_are_consistent([123], ["scope1"], enforce_no_loss=True) is False  # type: ignore[list-item]
    assert any("invalid or missing predicate_id entries" in err for err in validator.errors)
    validator.errors.clear()


def test_actor_separated_validation() -> None:
    """Proposer, determiner, and executor roles must be distinct."""
    validator = ProofValidator({})

    # Identical proposer and determiner
    assert validator.actors_are_distinct("actor-1", "actor-1", None) is False
    assert "Collision: proposer and determiner are same" in validator.errors[0]

    # Identical proposer and executor
    validator.errors.clear()
    assert validator.actors_are_distinct("actor-1", "actor-2", "actor-1") is False
    assert "Collision: proposer and executor are same" in validator.errors[0]

    # Identical determiner and executor
    validator.errors.clear()
    assert validator.actors_are_distinct("actor-1", "actor-2", "actor-2") is False
    assert "Collision: determiner and executor are same" in validator.errors[0]

    # Distinct roles
    validator.errors.clear()
    assert validator.actors_are_distinct("actor-1", "actor-2", "actor-3") is True
    assert len(validator.errors) == 0


def test_restart_scopes_lookup_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that _validate_restart_scopes fails on missing, multiple, or malformed DB data."""
    import shutil
    import tempfile

    from src.data.database import create_engine_from_url, init_db

    # Setup SQLite test DB URL
    temp_dir = tempfile.mkdtemp()
    db_file = Path(temp_dir) / "test.db"
    url = f"sqlite:///{db_file}"
    engine = create_engine_from_url(url)
    init_db(engine)

    validator = ProofValidator({})

    # 1. No publication found
    validator.errors.clear()
    monkeypatch.setenv("DATABASE_URL", url)
    args = Namespace(
        before_scopes='["scope-1"]',
        after_scopes=None,
        run_id="nonexistent-run",
        rebuild_job_id="nonexistent-run",
        strict=True,
    )
    validator._validate_restart_scopes(args)
    assert any("Expected publication" in err for err in validator.errors)

    # 2. Malformed json scopes
    # Seed a publication and revision with malformed scopes JSON
    import uuid
    from datetime import datetime, timezone

    from sqlalchemy.orm import sessionmaker

    from src.data.db_models import RebuildJobORM
    from src.data.relationship_assertion_db_models import (
        RelationshipProjectionPublicationORM,
        RelationshipProjectionRevisionORM,
    )

    Session = sessionmaker(bind=engine)
    session = Session()
    now = datetime.now(timezone.utc)
    job = RebuildJobORM(
        job_id="malformed-run",
        requested_by="owner-1",
        status="succeeded",
        source="staging",
        created_at=now,
        updated_at=now,
        started_at=now,
        completed_at=now,
        execution_id="malformed-run",
    )
    revision = RelationshipProjectionRevisionORM(
        id="rev-malformed",
        purpose="testing",
        effective_at=now,
        known_at=now,
        contract_version="v1",
        projector_version="v1",
        edge_set_hash="a" * 64,
        projection_hash="b" * 64,
        governed_scopes="malformed { json }",
        created_at=now,
    )
    publication = RelationshipProjectionPublicationORM(
        id=str(uuid.uuid4()),
        revision_id="rev-malformed",
        rebuild_job_id="malformed-run",
        published_at=now,
        execution_id="malformed-run",
    )
    session.add(job)
    session.add(revision)
    session.flush()
    session.add(publication)
    session.commit()
    session.close()

    validator.errors.clear()
    args.rebuild_job_id = "malformed-run"
    validator._validate_restart_scopes(args)
    assert any("governed_scopes is malformed" in err for err in validator.errors)
    engine.dispose()
    shutil.rmtree(temp_dir)


@pytest.mark.parametrize(
    "mode, should_error",
    [
        ("seed_and_publish", False),
        ("verify_after_restart", True),
    ],
)
def test_strict_mode_expected_revision_hash_requirement(mode: str, should_error: bool):
    validator = ProofValidator({})
    args = Namespace(
        strict=True,
        mode=mode,
        revision_hash="a" * 64,
        expected_revision_hash=None,
    )
    validator._validate_revision(args)

    if should_error:
        assert any("Expected revision hash required" in err for err in validator.errors)
    else:
        assert not validator.errors


@pytest.mark.parametrize(
    ("scopes", "expected", "error_fragment"),
    [
        ({"not": "a list"}, None, "must be a non-empty list"),
        ([{"predicate_id": 123}], None, "invalid or missing predicate_id"),
        ([{"predicate_id": "scope-1"}], None, "invalid or missing predicate_id"),
        (
            [{"predicate_id": "scope-1", "purpose": "other"}],
            None,
            "incorrect purpose",
        ),
        ([" "], None, "invalid or missing predicate_id"),
        (
            ["scope-1", {"predicate_id": "scope-2", "purpose": "testing"}],
            ("hash", ["scope-1::testing", "scope-2::testing"]),
            None,
        ),
    ],
)
def test_validate_revision_scopes(
    scopes: object,
    expected: tuple[str, list[str]] | None,
    error_fragment: str | None,
) -> None:
    """Validate supported and rejected governed-scope representations."""
    import json
    from unittest.mock import MagicMock

    validator = ProofValidator({})
    conn = MagicMock()
    conn.execute().first.return_value = (
        "hash",
        json.dumps(scopes),
        "testing",
    )

    result = validator._get_and_validate_revision_scopes(
        conn=conn,
        clean_rev_id="r",
    )

    assert result == expected
    if error_fragment:
        assert any(error_fragment in error for error in validator.errors)
    else:
        assert not validator.errors


def test_scopes_are_consistent_purpose_mismatch():
    """Test that scopes_are_consistent rejects identical predicate_ids if the purpose differs."""
    validator = ProofValidator({})

    before = [{"predicate_id": "scope-1", "purpose": "purpose-a"}]
    after = [{"predicate_id": "scope-1", "purpose": "purpose-b"}]

    assert validator.scopes_are_consistent(before, after, enforce_no_loss=True) is False
    assert any("Scopes disappeared" in err for err in validator.errors)


def test_scopes_are_consistent_mixed_equivalent_representations() -> None:
    """Treat equivalent string and canonical object scopes identically."""
    validator = ProofValidator({})

    before = ["scope-1"]
    after = [{"predicate_id": "scope-1", "purpose": "testing"}]

    assert validator.scopes_are_consistent(
        before,
        after,
        enforce_no_loss=True,
        expected_purpose="testing",
    )
    assert not validator.errors
