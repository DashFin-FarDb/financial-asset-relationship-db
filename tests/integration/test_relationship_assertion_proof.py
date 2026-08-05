"""Integration test for check_relationship_assertion_proof.py staging proof check script."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from scripts.check_relationship_assertion_proof import run_seed_and_publish, run_verify_after_restart
from src.data.database import create_engine_from_url, init_db


@pytest.fixture
def test_db_url(tmp_path: Path) -> str:
    """Fixture to create and initialize a temporary SQLite test database."""
    db_file = tmp_path / "staging-proof-test.db"
    url = f"sqlite:///{db_file}"
    engine = create_engine_from_url(url)
    init_db(engine)
    engine.dispose()
    return url


def _no_op(*_args: Any, **_kwargs: Any) -> None:
    """Typed no-op used to isolate external proof boundaries."""


@patch("scripts.check_relationship_assertion_proof.check_postgresql_proof", _no_op)
@patch("scripts.check_relationship_assertion_proof.verify_deployed_sha", _no_op)
@patch("scripts.check_relationship_assertion_proof.check_schema_authz_evidence", _no_op)
def test_staging_proof_flow_sqlite(test_db_url: str) -> None:
    """Test the complete staging proof seeding, publication, and restart verification flow using SQLite."""
    # 1. Run seed_and_publish
    deployed_sha = "a" * 40
    run_id = "test-run-1"

    metadata = run_seed_and_publish(test_db_url, deployed_sha, run_id)
    assert metadata["deployed_sha"] == deployed_sha
    assert metadata["run_id"] == run_id
    assert metadata["mode"] == "seed_and_publish"
    assert metadata["edge_set_hash"] != ""
    assert metadata["projection_hash"] != ""
    assert metadata["governed_scopes"] == ["scope-1"]
    assert metadata["proposer_id"] == "proposer-actor-1"
    assert metadata["determiner_id"] == "determiner-actor-1"
    assert metadata["owner_id"] == "owner-actor-1"

    # 2. Run verify_after_restart
    metadata_verify = run_verify_after_restart(test_db_url, deployed_sha, run_id, metadata)
    assert metadata_verify["deployed_sha"] == deployed_sha
    assert metadata_verify["run_id"] == run_id
    assert metadata_verify["mode"] == "verify_after_restart"
    assert metadata_verify["scope_continuity_passed"] is True
    assert metadata_verify["historical_reconstruction_passed"] is True


@patch("scripts.check_relationship_assertion_proof.check_postgresql_proof", _no_op)
@patch("scripts.check_relationship_assertion_proof.verify_deployed_sha", _no_op)
@patch("scripts.check_relationship_assertion_proof.check_schema_authz_evidence", _no_op)
def test_proof_validator_populates_from_db(test_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that ProofValidator correctly populates proposer, determiner, owner, and pub_count from DB."""
    from argparse import Namespace

    from scripts.check_relationship_assertion_proof import ProofValidator

    deployed_sha = "a" * 40
    run_id = "test-run-2"
    run_seed_and_publish(test_db_url, deployed_sha, run_id)

    monkeypatch.setenv("DATABASE_URL", test_db_url)
    validator = ProofValidator({})
    args = Namespace(
        mode="seed_and_publish",
        deployed_sha=deployed_sha,
        contract_digest="c" * 64,
        registry_digest="d" * 64,
        authz_evidence=None,
        proposer_id=None,
        determiner_id=None,
        executor_id=None,
        publication_count=None,
        owner_id=None,
        expected_owner=None,
        revision_hash=None,
        expected_revision_hash=None,
        output=None,
        strict=False,
        rebuild_job_id=run_id,
        execution_id=run_id,
    )

    result = validator.validate_seed_and_publish(args)
    assert result["status"] == "passed"
    assert args.proposer_id == "proposer-actor-1"
    assert args.determiner_id == "determiner-actor-1"
    assert args.owner_id == "owner-actor-1"
    assert args.publication_count == 1


@patch("scripts.check_relationship_assertion_proof.check_postgresql_proof", _no_op)
@patch("scripts.check_relationship_assertion_proof.verify_deployed_sha", _no_op)
@patch("scripts.check_relationship_assertion_proof.check_schema_authz_evidence", _no_op)
def test_proof_validator_rejects_unrelated_events_and_ambiguity(
    test_db_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that ProofValidator fails on ambiguous actor evidence or unrelated events."""
    import uuid
    from argparse import Namespace
    from datetime import datetime, timezone

    from sqlalchemy.orm import sessionmaker

    from scripts.check_relationship_assertion_proof import ProofValidator
    from src.data.relationship_assertion_db_models import RelationshipAssertionEventORM

    deployed_sha = "a" * 40
    run_id = "test-run-3"
    run_seed_and_publish(test_db_url, deployed_sha, run_id)

    # Manually add an ambiguous determiner event (same job, same assertion, different actor)
    engine = create_engine_from_url(test_db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Find the assertion seeded
    event = session.query(RelationshipAssertionEventORM).filter_by(correlation_id=run_id).first()
    assertion_id = event.assertion_id

    # Create another det event to introduce ambiguity
    ambiguous_det = RelationshipAssertionEventORM(
        id=str(uuid.uuid4()),
        assertion_id=assertion_id,
        sequence=3,
        from_state="Accepted",
        to_state="Accepted",
        authority="determiner",
        actor_id="determiner-actor-2",  # Different actor
        rationale="Ambiguous determination",
        policy_version="v1",
        recorded_at=datetime.now(timezone.utc),
        correlation_id=run_id,
    )
    session.add(ambiguous_det)
    session.commit()
    session.close()

    monkeypatch.setenv("DATABASE_URL", test_db_url)
    validator = ProofValidator({})
    args = Namespace(
        mode="seed_and_publish",
        deployed_sha=deployed_sha,
        contract_digest="c" * 64,
        registry_digest="d" * 64,
        authz_evidence=None,
        proposer_id=None,
        determiner_id=None,
        executor_id=None,
        publication_count=None,
        owner_id=None,
        expected_owner=None,
        revision_hash=None,
        expected_revision_hash=None,
        output=None,
        strict=False,
        rebuild_job_id=run_id,
        execution_id=run_id,
    )

    result = validator.validate_seed_and_publish(args)
    assert result["status"] == "failed"
    assert any("Ambiguous determining actor evidence" in err for err in result["errors"])
    engine.dispose()


@patch("scripts.check_relationship_assertion_proof.check_postgresql_proof", _no_op)
@patch("scripts.check_relationship_assertion_proof.verify_deployed_sha", _no_op)
@patch("scripts.check_relationship_assertion_proof.check_schema_authz_evidence", _no_op)
def test_proof_validator_rejects_unrelated_newer_job(test_db_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that ProofValidator does not bind to a newer unrelated job in the database."""
    from argparse import Namespace

    from scripts.check_relationship_assertion_proof import ProofValidator

    deployed_sha = "a" * 40
    target_job_id = "target-job-1"
    run_seed_and_publish(test_db_url, deployed_sha, target_job_id)

    # Seed a newer unrelated job afterwards
    unrelated_job_id = "newer-unrelated-job"
    run_seed_and_publish(test_db_url, deployed_sha, unrelated_job_id)

    monkeypatch.setenv("DATABASE_URL", test_db_url)
    validator = ProofValidator({})

    # Certify the target job (should succeed even though it's older than the unrelated job)
    args = Namespace(
        mode="seed_and_publish",
        deployed_sha=deployed_sha,
        contract_digest="c" * 64,
        registry_digest="d" * 64,
        authz_evidence=None,
        proposer_id=None,
        determiner_id=None,
        executor_id=None,
        publication_count=None,
        owner_id=None,
        expected_owner=None,
        revision_hash=None,
        expected_revision_hash=None,
        output=None,
        strict=False,
        rebuild_job_id=target_job_id,
        execution_id=target_job_id,
    )
    result = validator.validate_seed_and_publish(args)
    assert result["status"] == "passed"
    assert args.rebuild_job_id == target_job_id

    # Try to certify with a wrong/non-existent job ID (should fail)
    validator_fail = ProofValidator({})
    args_fail = Namespace(
        mode="seed_and_publish",
        deployed_sha=deployed_sha,
        contract_digest="c" * 64,
        registry_digest="d" * 64,
        authz_evidence=None,
        proposer_id=None,
        determiner_id=None,
        executor_id=None,
        publication_count=None,
        owner_id=None,
        expected_owner=None,
        revision_hash=None,
        expected_revision_hash=None,
        output=None,
        strict=False,
        rebuild_job_id="wrong-job-id",
        execution_id="wrong-job-id",
    )
    result_fail = validator_fail.validate_seed_and_publish(args_fail)
    assert result_fail["status"] == "failed"
    assert any("Certified rebuild job was not found" in err for err in result_fail["errors"])
