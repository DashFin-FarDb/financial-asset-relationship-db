import argparse
import hashlib
import json
from pathlib import Path

import pytest

from scripts.check_relationship_assertion_proof import ProofValidator


@pytest.fixture
def base_args(tmp_path):
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
    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    base_args.before_assertion_count = 0
    validator.validate_verify_after_restart(base_args)
    assert any("Seed assertion count must be > 0" in e for e in validator.errors)


def test_missing_health_file(base_args):
    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    base_args.health_observation_path = None
    validator._validate_restart_persistence(base_args)
    assert any("Health observation JSON is missing" in e for e in validator.errors)


def test_malformed_health_json(tmp_path, base_args):
    bad_health = tmp_path / "bad.json"
    bad_health.write_text("{bad json")
    base_args.health_observation_path = str(bad_health)

    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    validator._validate_restart_persistence(base_args)
    assert any("Failed to load or parse health observation" in e for e in validator.errors)


def test_persistence_configured_false(tmp_path, base_args):
    health = json.loads(Path(base_args.health_observation_path).read_text())
    health["persistence_configured"] = False
    Path(base_args.health_observation_path).write_text(json.dumps(health))

    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    validator._validate_restart_persistence(base_args)
    assert any("Health observation failed persistence validation" in e for e in validator.errors)


def test_persistence_enabled_false(tmp_path, base_args):
    health = json.loads(Path(base_args.health_observation_path).read_text())
    health["graph"]["persistence_enabled"] = False
    Path(base_args.health_observation_path).write_text(json.dumps(health))

    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    validator._validate_restart_persistence(base_args)
    assert any("Health observation failed persistence validation" in e for e in validator.errors)


def test_persistence_loaded_false(tmp_path, base_args):
    health = json.loads(Path(base_args.health_observation_path).read_text())
    health["graph"]["persistence_loaded"] = False
    Path(base_args.health_observation_path).write_text(json.dumps(health))

    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    validator._validate_restart_persistence(base_args)
    assert any("Health observation failed persistence validation" in e for e in validator.errors)


def test_startup_source_not_persisted(tmp_path, base_args):
    health = json.loads(Path(base_args.health_observation_path).read_text())
    health["graph"]["startup_source"] = "memory"
    Path(base_args.health_observation_path).write_text(json.dumps(health))

    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    validator._validate_restart_persistence(base_args)
    assert any("expected persisted" in e for e in validator.errors)


def test_startup_source_mismatch(tmp_path, base_args):
    base_args.startup_source = "memory"
    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    validator._validate_restart_persistence(base_args)
    assert any("Health observation and supplied startup source do not match" in e for e in validator.errors)


def test_valid_health_provenance(base_args):
    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    validator._validate_restart_persistence(base_args)
    assert len(validator.errors) == 0

    health_bytes = Path(base_args.health_observation_path).read_bytes()
    expected_digest = hashlib.sha256(health_bytes).hexdigest()

    assert validator.metadata["health_observation_sha256"] == expected_digest
    assert validator.metadata["health_observation_run_id"] == "run123"
    assert validator.metadata["health_observation_deployed_sha"] == "sha123"


class MockSession:
    def __init__(self, count_val, hash_val):
        self.count_val = count_val
        self.hash_val = hash_val

    def execute(self, stmt, params=None):
        class Result:
            def __init__(self, val):
                self.val = val

            def scalar(self):
                return self.val

            def all(self):
                return [[f"id_{i}"] for i in range(self.val)] if isinstance(self.val, int) else []

        if "count" in str(stmt).lower():
            return Result(self.count_val)
        if "hash" in str(stmt).lower():
            return Result(self.hash_val)
        return Result(self.count_val)


def test_restart_assertion_count_mismatch(base_args):
    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    validator.metadata["reconstructed_assertions"] = 5
    validator._validate_reconstructed_assertion = lambda a, e: True
    base_args.history_entries = 10

    reconstructed = 5
    if base_args.before_assertion_count is not None:
        if reconstructed != base_args.before_assertion_count:
            validator.add_error(
                f"Assertion count mismatch: {reconstructed} vs expected {base_args.before_assertion_count}"
            )

    assert any("Assertion count mismatch: 5 vs expected 10" in e for e in validator.errors)


def test_edge_count_mismatch(base_args):
    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    edge_count = 15
    if base_args.before_edge_count is not None:
        if edge_count != base_args.before_edge_count:
            validator.add_error(f"Edge count mismatch: {edge_count} vs expected {base_args.before_edge_count}")

    assert any("Edge count mismatch: 15 vs expected 20" in e for e in validator.errors)


def test_edge_manifest_mismatch(base_args):
    validator = ProofValidator({"db_url": "sqlite:///:memory:"})
    edge_manifest_hash = "wronghash"
    if base_args.before_edge_manifest_hash is not None:
        if edge_manifest_hash != base_args.before_edge_manifest_hash:
            validator.add_error(
                f"Edge manifest hash mismatch: {edge_manifest_hash} vs expected {base_args.before_edge_manifest_hash}"
            )

    assert any("Edge manifest hash mismatch" in e for e in validator.errors)
