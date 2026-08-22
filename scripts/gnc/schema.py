"""Deterministic, offline schemas for GNC Phase 1.

This module deliberately has no network, subprocess, or repository-write path.
It validates JSON-compatible records and returns normalized copies.
"""

from __future__ import annotations

import hashlib
import json
import re
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = 1
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
_SECRET_TEXT = re.compile(
    r"-----BEGIN [A-Z ]+PRIVATE KEY-----|\b(?:gh[opusr]_|sk_live_|xox[baprs]-)[A-Za-z0-9_-]+",
    re.IGNORECASE,
)
_FORBIDDEN_REPLAY_KEYS = {
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


class GncSchemaError(ValueError):
    """A field-specific GNC schema validation failure."""


class RuleType(str, Enum):
    """Contract rule classification and blocking eligibility."""

    MANDATORY_INVARIANT = "mandatory_invariant"
    FIXED_DECISION = "fixed_decision"
    PREFERRED_PATTERN = "preferred_pattern"
    EXAMPLE = "example"

    @property
    def may_block(self) -> bool:
        """Return whether this rule type may be a deterministic blocker."""
        return self in {self.MANDATORY_INVARIANT, self.FIXED_DECISION}


class EvidenceState(str, Enum):
    """Execution/applicability state for one evidence record."""

    EXECUTED = "executed"
    SKIPPED = "skipped"
    CANCELED = "canceled"
    UNAVAILABLE = "unavailable"
    STALE_SHA = "stale_sha"
    WRONG_TARGET = "wrong_target"


class FindingState(str, Enum):
    """Durable finding lifecycle states."""

    OPEN = "open"
    RESOLVED = "resolved"
    DEFERRED_OUT_OF_SCOPE = "deferred_out_of_scope"
    REJECTED_SPECULATIVE = "rejected_speculative"
    DUPLICATE_OF = "duplicate_of"
    WAIVED = "waived"
    REOPENED_AS_RECURRENCE = "reopened_as_recurrence"


def _error(field: str, message: str) -> GncSchemaError:
    return GncSchemaError(f"{field}: {message}")


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _error(field, "must be an object")
    return value


def _string(value: Any, field: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str):
        raise _error(field, "must be a string")
    if nonempty and not value.strip():
        raise _error(field, "must be a non-empty string")
    return value.strip() if nonempty else value


def _integer(value: Any, field: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _error(field, f"must be an integer >= {minimum}")
    if value < minimum:
        raise _error(field, f"must be an integer >= {minimum}")
    return value


def _sha(value: Any, field: str) -> str:
    text = _string(value, field)
    if not _SHA256.fullmatch(text):
        raise _error(field, "must be a lowercase 64-character SHA-256/commit digest")
    return text


def _identifier(value: Any, field: str) -> str:
    text = _string(value, field)
    if not _IDENTIFIER.fullmatch(text):
        raise _error(field, "must be a stable lowercase identifier")
    return text


def _string_list(value: Any, field: str, *, nonempty: bool = False) -> list[str]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise _error(field, "must be a list of strings")
    result = [_string(item, f"{field}[{index}]") for index, item in enumerate(value)]
    if nonempty and not result:
        raise _error(field, "must not be empty")
    if len(result) != len(set(result)):
        raise _error(field, "must not contain duplicates")
    return result


def _repo_paths(value: Any, field: str) -> list[str]:
    paths = _string_list(value, field)
    for index, path in enumerate(paths):
        normalized = path.replace("\\", "/")
        pure = PurePosixPath(normalized)
        is_drive_qualified = re.match(r"^[A-Za-z]:", normalized) is not None
        is_unc = normalized.startswith("//")
        if pure.is_absolute() or is_drive_qualified or is_unc:
            raise _error(f"{field}[{index}]", "must be a repository-relative path, not an absolute path")
        if ".." in pure.parts or not pure.parts:
            raise _error(f"{field}[{index}]", "must be a safe repository-relative path")
    return paths


def _require_keys(data: Mapping[str, Any], required: set[str], field: str) -> None:
    missing = sorted(required - set(data))
    if missing:
        raise _error(field, f"missing required fields: {', '.join(missing)}")


def _json_mapping(value: Mapping[Any, Any], field: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise _error(field, "object keys must be strings")
        result[key] = _json_value(item, f"{field}.{key}")
    return result


def _json_sequence(value: Sequence[Any], field: str) -> list[Any]:
    return [_json_value(item, f"{field}[{index}]") for index, item in enumerate(value)]


def _json_value(value: Any, field: str) -> Any:
    """Normalize JSON data and reject ambiguous/non-canonical types."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        raise _error(field, "floating-point values are not canonical")
    if isinstance(value, Mapping):
        return _json_mapping(value, field)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return _json_sequence(value, field)
    raise _error(field, f"unsupported canonical JSON type: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    """Return stable UTF-8 JSON independent of mapping order and whitespace."""
    normalized = _json_value(value, "record")
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_hash(value: Any) -> str:
    """Return the SHA-256 digest of canonical JSON."""
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _validate_rule(value: Any, index: int) -> dict[str, Any]:
    field = f"contract.rules[{index}]"
    data = _mapping(value, field)
    _require_keys(data, {"rule_id", "type", "statement"}, field)
    try:
        rule_type = RuleType(_string(data["type"], f"{field}.type"))
    except ValueError as exc:
        raise _error(f"{field}.type", "is not a supported rule type") from exc
    return {
        "rule_id": _identifier(data["rule_id"], f"{field}.rule_id"),
        "type": rule_type.value,
        "statement": _string(data["statement"], f"{field}.statement"),
        "blocking_eligible": rule_type.may_block,
    }


def _validate_rules(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise _error("contract.rules", "must be a list")
    rules = [_validate_rule(rule, index) for index, rule in enumerate(value)]
    if not rules:
        raise _error("contract.rules", "must not be empty")
    rule_ids = [rule["rule_id"] for rule in rules]
    if len(rule_ids) != len(set(rule_ids)):
        raise _error("contract.rules", "rule_id values must be unique")
    return rules


def _validate_contract_paths(data: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    allowed_paths = _repo_paths(data["allowed_paths"], "contract.allowed_paths")
    forbidden_paths = _repo_paths(data["forbidden_paths"], "contract.forbidden_paths")
    overlap = set(allowed_paths) & set(forbidden_paths)
    if overlap:
        raise _error("contract.paths", f"allowed and forbidden paths overlap: {', '.join(sorted(overlap))}")
    return allowed_paths, forbidden_paths


def _add_amendment_fields(normalized: dict[str, Any], data: Mapping[str, Any], version: int) -> None:
    if version == 1:
        return
    normalized["previous_contract_hash"] = _sha(data.get("previous_contract_hash"), "contract.previous_contract_hash")
    normalized["amendment_reason"] = _string(data.get("amendment_reason"), "contract.amendment_reason")


def validate_contract(value: Any) -> dict[str, Any]:
    """Validate and normalize one frozen PR implementation contract."""
    data = _mapping(value, "contract")
    required = {
        "schema_version",
        "contract_id",
        "version",
        "parent_issue",
        "objective",
        "base_sha",
        "policy_sha",
        "risk_class",
        "allowed_paths",
        "forbidden_paths",
        "rules",
        "required_evidence",
        "merge_criteria",
        "stop_conditions",
        "approved_by",
        "approved_at",
    }
    _require_keys(data, required, "contract")
    version = _integer(data["version"], "contract.version")
    if data["schema_version"] != SCHEMA_VERSION:
        raise _error("contract.schema_version", f"must equal {SCHEMA_VERSION}")
    rules = _validate_rules(data["rules"])
    allowed_paths, forbidden_paths = _validate_contract_paths(data)
    normalized = {
        "schema_version": SCHEMA_VERSION,
        "contract_id": _identifier(data["contract_id"], "contract.contract_id"),
        "version": version,
        "parent_issue": _integer(data["parent_issue"], "contract.parent_issue"),
        "objective": _string(data["objective"], "contract.objective"),
        "base_sha": _sha(data["base_sha"], "contract.base_sha"),
        "policy_sha": _sha(data["policy_sha"], "contract.policy_sha"),
        "risk_class": _string(data["risk_class"], "contract.risk_class"),
        "allowed_paths": allowed_paths,
        "forbidden_paths": forbidden_paths,
        "rules": rules,
        "required_evidence": _string_list(data["required_evidence"], "contract.required_evidence", nonempty=True),
        "merge_criteria": _string_list(data["merge_criteria"], "contract.merge_criteria", nonempty=True),
        "stop_conditions": _string_list(data["stop_conditions"], "contract.stop_conditions", nonempty=True),
        "approved_by": _string(data["approved_by"], "contract.approved_by"),
        "approved_at": _string(data["approved_at"], "contract.approved_at"),
    }
    _add_amendment_fields(normalized, data, version)
    return normalized


def finding_fingerprint(*, rule_id: str, subject: str, failure_mode: str, expected_outcome: str) -> str:
    """Hash stable finding semantics, excluding reviewer wording."""
    components = {
        "rule_id": _identifier(rule_id, "finding.rule_id"),
        "subject": " ".join(_string(subject, "finding.subject").casefold().split()),
        "failure_mode": " ".join(_string(failure_mode, "finding.failure_mode").casefold().split()),
        "expected_outcome": " ".join(_string(expected_outcome, "finding.expected_outcome").casefold().split()),
    }
    return canonical_hash(components)


def _validate_evidence(data: Mapping[str, Any]) -> dict[str, Any]:
    field = "evidence"
    _require_keys(data, {"evidence_id", "requirement_id", "head_sha", "target", "state", "result"}, field)
    try:
        state = EvidenceState(_string(data["state"], f"{field}.state"))
    except ValueError as exc:
        raise _error(f"{field}.state", "is not a supported evidence state") from exc
    result = _string(data["result"], f"{field}.result")
    if state is not EvidenceState.EXECUTED and result == "pass":
        raise _error(f"{field}.result", "non-executed evidence cannot pass")
    return {
        "record_type": "evidence",
        "evidence_id": _identifier(data["evidence_id"], f"{field}.evidence_id"),
        "requirement_id": _identifier(data["requirement_id"], f"{field}.requirement_id"),
        "head_sha": _sha(data["head_sha"], f"{field}.head_sha"),
        "target": _string(data["target"], f"{field}.target"),
        "state": state.value,
        "result": result,
        "run_ref": _string(data.get("run_ref", "local"), f"{field}.run_ref"),
    }


def evidence_satisfies(value: Any, *, head_sha: str, target: str) -> bool:
    """Return whether evidence is an executed pass for the exact head/target."""
    record = _validate_evidence(_mapping(value, "evidence"))
    return (
        record["state"] == EvidenceState.EXECUTED.value
        and record["result"] == "pass"
        and record["head_sha"] == _sha(head_sha, "head_sha")
        and record["target"] == _string(target, "target")
    )


def _finding_state(data: Mapping[str, Any]) -> FindingState:
    try:
        return FindingState(_string(data["state"], "finding.state"))
    except ValueError as exc:
        raise _error("finding.state", "is not a supported finding state") from exc


def _validate_duplicate_relation(state: FindingState, duplicate_of: Any) -> None:
    if state is FindingState.DUPLICATE_OF and not duplicate_of:
        raise _error("finding.duplicate_of", "is required for duplicate_of state")
    if state is not FindingState.DUPLICATE_OF and duplicate_of is not None:
        raise _error("finding.duplicate_of", "is only valid for duplicate_of state")


def _validate_blocking_basis(origin: str, blocking_basis: Any) -> None:
    allowed = {None, "human_confirmed", "deterministic_rule"}
    if origin == "model" and blocking_basis not in allowed:
        raise _error("finding.blocking_basis", "model findings cannot block without deterministic or human basis")


def _validate_finding(data: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "finding_id",
        "rule_id",
        "subject",
        "failure_mode",
        "expected_outcome",
        "origin",
        "state",
        "head_sha",
    }
    _require_keys(data, required, "finding")
    state = _finding_state(data)
    duplicate_of = data.get("duplicate_of")
    _validate_duplicate_relation(state, duplicate_of)
    origin = _string(data["origin"], "finding.origin")
    blocking_basis = data.get("blocking_basis")
    _validate_blocking_basis(origin, blocking_basis)
    result = {
        "record_type": "finding",
        "finding_id": _identifier(data["finding_id"], "finding.finding_id"),
        "rule_id": _identifier(data["rule_id"], "finding.rule_id"),
        "subject": _string(data["subject"], "finding.subject"),
        "failure_mode": _string(data["failure_mode"], "finding.failure_mode"),
        "expected_outcome": _string(data["expected_outcome"], "finding.expected_outcome"),
        "origin": origin,
        "state": state.value,
        "head_sha": _sha(data["head_sha"], "finding.head_sha"),
    }
    result["fingerprint"] = finding_fingerprint(
        rule_id=result["rule_id"],
        subject=result["subject"],
        failure_mode=result["failure_mode"],
        expected_outcome=result["expected_outcome"],
    )
    if duplicate_of is not None:
        result["duplicate_of"] = _identifier(duplicate_of, "finding.duplicate_of")
    if blocking_basis is not None:
        result["blocking_basis"] = _string(blocking_basis, "finding.blocking_basis")
    return result


def _validate_review_run(data: Mapping[str, Any]) -> dict[str, Any]:
    field = "review_run"
    required = {
        "run_id",
        "head_sha",
        "merge_base_sha",
        "contract_hash",
        "policy_sha",
        "context_digest",
        "evaluator_version",
        "target",
        "review_mode",
        "verdict",
        "analyzed_blobs",
    }
    _require_keys(data, required, field)
    blobs = _mapping(data["analyzed_blobs"], f"{field}.analyzed_blobs")
    return {
        "record_type": "review_run",
        "run_id": _identifier(data["run_id"], f"{field}.run_id"),
        "head_sha": _sha(data["head_sha"], f"{field}.head_sha"),
        "merge_base_sha": _sha(data["merge_base_sha"], f"{field}.merge_base_sha"),
        "contract_hash": _sha(data["contract_hash"], f"{field}.contract_hash"),
        "policy_sha": _sha(data["policy_sha"], f"{field}.policy_sha"),
        "context_digest": _sha(data["context_digest"], f"{field}.context_digest"),
        "evaluator_version": _string(data["evaluator_version"], f"{field}.evaluator_version"),
        "target": _string(data["target"], f"{field}.target"),
        "review_mode": _string(data["review_mode"], f"{field}.review_mode"),
        "verdict": _string(data["verdict"], f"{field}.verdict"),
        "analyzed_blobs": {path: _sha(digest, f"{field}.analyzed_blobs.{path}") for path, digest in blobs.items()},
    }


def _validate_waiver(data: Mapping[str, Any]) -> dict[str, Any]:
    field = "waiver"
    required = {"waiver_id", "finding_id", "actor", "reason", "scope", "head_sha", "contract_hash", "expires_at"}
    _require_keys(data, required, field)
    return {
        "record_type": "waiver",
        "waiver_id": _identifier(data["waiver_id"], f"{field}.waiver_id"),
        "finding_id": _identifier(data["finding_id"], f"{field}.finding_id"),
        "actor": _string(data["actor"], f"{field}.actor"),
        "reason": _string(data["reason"], f"{field}.reason"),
        "scope": _string(data["scope"], f"{field}.scope"),
        "head_sha": _sha(data["head_sha"], f"{field}.head_sha"),
        "contract_hash": _sha(data["contract_hash"], f"{field}.contract_hash"),
        "expires_at": _string(data["expires_at"], f"{field}.expires_at"),
    }


def validate_record(value: Any) -> dict[str, Any]:
    """Validate a review-run, evidence, finding, waiver, or contract record."""
    data = _mapping(value, "record")
    record_type = _string(data.get("record_type"), "record.record_type")
    if record_type == "contract_version":
        contract = validate_contract(data.get("contract"))
        return {"record_type": record_type, "contract": contract, "contract_hash": canonical_hash(contract)}
    validators = {
        "review_run": _validate_review_run,
        "evidence": _validate_evidence,
        "finding": _validate_finding,
        "waiver": _validate_waiver,
    }
    try:
        return validators[record_type](data)
    except KeyError as exc:
        raise _error("record.record_type", f"unsupported type {record_type!r}") from exc


def _assert_sanitized_mapping(value: Mapping[Any, Any], field: str) -> None:
    for key, item in value.items():
        normalized_key = str(key).casefold()
        if normalized_key in _FORBIDDEN_REPLAY_KEYS:
            raise _error(f"{field}.{key}", "raw, secret, transcript, or executable content is forbidden")
        _assert_sanitized(item, f"{field}.{key}")


def _assert_sanitized_sequence(value: Sequence[Any], field: str) -> None:
    for index, item in enumerate(value):
        _assert_sanitized(item, f"{field}[{index}]")


def _assert_sanitized(value: Any, field: str = "fixture") -> None:
    if isinstance(value, Mapping):
        _assert_sanitized_mapping(value, field)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        _assert_sanitized_sequence(value, field)
        return
    if isinstance(value, str) and _SECRET_TEXT.search(value):
        raise _error(field, "secret-like material is forbidden")


def validate_replay_fixture(value: Any) -> dict[str, Any]:
    """Validate one sanitized, deterministic historical replay scenario."""
    data = _mapping(value, "fixture")
    _assert_sanitized(data)
    _require_keys(
        data, {"scenario_id", "source_refs", "contract", "review_run", "evidence", "findings", "expected"}, "fixture"
    )
    contract = validate_contract(data["contract"])
    run = _validate_review_run(_mapping(data["review_run"], "fixture.review_run"))
    if run["contract_hash"] != canonical_hash(contract):
        raise _error("fixture.review_run.contract_hash", "does not match the normalized contract")
    evidence = [_validate_evidence(_mapping(item, "fixture.evidence[]")) for item in data["evidence"]]
    findings = [_validate_finding(_mapping(item, "fixture.findings[]")) for item in data["findings"]]
    expected = _mapping(data["expected"], "fixture.expected")
    expected_ids = _string_list(expected.get("finding_ids"), "fixture.expected.finding_ids")
    actual_ids = [finding["finding_id"] for finding in findings]
    if expected_ids != actual_ids:
        raise _error("fixture.expected.finding_ids", "must exactly match findings in stable order")
    return {
        "scenario_id": _identifier(data["scenario_id"], "fixture.scenario_id"),
        "source_refs": _string_list(data["source_refs"], "fixture.source_refs", nonempty=True),
        "contract": contract,
        "review_run": run,
        "evidence": evidence,
        "findings": findings,
        "expected": {
            "verdict": _string(expected.get("verdict"), "fixture.expected.verdict"),
            "finding_ids": expected_ids,
        },
    }
