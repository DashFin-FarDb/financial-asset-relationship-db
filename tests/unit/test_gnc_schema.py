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
GIT_SHA_A = "a" * 40
GIT_SHA_B = "b" * 40
DEFAULT_REPLAY_FIXTURE = FIXTURE_ROOT / "grac-durable-scope-gap.json"


def _replay_fixture() -> dict:
    return json.loads(DEFAULT_REPLAY_FIXTURE.read_text(encoding="utf-8"))


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


def _review_run(contract_hash: str, context_digest: str, analyzed_blobs: dict[str, str]) -> dict:
    return {
        "record_type": "review_run",
        "run_id": "run.context",
        "head_sha": SHA_A,
        "merge_base_sha": SHA_B,
        "contract_hash": contract_hash,
        "policy_sha": SHA_B,
        "context_digest": context_digest,
        "evaluator_version": "gnc-phase1",
        "target": "repository",
        "review_mode": "full",
        "verdict": "pass",
        "analyzed_blobs": analyzed_blobs,
    }


def _finding(**overrides: object) -> dict:
    record: dict[str, object] = {
        "record_type": "finding",
        "finding_id": "finding.one",
        "rule_id": "scope.allowlist",
        "subject": "src/example.py",
        "failure_mode": "Outside approved scope",
        "expected_outcome": "Remain within scope",
        "origin": "deterministic",
        "state": "open",
        "head_sha": SHA_A,
    }
    record.update(overrides)
    return record


def _waiver(**overrides: object) -> dict:
    record: dict[str, object] = {
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
    record.update(overrides)
    return record


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

    @pytest.mark.parametrize("schema_version", [True, 1.0])
    def test_contract_schema_version_must_be_an_integer(self, schema_version: object) -> None:
        contract = _contract()
        contract["schema_version"] = schema_version
        with pytest.raises(GncSchemaError, match="contract.schema_version: must be an integer"):
            validate_contract(contract)

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

    def test_contract_version_record_binds_normalized_contract_and_hash(self) -> None:
        contract = validate_contract(_contract())
        record = validate_record({"record_type": "contract_version", "contract": _contract()})
        assert record == {
            "record_type": "contract_version",
            "contract": contract,
            "contract_hash": canonical_hash(contract),
        }

    @pytest.mark.parametrize("approved_at", ["not-a-date", "2026-08-22T00:00:00"])
    def test_contract_approval_timestamp_must_be_timezone_aware_iso_8601(self, approved_at: str) -> None:
        contract = _contract()
        contract["approved_at"] = approved_at
        with pytest.raises(GncSchemaError, match="contract.approved_at"):
            validate_contract(contract)

    @pytest.mark.parametrize("git_object_id", [GIT_SHA_A, SHA_A])
    def test_contract_accepts_sha1_and_sha256_git_object_ids(self, git_object_id: str) -> None:
        contract = _contract()
        contract["base_sha"] = git_object_id
        contract["policy_sha"] = git_object_id
        normalized = validate_contract(contract)
        assert normalized["base_sha"] == git_object_id
        assert normalized["policy_sha"] == git_object_id

    def test_git_object_id_error_reports_both_supported_lengths(self) -> None:
        contract = _contract()
        contract["base_sha"] = "A" * 40
        with pytest.raises(GncSchemaError, match="lowercase 40- or 64-character Git object ID"):
            validate_contract(contract)

    def test_contract_paths_cannot_overlap(self) -> None:
        contract = _contract()
        contract["forbidden_paths"] = ["src/example.py"]
        with pytest.raises(GncSchemaError, match="overlap"):
            validate_contract(contract)

    def test_contract_paths_are_canonical_and_directory_scopes_cannot_overlap(self) -> None:
        contract = _contract()
        contract["allowed_paths"] = ["src\\governance\\schema.py"]
        assert validate_contract(contract)["allowed_paths"] == ["src/governance/schema.py"]
        contract["forbidden_paths"] = ["src"]
        with pytest.raises(GncSchemaError, match="overlap"):
            validate_contract(contract)

    def test_contract_paths_normalize_dot_segments_and_detect_equivalence(self) -> None:
        contract = _contract()
        contract["allowed_paths"] = ["src/./example.py"]
        assert validate_contract(contract)["allowed_paths"] == ["src/example.py"]
        contract["allowed_paths"] = ["src/example.py", "src/./example.py"]
        with pytest.raises(GncSchemaError, match="equivalent paths"):
            validate_contract(contract)

    def test_required_evidence_uses_stable_identifiers(self) -> None:
        contract = _contract()
        contract["required_evidence"] = ["Pytest report"]
        with pytest.raises(GncSchemaError, match="stable lowercase identifier"):
            validate_contract(contract)

    @pytest.mark.parametrize("path", ["C:/outside/file.py", "C:\\outside\\file.py", "//server/share/file.py"])
    def test_contract_rejects_drive_qualified_and_unc_paths(self, path: str) -> None:
        contract = _contract()
        contract["allowed_paths"] = [path]
        with pytest.raises(GncSchemaError, match="repository-relative"):
            validate_contract(contract)

    def test_review_run_binds_context_digest(self) -> None:
        contract = validate_contract(_contract())
        analyzed_blobs = {"src/example.py": SHA_B}
        digest = canonical_hash([{"path": "src/example.py", "blob_sha": SHA_B}])
        record = validate_record(_review_run(canonical_hash(contract), digest, analyzed_blobs))
        assert record["context_digest"] == digest

    def test_review_run_rejects_unbound_context_digest(self) -> None:
        contract = validate_contract(_contract())
        run = _review_run(canonical_hash(contract), SHA_A, {"src/example.py": SHA_B})
        with pytest.raises(GncSchemaError, match="canonical analyzed_blobs"):
            validate_record(run)

    @pytest.mark.parametrize("path", ["/outside.py", "../outside.py", "C:/outside.py", "//server/share.py"])
    def test_review_run_rejects_unsafe_analyzed_blob_paths(self, path: str) -> None:
        contract_hash = canonical_hash(validate_contract(_contract()))
        run = _review_run(contract_hash, SHA_A, {path: SHA_B})
        with pytest.raises(GncSchemaError, match="repository-relative") as exc_info:
            validate_record(run)
        assert repr(path) in str(exc_info.value)

    @pytest.mark.parametrize("path", ["src\\example.py", "src/./example.py"])
    def test_review_run_canonicalizes_analyzed_blob_paths_before_hashing(self, path: str) -> None:
        contract_hash = canonical_hash(validate_contract(_contract()))
        digest = canonical_hash([{"path": "src/example.py", "blob_sha": SHA_B}])
        record = validate_record(_review_run(contract_hash, digest, {path: SHA_B}))
        assert record["analyzed_blobs"] == {"src/example.py": SHA_B}

    def test_review_run_rejects_equivalent_analyzed_blob_paths(self) -> None:
        contract_hash = canonical_hash(validate_contract(_contract()))
        blobs = {"src/example.py": SHA_B, "src/./example.py": SHA_B}
        run = _review_run(contract_hash, SHA_A, blobs)
        with pytest.raises(GncSchemaError, match="equivalent repository paths"):
            validate_record(run)

    def test_review_run_accepts_sha1_git_references_but_requires_sha256_canonical_hashes(self) -> None:
        contract_input = _contract()
        contract_input["base_sha"] = GIT_SHA_A
        contract_input["policy_sha"] = GIT_SHA_B
        contract = validate_contract(contract_input)
        blobs = {"src/example.py": GIT_SHA_B}
        digest = canonical_hash([{"path": "src/example.py", "blob_sha": GIT_SHA_B}])
        run = _review_run(canonical_hash(contract), digest, blobs)
        run.update({"head_sha": GIT_SHA_A, "merge_base_sha": GIT_SHA_B, "policy_sha": GIT_SHA_B})
        assert validate_record(run)["head_sha"] == GIT_SHA_A

        run["contract_hash"] = GIT_SHA_A
        with pytest.raises(GncSchemaError, match="lowercase 64-character SHA-256 digest"):
            validate_record(run)


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
            "run_ref": "ci/pytest",
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
                    "run_ref": "ci/pytest",
                }
            )

    def test_evidence_requires_execution_provenance(self) -> None:
        evidence = {
            "record_type": "evidence",
            "evidence_id": "evidence.pytest",
            "requirement_id": "pytest",
            "head_sha": SHA_A,
            "target": "linux",
            "state": "executed",
            "result": "pass",
        }
        with pytest.raises(GncSchemaError, match="missing required fields: run_ref"):
            validate_record(evidence)

    def test_evidence_run_ref_rejects_the_review_run_namespace(self) -> None:
        evidence = {
            "record_type": "evidence",
            "evidence_id": "evidence.pytest",
            "requirement_id": "pytest",
            "head_sha": SHA_A,
            "target": "linux",
            "state": "executed",
            "result": "pass",
            "run_ref": "run.unrelated",
        }
        with pytest.raises(GncSchemaError, match=r"evidence\.run_ref.*not a GNC review-run ID"):
            validate_record(evidence)
        with pytest.raises(GncSchemaError, match=r"evidence\.run_ref.*not a GNC review-run ID"):
            evidence_satisfies(evidence, head_sha=SHA_A, target="linux")

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
        base = _finding(state="duplicate_of")
        with pytest.raises(GncSchemaError, match="duplicate_of"):
            validate_record(base)
        with pytest.raises(GncSchemaError, match="finding.duplicate_of"):
            validate_record(dict(base, duplicate_of=None))
        duplicate = validate_record(dict(base, duplicate_of="finding.original"))
        recurrence = validate_record(dict(base, state="reopened_as_recurrence", finding_id="finding.recurrence"))
        assert duplicate["state"] == "duplicate_of"
        assert recurrence["state"] == "reopened_as_recurrence"

    def test_non_duplicate_finding_rejects_an_explicit_null_duplicate_target(self) -> None:
        finding = _finding(duplicate_of=None)
        with pytest.raises(GncSchemaError, match=r"finding\.duplicate_of.*only valid"):
            validate_record(finding)

    def test_blocking_basis_requires_auditable_linkage(self) -> None:
        finding = _finding(finding_id="finding.model", origin="model", blocking_basis="deterministic_rule")
        with pytest.raises(GncSchemaError, match="blocking_rule_id"):
            validate_record(finding)
        linked = validate_record(dict(finding, blocking_rule_id="scope.allowlist"))
        assert linked["blocking_rule_id"] == "scope.allowlist"
        confirmed = validate_record(dict(finding, blocking_basis="human_confirmed", confirmed_by="maintainer"))
        assert confirmed["confirmed_by"] == "maintainer"

    @pytest.mark.parametrize(
        "linkage",
        [
            {"blocking_rule_id": "scope.allowlist"},
            {"blocking_basis": None, "confirmed_by": "maintainer"},
            {
                "blocking_basis": "human_confirmed",
                "confirmed_by": "maintainer",
                "blocking_rule_id": "scope.allowlist",
            },
            {
                "blocking_basis": "deterministic_rule",
                "blocking_rule_id": "scope.allowlist",
                "confirmed_by": "maintainer",
            },
        ],
    )
    def test_blocking_linkage_fields_require_their_matching_basis(self, linkage: dict[str, object]) -> None:
        finding = _finding(**linkage)
        with pytest.raises(GncSchemaError, match="blocking_rule_id|confirmed_by"):
            validate_record(finding)

    @pytest.mark.parametrize("origin,basis", [("deterministic", "unknown"), ("model", ["deterministic_rule"])])
    def test_blocking_basis_rejects_every_unsupported_value(self, origin: str, basis: object) -> None:
        finding = _finding(finding_id="finding.invalid-basis", origin=origin, blocking_basis=basis)
        with pytest.raises(GncSchemaError, match="finding.blocking_basis"):
            validate_record(finding)

    def test_waiver_binds_actor_scope_head_contract_and_expiry(self) -> None:
        waiver = validate_record(_waiver(), as_of="2026-08-22T00:00:00Z")
        assert waiver["scope"] == "src/example.py"

    @pytest.mark.parametrize("expires_at", ["not-a-date", "2026-08-23T00:00:00"])
    def test_waiver_expiry_must_be_timezone_aware_iso_8601(self, expires_at: str) -> None:
        waiver = _waiver(expires_at=expires_at)
        with pytest.raises(GncSchemaError, match="waiver.expires_at"):
            validate_record(waiver, as_of="2026-08-22T00:00:00Z")

    def test_waiver_requires_explicit_as_of_and_rejects_expired_records(self) -> None:
        waiver = _waiver()
        with pytest.raises(GncSchemaError, match="record.as_of"):
            validate_record(waiver)
        expired_waiver = _waiver()
        with pytest.raises(GncSchemaError, match="waiver is expired"):
            validate_record(expired_waiver, as_of="2026-08-23T00:00:00Z")


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
        raw = _replay_fixture()
        raw["secret"] = {"synthetic": True}
        with pytest.raises(GncSchemaError, match="forbidden"):
            validate_replay_fixture(raw)

    def test_replay_rejects_github_fine_grained_pat_text(self) -> None:
        raw = _replay_fixture()
        raw["source_refs"].append("_".join(("github", "pat", "example-replay-token")))
        with pytest.raises(GncSchemaError, match="secret-like"):
            validate_replay_fixture(raw)

    def test_replay_rejects_every_documented_slack_token_family(self) -> None:
        raw = _replay_fixture()
        raw["source_refs"].append("xoxc-replay-token")
        with pytest.raises(GncSchemaError, match="secret-like"):
            validate_replay_fixture(raw)

    @pytest.mark.parametrize("key", [" secret ", "PATCH "])
    def test_replay_forbidden_keys_ignore_case_and_surrounding_whitespace(self, key: str) -> None:
        raw = _replay_fixture()
        raw[key] = "redacted"
        with pytest.raises(GncSchemaError, match="forbidden"):
            validate_replay_fixture(raw)

    def test_replay_rejects_non_string_object_keys(self) -> None:
        raw = _replay_fixture()
        raw[1] = "invalid"
        with pytest.raises(GncSchemaError, match="object keys must be strings"):
            validate_replay_fixture(raw)

    def test_replay_rejects_floats_in_ignored_nested_metadata(self) -> None:
        raw = _replay_fixture()
        raw["metadata"] = {"synthetic_float": 0.1}
        with pytest.raises(GncSchemaError, match="floating-point values are forbidden"):
            validate_replay_fixture(raw)

    @pytest.mark.parametrize("invalid_value", [{"not", "json"}, b"not-json", object()])
    def test_replay_rejects_non_json_values_in_ignored_nested_metadata(self, invalid_value: object) -> None:
        raw = _replay_fixture()
        raw["metadata"] = {"invalid_value": invalid_value}
        with pytest.raises(GncSchemaError, match="unsupported JSON value type"):
            validate_replay_fixture(raw)

    @pytest.mark.parametrize("field", ["evidence", "findings"])
    def test_replay_record_collections_must_be_lists(self, field: str) -> None:
        raw = _replay_fixture()
        raw[field] = {"not": "a list"}
        with pytest.raises(GncSchemaError, match=rf"fixture\.{field}: must be a list"):
            validate_replay_fixture(raw)

    def test_replay_operational_entries_require_record_type(self) -> None:
        review_fixture = _replay_fixture()
        review_fixture["review_run"].pop("record_type")
        with pytest.raises(GncSchemaError, match=r"fixture\.review_run: missing required fields: record_type"):
            validate_replay_fixture(review_fixture)
        finding_fixture = _replay_fixture()
        finding_fixture["findings"][0].pop("record_type")
        with pytest.raises(GncSchemaError, match="missing required fields: record_type"):
            validate_replay_fixture(finding_fixture)
        evidence_fixture = json.loads((FIXTURE_ROOT / "grac-review-and-evidence-gap.json").read_text(encoding="utf-8"))
        evidence_fixture["evidence"][0]["record_type"] = "finding"
        with pytest.raises(GncSchemaError, match="must equal 'evidence'"):
            validate_replay_fixture(evidence_fixture)

    @pytest.mark.parametrize(
        "record_path,error_path",
        [
            (("review_run",), r"fixture\.review_run\.record_type"),
            (("findings", 0), r"fixture\.findings\[0\]\.record_type"),
            (("evidence", 0), r"fixture\.evidence\[0\]\.record_type"),
        ],
    )
    def test_replay_operational_record_types_must_be_strings(
        self, record_path: tuple[str | int, ...], error_path: str
    ) -> None:
        raw = json.loads((FIXTURE_ROOT / "grac-review-and-evidence-gap.json").read_text(encoding="utf-8"))
        record = raw[record_path[0]]
        if len(record_path) == 2:
            record = record[record_path[1]]
        record["record_type"] = ["not", "a", "string"]
        with pytest.raises(GncSchemaError, match=rf"{error_path}: must be a string"):
            validate_replay_fixture(raw)

    def test_replay_record_errors_preserve_collection_index(self) -> None:
        raw = json.loads((FIXTURE_ROOT / "grac-review-and-evidence-gap.json").read_text(encoding="utf-8"))
        raw["evidence"][0].pop("requirement_id")
        with pytest.raises(GncSchemaError, match=r"fixture\.evidence\[0\]: missing required fields: requirement_id"):
            validate_replay_fixture(raw)

        raw = json.loads((FIXTURE_ROOT / "grac-review-and-evidence-gap.json").read_text(encoding="utf-8"))
        raw["findings"][0].pop("rule_id")
        with pytest.raises(GncSchemaError, match=r"fixture\.findings\[0\]: missing required fields: rule_id"):
            validate_replay_fixture(raw)

    def test_expected_finding_order_is_part_of_golden_verdict(self) -> None:
        raw = _replay_fixture()
        raw["expected"]["finding_ids"] = []
        with pytest.raises(GncSchemaError, match="exactly match"):
            validate_replay_fixture(raw)

    def test_expected_finding_ids_must_be_stable_identifiers(self) -> None:
        raw = _replay_fixture()
        raw["expected"]["finding_ids"][0] = "Not a stable identifier"
        with pytest.raises(GncSchemaError, match=r"fixture\.expected\.finding_ids\[0\].*stable lowercase identifier"):
            validate_replay_fixture(raw)

    @pytest.mark.parametrize("field", ["finding_ids", "verdict"])
    def test_expected_requires_both_golden_fields(self, field: str) -> None:
        raw = _replay_fixture()
        raw["expected"].pop(field)
        with pytest.raises(GncSchemaError, match=rf"fixture\.expected: missing required fields: {field}"):
            validate_replay_fixture(raw)

    def test_expected_verdict_must_match_recorded_review_run(self) -> None:
        raw = json.loads((FIXTURE_ROOT / "grac-durable-scope-gap.json").read_text(encoding="utf-8"))
        raw["expected"]["verdict"] = "pass"
        with pytest.raises(GncSchemaError, match="review_run.verdict"):
            validate_replay_fixture(raw)

    def test_replay_run_policy_must_match_contract(self) -> None:
        raw = _replay_fixture()
        raw["review_run"]["policy_sha"] = SHA_A
        with pytest.raises(GncSchemaError, match="contract.policy_sha"):
            validate_replay_fixture(raw)

    def test_replay_run_merge_base_must_match_contract(self) -> None:
        raw = _replay_fixture()
        raw["review_run"]["merge_base_sha"] = SHA_B
        with pytest.raises(GncSchemaError, match="contract.base_sha"):
            validate_replay_fixture(raw)

    def test_replay_findings_must_bind_to_run_head_and_contract_rule(self) -> None:
        raw = _replay_fixture()
        raw["findings"][0]["head_sha"] = SHA_A
        with pytest.raises(GncSchemaError, match="review_run.head_sha"):
            validate_replay_fixture(raw)
        raw["findings"][0]["head_sha"] = raw["review_run"]["head_sha"]
        raw["findings"][0]["rule_id"] = "missing.rule"
        raw["findings"][0]["blocking_rule_id"] = "missing.rule"
        with pytest.raises(GncSchemaError, match="does not exist"):
            validate_replay_fixture(raw)

    def test_replay_blockers_require_an_eligible_contract_rule(self) -> None:
        raw = _replay_fixture()
        raw["contract"]["rules"].append(
            {"rule_id": "style.preference", "type": "preferred_pattern", "statement": "Prefer a small diff."}
        )
        raw["review_run"]["contract_hash"] = canonical_hash(validate_contract(raw["contract"]))
        raw["findings"][0]["rule_id"] = "style.preference"
        raw["findings"][0]["blocking_rule_id"] = "style.preference"
        with pytest.raises(GncSchemaError, match="not blocking-eligible"):
            validate_replay_fixture(raw)

    def test_replay_evidence_requires_contract_and_state_consistent_bindings(self) -> None:
        path = FIXTURE_ROOT / "grac-review-and-evidence-gap.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["evidence"][0]["requirement_id"] = "unrelated"
        with pytest.raises(GncSchemaError, match="not required"):
            validate_replay_fixture(raw)
        raw["evidence"][0]["requirement_id"] = "postgresql"
        raw["evidence"][0]["target"] = raw["review_run"]["target"]
        with pytest.raises(GncSchemaError, match="wrong_target"):
            validate_replay_fixture(raw)

    def test_replay_evidence_run_ref_requires_a_declared_execution_source(self) -> None:
        raw = _replay_fixture()
        raw["evidence"][0]["run_ref"] = "ci/foreign"
        with pytest.raises(GncSchemaError, match=r"fixture\.evidence\[0\]\.run_ref.*no matching execution source"):
            validate_replay_fixture(raw)

    def test_replay_evidence_run_ref_rejects_the_review_run_namespace(self) -> None:
        raw = _replay_fixture()
        raw["evidence"][0]["run_ref"] = "run.unrelated"
        raw["source_refs"].append("execution:run.unrelated")
        with pytest.raises(GncSchemaError, match=r"fixture\.evidence\[0\]\.run_ref.*not a GNC review-run ID"):
            validate_replay_fixture(raw)

    def test_replay_stale_evidence_must_differ_only_by_head(self) -> None:
        path = FIXTURE_ROOT / "grac-durable-scope-gap.json"

        matching_head = json.loads(path.read_text(encoding="utf-8"))
        matching_head["evidence"][0]["head_sha"] = matching_head["review_run"]["head_sha"]
        with pytest.raises(GncSchemaError, match=r"fixture\.evidence\[0\].*stale_sha"):
            validate_replay_fixture(matching_head)

        wrong_target = json.loads(path.read_text(encoding="utf-8"))
        wrong_target["evidence"][0]["target"] = "another-target"
        with pytest.raises(GncSchemaError, match=r"fixture\.evidence\[0\].*stale_sha"):
            validate_replay_fixture(wrong_target)

    @pytest.mark.parametrize(
        "fixture_name",
        ["grac-durable-scope-gap.json", "grac-review-and-evidence-gap.json"],
    )
    def test_replay_preserves_non_current_evidence_as_non_satisfying_historical_fact(self, fixture_name: str) -> None:
        raw = json.loads((FIXTURE_ROOT / fixture_name).read_text(encoding="utf-8"))
        normalized = validate_replay_fixture(raw)
        evidence = normalized["evidence"][0]
        run = normalized["review_run"]
        assert evidence["state"] in {"stale_sha", "wrong_target"}
        assert not evidence_satisfies(evidence, head_sha=run["head_sha"], target=run["target"])
