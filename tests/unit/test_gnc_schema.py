"""GNC Phase 1 schema and replay-corpus tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.gnc.schema import (
    GncSchemaError,
    RuleType,
    canonical_hash,
    canonical_json_bytes,
    evidence_satisfies,
    finding_fingerprint,
    validate_contract,
    validate_record,
    validate_replay_fixture,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "gnc" / "replay"
SHA_A = "a" * 64
SHA_B = "b" * 64


def _contract() -> dict:
    return {
        "schema_version": 1,
        "contract_id": "gnc.test-contract",
        "version": 1,
        "parent_issue": 1558,
        "objective": "Review one exact PR head against frozen scope.",
        "base_sha": SHA_A,
        "policy_sha": SHA_B,
        "risk_class": "high",
        "allowed_paths": ["src/example.py"],
        "forbidden_paths": [".github/workflows"],
        "rules": [
            {"rule_id": "scope.allowlist", "type": "mandatory_invariant", "statement": "Only allowed paths change."},
            {"rule_id": "style.preference", "type": "preferred_pattern", "statement": "Prefer a small diff."},
        ],
        "required_evidence": ["pytest"],
        "merge_criteria": ["Exact-head test passes."],
        "stop_conditions": ["An unapproved path changes."],
        "approved_by": "maintainer",
        "approved_at": "2026-08-22T00:00:00Z",
    }


@pytest.mark.unit
class TestCanonicalContract:
    def test_canonical_hash_ignores_mapping_order_and_whitespace(self) -> None:
        first = {"b": [2, 3], "a": "value"}
        second = json.loads('{  "a" : "value", "b" : [2,3] }')
        assert canonical_json_bytes(first) == canonical_json_bytes(second)
        assert canonical_hash(first) == canonical_hash(second)

    def test_canonical_json_rejects_floats(self) -> None:
        with pytest.raises(GncSchemaError, match="floating-point"):
            canonical_json_bytes({"confidence": 0.9})

    def test_rule_types_control_blocking_eligibility(self) -> None:
        contract = validate_contract(_contract())
        assert contract["rules"][0]["blocking_eligible"] is True
        assert contract["rules"][1]["blocking_eligible"] is False
        assert RuleType.EXAMPLE.may_block is False

    def test_contract_amendment_requires_previous_hash_and_reason(self) -> None:
        amended = _contract()
        amended["version"] = 2
        with pytest.raises(GncSchemaError, match="previous_contract_hash"):
            validate_contract(amended)
        amended["previous_contract_hash"] = canonical_hash(validate_contract(_contract()))
        amended["amendment_reason"] = "Add a newly approved validation target."
        assert validate_contract(amended)["version"] == 2

    def test_contract_paths_cannot_overlap(self) -> None:
        contract = _contract()
        contract["forbidden_paths"] = ["src/example.py"]
        with pytest.raises(GncSchemaError, match="overlap"):
            validate_contract(contract)


@pytest.mark.unit
class TestOperationalRecords:
    def test_evidence_only_satisfies_exact_executed_pass(self) -> None:
        evidence = {
            "record_type": "evidence",
            "evidence_id": "evidence.pytest",
            "requirement_id": "pytest",
            "head_sha": SHA_A,
            "target": "linux-py312",
            "state": "executed",
            "result": "pass",
        }
        assert evidence_satisfies(evidence, head_sha=SHA_A, target="linux-py312")
        assert not evidence_satisfies(evidence, head_sha=SHA_B, target="linux-py312")
        for state in ("skipped", "canceled", "unavailable", "stale_sha", "wrong_target"):
            invalid = dict(evidence, state=state, result="not_run")
            assert not evidence_satisfies(invalid, head_sha=SHA_A, target="linux-py312")

    def test_nonexecuted_evidence_cannot_claim_pass(self) -> None:
        with pytest.raises(GncSchemaError, match="cannot pass"):
            validate_record(
                {
                    "record_type": "evidence",
                    "evidence_id": "evidence.skipped",
                    "requirement_id": "pytest",
                    "head_sha": SHA_A,
                    "target": "linux",
                    "state": "skipped",
                    "result": "pass",
                }
            )

    def test_finding_fingerprint_ignores_reviewer_wording_and_spacing(self) -> None:
        first = finding_fingerprint(
            rule_id="scope.allowlist",
            subject="src/API.py",
            failure_mode="Unexpected   path changed",
            expected_outcome="Only approved paths change",
        )
        second = finding_fingerprint(
            rule_id="scope.allowlist",
            subject="SRC/api.py",
            failure_mode="unexpected path changed",
            expected_outcome="only approved paths change",
        )
        assert first == second

    def test_duplicate_requires_target_and_recurrence_remains_distinct(self) -> None:
        base = {
            "record_type": "finding",
            "finding_id": "finding.one",
            "rule_id": "scope.allowlist",
            "subject": "src/example.py",
            "failure_mode": "Outside approved scope",
            "expected_outcome": "Remain within scope",
            "origin": "deterministic",
            "state": "duplicate_of",
            "head_sha": SHA_A,
        }
        with pytest.raises(GncSchemaError, match="duplicate_of"):
            validate_record(base)
        duplicate = validate_record(dict(base, duplicate_of="finding.original"))
        recurrence = validate_record(dict(base, state="reopened_as_recurrence", finding_id="finding.recurrence"))
        assert duplicate["state"] == "duplicate_of"
        assert recurrence["state"] == "reopened_as_recurrence"

    def test_waiver_binds_actor_scope_head_contract_and_expiry(self) -> None:
        waiver = validate_record(
            {
                "record_type": "waiver",
                "waiver_id": "waiver.one",
                "finding_id": "finding.one",
                "actor": "maintainer",
                "reason": "Bounded exception",
                "scope": "src/example.py",
                "head_sha": SHA_A,
                "contract_hash": SHA_B,
                "expires_at": "2026-08-23T00:00:00Z",
            }
        )
        assert waiver["scope"] == "src/example.py"


@pytest.mark.unit
class TestReplayCorpus:
    def test_all_six_sanitized_scenarios_validate_deterministically(self) -> None:
        paths = sorted(FIXTURE_ROOT.glob("*.json"))
        assert len(paths) == 6
        for path in paths:
            raw = json.loads(path.read_text(encoding="utf-8"))
            first = validate_replay_fixture(raw)
            second = validate_replay_fixture(copy.deepcopy(raw))
            assert canonical_hash(first) == canonical_hash(second)

    def test_replay_rejects_raw_secret_or_executable_payload(self) -> None:
        raw = json.loads(next(FIXTURE_ROOT.glob("*.json")).read_text(encoding="utf-8"))
        raw["secret"] = "ghp_not-allowed"
        with pytest.raises(GncSchemaError, match="forbidden"):
            validate_replay_fixture(raw)

    def test_expected_finding_order_is_part_of_golden_verdict(self) -> None:
        raw = json.loads(next(FIXTURE_ROOT.glob("*.json")).read_text(encoding="utf-8"))
        raw["expected"]["finding_ids"] = []
        with pytest.raises(GncSchemaError, match="exactly match"):
            validate_replay_fixture(raw)
