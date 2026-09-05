"""Static specification checks only; no Phase 3A runtime or adjudication."""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest

from scripts.gnc.schema import (
    GncSchemaError,
    canonical_hash,
    canonical_json_bytes,
    evidence_satisfies,
    finding_fingerprint,
    validate_contract,
    validate_record,
)

ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = ROOT / "tests/fixtures/gnc/shadow/phase3a-cases.json"
EXPECTED_PATH = ROOT / "tests/fixtures/gnc/shadow/phase3a-expected.json"
CONTRACT_PATH = ROOT / "docs/governance/gnc-phase-3a-shadow-contract.json"
METHOD_PATH = ROOT / "docs/governance/gnc-phase-3a-shadow-method.md"
BASE = "165efa4d239737fefad33ca1ecb1db347e6b8414"
# Predeclared normalized identity of the unchanged candidate contract at 7d192ed59.
# This pin detects drift; it is not human freeze acceptance or authority to repin.
CONTRACT_HASH = "20cc780707244455119e89f3fd30d7dd7424f3d925ea50a706acde9023a23ec0"
INPUT_HASH = "47f70d04ebf58cc60936488893890b58eb3b5b26890588365b39a7d281096fc6"
EXPECTED_HASH = "3d8b79a812e023fad51cf1ebfec8b83384b11a66edcbef6a6e401782f46b9205"
PATHS = {
    "docs/governance/gnc-phase-3a-shadow-method.md",
    "docs/governance/gnc-phase-3a-shadow-contract.json",
    "tests/fixtures/gnc/shadow/phase3a-cases.json",
    "tests/fixtures/gnc/shadow/phase3a-expected.json",
    "tests/unit/test_gnc_shadow_contract.py",
}
QUESTIONS = {
    "authority",
    "memory",
    "resolution",
    "identity",
    "waiver",
    "snapshot",
    "context",
    "input",
    "history",
    "measurement",
}
CANDIDATE_KEYS = {
    "candidate_id",
    "source_class",
    "family_id",
    "text",
    "proposed_action",
    "finding_id",
    "abstains",
}


def _unique_object(pairs):
    """Reject duplicate JSON keys before normalization could hide them."""
    result = {}
    for key, value in pairs:
        assert key not in result, f"duplicate JSON key: {key}"
        result[key] = value
    return result


def _bounded_bytes(path: Path) -> bytes:
    """Enforce the static file ceiling before decoding or parsing."""
    with path.open("rb") as stream:
        raw = stream.read(262145)
    assert len(raw) <= 262144
    return raw


def _read(path):
    """Read one bounded static specification without importing application code."""
    raw = _bounded_bytes(path)
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)


def _check_identity(data, digest):
    """Check a predeclared identity, not a runtime-derived expectation."""
    assert canonical_hash(data) == digest


def _check_json_mapping(value: dict[str, Any]) -> None:
    """Check mapping keys and recurse without interpreting stored data."""
    assert all(isinstance(key, str) for key in value)
    for key, item in value.items():
        assert key.strip().casefold() not in {
            "credential",
            "credentials",
            "diff",
            "evidence_body",
            "patch",
            "password",
            "private_key",
            "raw_evidence",
            "review_transcript",
            "script",
            "secret",
            "token",
        }
        _check_json_values(item)


def _check_json_sequence(value: list[Any]) -> None:
    """Check each stored sequence member without altering its order."""
    for item in value:
        _check_json_values(item)


def _check_json_text(value: str) -> None:
    """Check the existing bounded text and secret-pattern assertions."""
    assert len(value.encode("utf-8")) <= 4096
    assert not re.search(
        r"-----BEGIN [A-Z ]+PRIVATE KEY-----|(?<![A-Z0-9])"
        r"(?:github_pat_|gh[opusr]_|sk_live_|xox[a-z0-9]*-)[A-Z0-9_-]+",
        value,
        re.IGNORECASE,
    )


def _check_json_values(value: Any) -> None:
    """Dispatch static canonical-type checks, never runtime adjudication."""
    if isinstance(value, dict):
        _check_json_mapping(value)
    elif isinstance(value, list):
        _check_json_sequence(value)
    elif isinstance(value, str):
        _check_json_text(value)
    else:
        assert value is None or type(value) in (bool, int)


def _case_map(data):
    """Require unique, fully specified case entries without deriving outcomes."""
    cases = data["cases"]
    assert 0 < len(cases) <= data["limits"]["scenarios"]
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert {case["question"] for case in cases} == QUESTIONS
    for case in cases:
        assert set(case) == {"case_id", "question", "input"}
        assert re.fullmatch(r"[a-z0-9._-]+", case["case_id"])
    return {case["case_id"]: case for case in cases}


def test_frozen_contract_and_preparation_authority():
    """Preserve exact scope and distinguish preparation from acceptance."""
    raw = _read(CONTRACT_PATH)
    normalized = validate_contract(raw)
    assert canonical_hash(normalized) == CONTRACT_HASH, "frozen contract identity changed"
    assert normalized["contract_id"] == "gnc.phase3a-shadow-method"
    assert normalized["version"] == 1
    assert normalized["parent_issue"] == 1817
    assert normalized["base_sha"] == normalized["policy_sha"] == BASE
    assert set(normalized["allowed_paths"]) == PATHS
    assert normalized["approved_by"] == "mohavro"
    assert normalized["approved_at"] == "2026-09-05T16:30:22Z"
    assert "preparation approval is not freeze or runtime acceptance" in normalized["objective"]
    rules = {rule["rule_id"]: rule for rule in normalized["rules"]}
    assert len(rules) == 11
    assert INPUT_HASH in rules["method.frozen-identities"]["statement"]
    assert EXPECTED_HASH in rules["method.frozen-identities"]["statement"]
    assert all(rule["type"] in ("mandatory_invariant", "fixed_decision") for rule in rules.values())
    assert validate_contract(normalized) == normalized


def _assert_contract_mutation_rejected(monkeypatch: pytest.MonkeyPatch, altered: dict[str, Any]) -> None:
    """Exercise the real entry test, not just an otherwise unused hash helper."""
    validate_contract(altered)  # Mutation must be schema-valid, not rejected by parsing.
    monkeypatch.setitem(globals(), "_read", lambda path: altered)
    with pytest.raises(AssertionError, match="frozen contract identity changed"):
        test_frozen_contract_and_preparation_authority()


@pytest.mark.parametrize("operation", ["remove", "replace"])
@pytest.mark.parametrize(
    "field,index",
    [
        (field, index)
        for field, count in (
            ("required_evidence", 8),
            ("forbidden_paths", 15),
            ("merge_criteria", 5),
            ("stop_conditions", 5),
        )
        for index in range(count)
    ],
)
def test_contract_control_mutations_are_rejected(
    monkeypatch: pytest.MonkeyPatch, field: str, index: int, operation: str
) -> None:
    """Individually protect every required control, including human and exact-head review."""
    altered = copy.deepcopy(_read(CONTRACT_PATH))
    if operation == "remove":
        del altered[field][index]
    else:
        altered[field][index] += "-optional"
    _assert_contract_mutation_rejected(monkeypatch, altered)


@pytest.mark.parametrize("operation", ["remove", "weaken"])
@pytest.mark.parametrize("index", range(11))
def test_contract_rule_mutations_are_rejected(monkeypatch: pytest.MonkeyPatch, index: int, operation: str) -> None:
    """Reject removal or schema-valid weakening of each frozen rule statement."""
    altered = copy.deepcopy(_read(CONTRACT_PATH))
    if operation == "remove":
        del altered["rules"][index]
    else:
        altered["rules"][index]["statement"] = "This rule is optional."
    _assert_contract_mutation_rejected(monkeypatch, altered)


def test_contract_human_and_exact_head_controls_cannot_both_be_removed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reproduce the confirmed review counterexample against the actual entry test."""
    altered = copy.deepcopy(_read(CONTRACT_PATH))
    altered["required_evidence"].remove("named-human-freeze-review")
    altered["required_evidence"].remove("exact-head-checks")
    _assert_contract_mutation_rejected(monkeypatch, altered)


def test_contract_identity_accepts_formatting_only_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Preserve normalized identity across JSON whitespace and object-key ordering."""
    equivalent = json.loads(json.dumps(_read(CONTRACT_PATH), sort_keys=True, indent=4))
    monkeypatch.setitem(globals(), "_read", lambda path: equivalent)
    test_frozen_contract_and_preparation_authority()


def test_frozen_corpus_identities_bounds_and_question_inventory():
    """Detect any altered/missing corpus instead of regenerating a matching oracle."""
    inputs, expected = _read(INPUT_PATH), _read(EXPECTED_PATH)
    method_text = _bounded_bytes(METHOD_PATH).decode("utf-8")
    _check_identity(inputs, INPUT_HASH)
    _check_identity(expected, EXPECTED_HASH)
    _check_json_values(inputs)
    _check_json_values(expected)
    assert set(inputs) == {"schema_version", "fixture_kind", "limits", "questions", "synthetic_policy", "cases"}
    assert set(inputs["questions"]) == QUESTIONS
    assert inputs["fixture_kind"] == "public-synthetic-static-specification"
    assert inputs["limits"] == {
        "scenarios": 64,
        "snapshots_per_scenario": 8,
        "events_per_scenario": 64,
        "json_bytes": 262144,
        "text_bytes": 4096,
    }
    cases = _case_map(inputs)
    assert len(cases) == 63
    outcomes = expected["expected"]
    assert len(outcomes) == len(cases)
    assert [entry["case_id"] for entry in outcomes] == list(cases)
    for entry in outcomes:
        assert set(entry) in (
            {"case_id", "code", "assessment", "states", "links", "source_history", "rationale"},
            {"case_id", "code", "assessment", "states", "links", "source_history", "rationale", "counts"},
        )
        assert entry["source_history"] == "preserve-all"
        assert entry["assessment"] in {"full", "refused"}
        assert entry["rationale"].strip()
        assert entry["code"] in method_text
        if entry["assessment"] == "refused":
            assert entry["states"] == {}


def _check_input_envelope(value: dict[str, Any]) -> None:
    """Check fixture envelope keys, bounds and absence of oracle fields."""
    assert set(value) == {
        "as_of",
        "snapshots",
        "current_snapshot",
        "events",
        "candidates",
        "applicable_findings",
        "probe",
    }
    assert 1 <= len(value["snapshots"]) <= 8
    assert 1 <= len(value["events"]) <= 64
    assert not {"rationale", "code", "assessment", "states", "links"} & set(value)


def _check_synthetic_snapshots(snapshots: list[dict[str, Any]]) -> None:
    """Keep every fixture snapshot explicitly synthetic and model-free."""
    for snapshot in snapshots:
        assert snapshot["model"] == snapshot["prompt"] == "not-used"
        assert snapshot["repository"] == "synthetic/fardb-review"


def _check_synthetic_candidates(case_id: str, candidates: list[dict[str, Any]]) -> None:
    """Retain the one declared unknown-field probe without weakening other cases."""
    keys = CANDIDATE_KEYS | ({"unexpected"} if case_id == "input.unknown-field" else set())
    for candidate in candidates:
        assert set(candidate) == keys
        assert candidate["source_class"] == "synthetic_candidate"
        assert type(candidate["abstains"]) is bool


def test_static_inputs_and_expected_definitions_are_separate() -> None:
    """Check input envelopes without implementing the future decision procedure."""
    for case in _read(INPUT_PATH)["cases"]:
        value = case["input"]
        _check_input_envelope(value)
        _check_synthetic_snapshots(value["snapshots"])
        _check_synthetic_candidates(case["case_id"], value["candidates"])


def test_negative_probe_recipes_are_bounded_and_not_executed():
    """Validate declared above-limit future probes without constructing a runtime."""
    probes = {
        case["case_id"]: case["input"]["probe"]
        for case in _read(INPUT_PATH)["cases"]
        if case["input"]["probe"] is not None
    }
    assert probes == {
        "input.event-limit": {"kind": "events", "count": 65},
        "input.text-limit": {"kind": "text-bytes", "count": 4097},
        "input.json-limit": {"kind": "input-bytes", "count": 262145},
        "input.snapshot-limit": {"kind": "snapshots", "count": 9},
    }


def test_static_file_byte_limit(tmp_path: Path) -> None:
    """Exercise the actual static reader at the limit and one byte above it."""
    path = tmp_path / "bounded.txt"
    path.write_bytes(b"x" * 262144)
    assert len(_bounded_bytes(path)) == 262144
    path.write_bytes(b"x" * 262145)
    with pytest.raises(AssertionError):
        _bounded_bytes(path)


def test_static_negative_oracle_and_input_mutations_are_detected():
    """Prove static hash checks detect substitutions, not runtime correctness."""
    for path, digest, field in (
        (INPUT_PATH, INPUT_HASH, "fixture_kind"),
        (EXPECTED_PATH, EXPECTED_HASH, "oracle_kind"),
    ):
        altered = copy.deepcopy(_read(path))
        altered[field] = "substituted"
        with pytest.raises(AssertionError):
            _check_identity(altered, digest)
    with pytest.raises(AssertionError):
        _unique_object([("same", 1), ("same", 2)])
    with pytest.raises(GncSchemaError):
        canonical_json_bytes({"floating": 1.5})


def _check_primitive_events(events: list[dict[str, Any]]) -> None:
    """Validate existing finding and evidence records without lifecycle decisions."""
    for event in events:
        if event["event_type"] in {"finding", "evidence"}:
            validate_record(event["record"])


def test_existing_finding_and_evidence_record_compatibility() -> None:
    """Check all stored records against the unchanged landed primitive."""
    cases = _case_map(_read(INPUT_PATH))
    for case in cases.values():
        _check_primitive_events(case["input"]["events"])


def test_existing_evidence_state_compatibility() -> None:
    """Preserve passing evidence and every unsatisfied execution-state contrast."""
    cases = _case_map(_read(INPUT_PATH))
    valid = cases["resolution.valid"]["input"]["events"][1]["record"]
    assert evidence_satisfies(valid, head_sha="1" * 40, target="synthetic-unit")
    for label in ("failed", "skipped", "canceled", "unavailable", "stale_sha", "wrong_target"):
        record = cases[f"evidence.{label}"]["input"]["events"][1]["record"]
        assert not evidence_satisfies(record, head_sha="1" * 40, target="synthetic-unit")


def test_existing_evidence_exact_binding_compatibility() -> None:
    """Keep each executed-pass mismatch isolated to exactly one binding."""
    cases = _case_map(_read(INPUT_PATH))
    valid = cases["resolution.valid"]["input"]["events"][1]["record"]
    for label, field in (("executed-wrong-head", "head_sha"), ("executed-wrong-target", "target")):
        changed_input = copy.deepcopy(cases[f"evidence.{label}"]["input"])
        record = changed_input["events"][1]["record"]
        assert record["state"] == "executed"
        assert record["result"] == "pass"
        assert record[field] != valid[field]
        assert not evidence_satisfies(record, head_sha="1" * 40, target="synthetic-unit")
        # Restoring exactly one binding recovers the entire positive-control input.
        record[field] = valid[field]
        assert changed_input == cases["resolution.valid"]["input"]
        assert evidence_satisfies(record, head_sha="1" * 40, target="synthetic-unit")


def test_existing_finding_fingerprint_compatibility() -> None:
    """Preserve exact-duplicate and distinct-failure-mode fingerprint controls."""
    cases = _case_map(_read(INPUT_PATH))
    first, second = cases["identity.exact-duplicate"]["input"]["events"]
    fields = ("rule_id", "subject", "failure_mode", "expected_outcome")
    assert finding_fingerprint(**{key: first["record"][key] for key in fields}) == finding_fingerprint(
        **{key: second["record"][key] for key in fields}
    )
    different = cases["identity.distinct-mode"]["input"]["events"][1]["record"]
    assert finding_fingerprint(**{key: first["record"][key] for key in fields}) != finding_fingerprint(
        **{key: different[key] for key in fields}
    )


def test_waiver_primitive_does_not_establish_external_authority():
    """Use supplied synthetic time while leaving source trust to the future boundary."""
    cases = _case_map(_read(INPUT_PATH))
    valid = cases["waiver.valid"]["input"]
    validate_record(valid["events"][1]["record"], as_of=valid["as_of"])
    expired = cases["waiver.wrong-expired"]["input"]
    with pytest.raises(GncSchemaError, match="expired"):
        validate_record(expired["events"][1]["record"], as_of=expired["as_of"])
    forged = cases["waiver.forged-actor"]["input"]
    # Structural success is deliberately NOT evidence that the actor was authenticated.
    validate_record(forged["events"][1]["record"], as_of=forged["as_of"])
    assert forged["events"][1]["source_class"] == "synthetic_candidate"


def test_positive_controls_and_measurement_definitions_are_explicit():
    """Protect reviewed controls without computing decisions from the cases."""
    outcomes = {item["case_id"]: item for item in _read(EXPECTED_PATH)["expected"]}
    assert outcomes["resolution.valid"]["states"] == {"f.one": "resolved"}
    assert outcomes["waiver.valid"]["states"] == {"f.one": "waived"}
    assert outcomes["identity.exact-duplicate"]["links"] == [{"from": "f.two", "to": "f.one"}]
    assert outcomes["identity.recurrence"]["states"]["f.two"] == "reopened_as_recurrence"
    assert outcomes["counts.empty-applicable"]["counts"]["defined_denominator"] is False
    assert outcomes["counts.abstention"]["counts"]["abstentions"] == 1
    variants = outcomes["counts.wording-variants"]["counts"]
    assert variants["predictions"] == 2
    assert variants["families"] == 1
