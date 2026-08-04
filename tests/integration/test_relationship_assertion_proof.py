"""Integration test for check_relationship_assertion_proof.py staging proof check script."""

from __future__ import annotations

from pathlib import Path
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


@patch("scripts.check_relationship_assertion_proof.check_postgresql_proof", lambda url: None)
@patch("scripts.check_relationship_assertion_proof.verify_deployed_sha", lambda sha: None)
@patch("scripts.check_relationship_assertion_proof.check_schema_authz_evidence", lambda sha: None)
def test_staging_proof_flow_sqlite(test_db_url: str, tmp_path: Path) -> None:
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
    assert len(metadata["governed_scopes"]) > 0

    # 2. Run verify_after_restart
    metadata_verify = run_verify_after_restart(test_db_url, deployed_sha, run_id, metadata)
    assert metadata_verify["deployed_sha"] == deployed_sha
    assert metadata_verify["run_id"] == run_id
    assert metadata_verify["mode"] == "verify_after_restart"
    assert metadata_verify["scope_continuity_passed"] is True
    assert metadata_verify["historical_reconstruction_passed"] is True
