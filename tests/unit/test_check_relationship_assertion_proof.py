import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.check_relationship_assertion_proof import ProofValidator


@pytest.fixture
def base_args(tmp_path):
    """Build valid strict restart arguments with a retained health observation."""
    health_json = {
        "persistence_configured": True,
        "graph": {"persistence_enabled": True, "persistence_loaded": True, "startup_source": "persisted"},
    }
    health_path = tmp_path / "health-observation.json"
    health_path.write_text(json.dumps(health_json))

    return argparse.Namespace(
        strict=True,
        require_persistence=True,
        startup_source="persisted",
        health_observation_path=str(health_path),
        run_id="run123",
        deployed_sha="sha123",
        before_assertion_count=10,
        before_edge_count=20,
        before_edge_manifest_hash="hash123",
        rebuild_job_id="job123",
        execution_id="exec123",
        check_authz=False,
        authz_evidence_path=None,
        publication_count=1,
        revision_hash="hash",
        proposer_id="foo",
        determiner_id="foo",
        owner_id="foo",
        expected_revision_id="rev1",
        before_scopes="[]",
        after_scopes="[]",
        empty_edge_before_scopes=None,
        empty_edge_after_scopes=None,
        history_entries=10,
        expected_revision_hash=None,
        empty_edge_assertion_count=0,
        mode="verify_after_restart",
    )


def test_strict_restart_missing_seed_baselines(base_args):
    """Reject strict restart verification if any seed baselines are missing."""
    validator = ProofValidator({"db_url": "sqlite:///:memory:"})

    # Missing assertion count
    base_args.before_assertion_count = None
    validator.validate_verify_after_restart(base_args)
    assert any("Strict restart verification requires seed graph baselines" in e for e in validator.errors)
    validator.errors.clear()

    # Missing edge count
    base_args.before_assertion_count = 10
    base_args.before_edge_count = None
    validator.validate_verify_after_restart(base_args)
    assert any("Strict restart verification requires seed graph baselines" in e for e in validator.errors)
    validator.errors.clear()

    # Missing edge manifest hash
    base_args.before_edge_count = 20
    base_args.before_edge_manifest_hash = ""
    validator.validate_verify_after_restart(base_args)
    assert any("Strict restart verification requires seed graph baselines" in e for e in validator.errors)


def test_zero_seed_assertion_count(base_args):
    """Reject strict restart verification if seed assertion count is zero."""
    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    base_args.before_assertion_count = 0
    validator.validate_verify_after_restart(base_args)
    assert any("Seed assertion count must be > 0" in e for e in validator.errors)


def test_missing_health_file(base_args):
    """Reject strict persistence proof without a retained health observation."""
    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    base_args.health_observation_path = None
    validator._validate_restart_persistence(base_args)
    assert any("Health observation JSON is missing" in e for e in validator.errors)


def test_malformed_health_json(tmp_path, base_args):
    """Reject persistence proof if health observation JSON is malformed."""
    bad_health = tmp_path / "bad.json"
    bad_health.write_text("{bad json")
    base_args.health_observation_path = str(bad_health)

    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    validator._validate_restart_persistence(base_args)
    assert any("Failed to load or parse health observation" in e for e in validator.errors)


def test_persistence_configured_false(tmp_path, base_args):
    """Reject persistence proof if persistence is not configured."""
    health = json.loads(Path(base_args.health_observation_path).read_text())
    health["persistence_configured"] = False
    Path(base_args.health_observation_path).write_text(json.dumps(health))

    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    validator._validate_restart_persistence(base_args)
    assert any("Health observation failed persistence validation" in e for e in validator.errors)


def test_persistence_enabled_false(tmp_path, base_args):
    """Reject persistence proof if persistence is not enabled in graph."""
    health = json.loads(Path(base_args.health_observation_path).read_text())
    health["graph"]["persistence_enabled"] = False
    Path(base_args.health_observation_path).write_text(json.dumps(health))

    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    validator._validate_restart_persistence(base_args)
    assert any("Health observation failed persistence validation" in e for e in validator.errors)


def test_persistence_loaded_false(tmp_path, base_args):
    """Reject persistence proof if persistence is not loaded in graph."""
    health = json.loads(Path(base_args.health_observation_path).read_text())
    health["graph"]["persistence_loaded"] = False
    Path(base_args.health_observation_path).write_text(json.dumps(health))

    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    validator._validate_restart_persistence(base_args)
    assert any("Health observation failed persistence validation" in e for e in validator.errors)


def test_startup_source_not_persisted(tmp_path, base_args):
    """Reject persistence proof if startup source is not persisted."""
    health = json.loads(Path(base_args.health_observation_path).read_text())
    health["graph"]["startup_source"] = "memory"
    Path(base_args.health_observation_path).write_text(json.dumps(health))

    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    validator._validate_restart_persistence(base_args)
    assert any("expected persisted" in e for e in validator.errors)


def test_startup_source_mismatch(tmp_path, base_args):
    """Reject persistence proof if startup source does not match expected source."""
    base_args.startup_source = "memory"
    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    validator._validate_restart_persistence(base_args)
    assert any("Health observation and supplied startup source do not match" in e for e in validator.errors)


def test_valid_health_provenance(base_args):
    """Verify successful binding of health observation metadata."""
    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    validator._validate_restart_persistence(base_args)
    assert len(validator.errors) == 0

    health_bytes = Path(base_args.health_observation_path).read_bytes()
    expected_digest = hashlib.sha256(health_bytes).hexdigest()

    assert validator.metadata["health_observation_sha256"] == expected_digest
    assert validator.metadata["health_observation_run_id"] == "run123"
    assert validator.metadata["health_observation_deployed_sha"] == "sha123"


def _setup_mock_session(
    mocker, mock_session, assertion_count, edge_count, edge_manifest_hash, expected_revision_id, execution_id
):
    """Setup mocked SQLAlchemy session methods for testing graph history reconstruction."""
    # We mock the return values for session.execute(...).all() and .scalar()
    # 1. Publication query: returns [(revision_id, execution_id)]
    # 2. Assertion IDs query: returns [[id_0], [id_1], ...]
    # 3. For each assertion ID: returns list of events via scalars().all()
    # 4. Edge count query via scalar()
    # 5. Edge manifest hash query via scalar()

    def execute_side_effect(stmt, params=None):
        """Side effect function to dispatch to appropriate mock result based on statement."""
        stmt_str = str(stmt).lower()
        mock_result = MagicMock()

        if "relationship_projection_publications" in stmt_str:
            mock_result.all.return_value = [(expected_revision_id, execution_id)]
        elif "relationship_projection_edges.assertion_id" in stmt_str:
            mock_result.all.return_value = [[f"id_{i}"] for i in range(assertion_count)]
        elif "relationship_assertion_events" in stmt_str:
            mock_result.scalars.return_value.all.return_value = []  # No events for now, we mock validate_reconstructed_assertion anyway
        elif "count" in stmt_str:
            mock_result.scalar.return_value = edge_count
        elif "hash" in stmt_str:
            mock_result.scalar.return_value = edge_manifest_hash
        else:
            mock_result.all.return_value = []
            mock_result.scalar.return_value = None

        return mock_result

    mock_session.execute.side_effect = execute_side_effect


@patch("sqlalchemy.create_engine")
@patch("sqlalchemy.orm.Session")
@patch("os.getenv")
def test_restart_assertion_count_mismatch(mock_getenv, mock_session_cls, mock_create_engine, base_args):
    """Reject restart reconstruction if assertion count does not match seed baseline."""
    mock_getenv.return_value = "sqlite:///:memory:"

    mock_session = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = mock_session

    # We reconstruct 5 assertions but expect 10 (from base_args.before_assertion_count)
    _setup_mock_session(
        mock_session, mock_session, 5, 20, "hash123", base_args.expected_revision_id, base_args.execution_id
    )

    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    validator._validate_reconstructed_assertion = MagicMock(return_value=True)

    validator._reconstruct_assertion_history_from_db(base_args)
    assert any("Assertion count mismatch: 5 vs expected 10" in e for e in validator.errors)


@patch("sqlalchemy.create_engine")
@patch("sqlalchemy.orm.Session")
@patch("os.getenv")
def test_edge_count_mismatch(mock_getenv, mock_session_cls, mock_create_engine, base_args):
    """Reject restart reconstruction if edge count does not match seed baseline."""
    mock_getenv.return_value = "sqlite:///:memory:"

    mock_session = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = mock_session

    # We reconstruct 10 assertions (correct) but 15 edges, expecting 20
    _setup_mock_session(
        mock_session, mock_session, 10, 15, "hash123", base_args.expected_revision_id, base_args.execution_id
    )

    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    validator._validate_reconstructed_assertion = MagicMock(return_value=True)

    validator._reconstruct_assertion_history_from_db(base_args)
    assert any("Edge count mismatch: 15 vs expected 20" in e for e in validator.errors)


@patch("sqlalchemy.create_engine")
@patch("sqlalchemy.orm.Session")
@patch("os.getenv")
def test_edge_manifest_mismatch(mock_getenv, mock_session_cls, mock_create_engine, base_args):
    """Reject restart reconstruction if edge manifest hash does not match seed baseline."""
    mock_getenv.return_value = "sqlite:///:memory:"

    mock_session = MagicMock()
    mock_session_cls.return_value.__enter__.return_value = mock_session

    # We reconstruct 10 assertions (correct) and 20 edges (correct), but wrong hash
    _setup_mock_session(
        mock_session, mock_session, 10, 20, "wronghash", base_args.expected_revision_id, base_args.execution_id
    )

    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    validator._validate_reconstructed_assertion = MagicMock(return_value=True)

    validator._reconstruct_assertion_history_from_db(base_args)
    assert any("Edge manifest hash mismatch: wronghash vs expected hash123" in e for e in validator.errors)
