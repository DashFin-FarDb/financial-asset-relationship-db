"""Deterministic, offline schemas for GNC Phase 1.

This module deliberately has no network, subprocess, or repository-write path.
It validates JSON-compatible records and returns normalized copies.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = 1
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_OBJECT_ID = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,127}$")
_SECRET_TEXT = re.compile(
    r"-----BEGIN [A-Z ]+PRIVATE KEY-----|\b(?:github_pat_|gh[opusr]_|sk_live_|xox[a-z0-9]*-)[A-Za-z0-9_-]+",
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


def _sha256(value: Any, field: str) -> str:
    text = _string(value, field)
    if not _SHA256.fullmatch(text):
        raise _error(field, "must be a lowercase 64-character SHA-256 digest")
    return text


def _git_object_id(value: Any, field: str) -> str:
    text = _string(value, field)
    if not _GIT_OBJECT_ID.fullmatch(text):
        raise _error(field, "must be a lowercase 40- or 64-character Git object ID")
    return text


def _timestamp(value: Any, field: str) -> datetime:
    text = _string(value, field)
    normalized = f"{text[:-1]}+00:00" if text.endswith("Z") else text
    try:
        timestamp = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise _error(field, "must be a valid ISO 8601 timestamp") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise _error(field, "must include a timezone offset")
    return timestamp


def _identifier(value: Any, field: str) -> str:
    text = _string(value, field)
    if not _IDENTIFIER.fullmatch(text):
        raise _error(field, "must be a stable lowercase identifier")
    return text


def _string_list(value: Any, field: str, *, nonempty: bool = False) -> list[str]:
    values = _sequence(value, field, description="a list of strings")
    result = [_string(item, f"{field}[{index}]") for index, item in enumerate(values)]
    if nonempty and not result:
        raise _error(field, "must not be empty")
    if len(result) != len(set(result)):
        raise _error(field, "must not contain duplicates")
    return result


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _sequence(value: Any, field: str, *, description: str = "a list") -> Sequence[Any]:
    if not _is_sequence(value):
        raise _error(field, f"must be {description}")
    return value


def _canonical_repo_path(path: str, field: str) -> str:
    normalized = path.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute():
        raise _error(field, "must be a repository-relative path, not an absolute path")
    if re.match(r"^[A-Za-z]:", normalized) is not None:
        raise _error(field, "must be a repository-relative path, not an absolute path")
    if normalized.startswith("//"):
        raise _error(field, "must be a repository-relative path, not an absolute path")
    if ".." in pure.parts or not pure.parts:
        raise _error(field, "must be a safe repository-relative path")
    return pure.as_posix()


def _repo_paths(value: Any, field: str) -> list[str]:
    paths = _string_list(value, field)
    canonical = [_canonical_repo_path(path, f"{field}[{index}]") for index, path in enumerate(paths)]
    if len(canonical) != len(set(canonical)):
        raise _error(field, "must not contain equivalent paths")
    return canonical


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
    if _is_sequence(value):
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
    values = _sequence(value, "contract.rules")
    rules = [_validate_rule(rule, index) for index, rule in enumerate(values)]
    if not rules:
        raise _error("contract.rules", "must not be empty")
    rule_ids = [rule["rule_id"] for rule in rules]
    if len(rule_ids) != len(set(rule_ids)):
        raise _error("contract.rules", "rule_id values must be unique")
    return rules


def _path_scopes_overlap(first: str, second: str) -> bool:
    first_parts = PurePosixPath(first).parts
    second_parts = PurePosixPath(second).parts
    shared = min(len(first_parts), len(second_parts))
    return first_parts[:shared] == second_parts[:shared]


def _validate_contract_paths(data: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    allowed_paths = _repo_paths(data["allowed_paths"], "contract.allowed_paths")
    forbidden_paths = _repo_paths(data["forbidden_paths"], "contract.forbidden_paths")
    overlap = {
        f"{allowed} <-> {forbidden}"
        for allowed in allowed_paths
        for forbidden in forbidden_paths
        if _path_scopes_overlap(allowed, forbidden)
    }
    if overlap:
        raise _error("contract.paths", f"allowed and forbidden paths overlap: {', '.join(sorted(overlap))}")
    return allowed_paths, forbidden_paths


def _add_amendment_fields(normalized: dict[str, Any], data: Mapping[str, Any], version: int) -> None:
    if version == 1:
        return
    normalized["previous_contract_hash"] = _sha256(
        data.get("previous_contract_hash"), "contract.previous_contract_hash"
    )
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
    schema_version = _integer(data["schema_version"], "contract.schema_version")
    version = _integer(data["version"], "contract.version")
    if schema_version != SCHEMA_VERSION:
        raise _error("contract.schema_version", f"must equal {SCHEMA_VERSION}")
    rules = _validate_rules(data["rules"])
    allowed_paths, forbidden_paths = _validate_contract_paths(data)
    approved_at = _string(data["approved_at"], "contract.approved_at")
    _timestamp(approved_at, "contract.approved_at")
    normalized = {
        "schema_version": SCHEMA_VERSION,
        "contract_id": _identifier(data["contract_id"], "contract.contract_id"),
        "version": version,
        "parent_issue": _integer(data["parent_issue"], "contract.parent_issue"),
        "objective": _string(data["objective"], "contract.objective"),
        "base_sha": _git_object_id(data["base_sha"], "contract.base_sha"),
        "policy_sha": _git_object_id(data["policy_sha"], "contract.policy_sha"),
        "risk_class": _string(data["risk_class"], "contract.risk_class"),
        "allowed_paths": allowed_paths,
        "forbidden_paths": forbidden_paths,
        "rules": rules,
        "required_evidence": _identifier_list(data["required_evidence"], "contract.required_evidence", nonempty=True),
        "merge_criteria": _string_list(data["merge_criteria"], "contract.merge_criteria", nonempty=True),
        "stop_conditions": _string_list(data["stop_conditions"], "contract.stop_conditions", nonempty=True),
        "approved_by": _string(data["approved_by"], "contract.approved_by"),
        "approved_at": approved_at,
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


def _external_run_ref(value: Any, field: str) -> str:
    run_ref = _string(value, field)
    if run_ref.startswith("run."):
        raise _error(field, "must identify external execution, not a GNC review-run ID")
    return run_ref


def _validate_evidence(data: Mapping[str, Any], field: str = "evidence") -> dict[str, Any]:
    _require_keys(
        data,
        {"record_type", "evidence_id", "requirement_id", "head_sha", "target", "state", "result", "run_ref"},
        field,
    )
    record_type = _string(data["record_type"], f"{field}.record_type")
    if record_type != "evidence":
        raise _error(f"{field}.record_type", "must equal 'evidence'")
    try:
        state = EvidenceState(_string(data["state"], f"{field}.state"))
    except ValueError as exc:
        raise _error(f"{field}.state", "is not a supported evidence state") from exc
    result = _string(data["result"], f"{field}.result")
    if state is not EvidenceState.EXECUTED and result == "pass":
        raise _error(f"{field}.result", "non-executed evidence cannot pass")
    run_ref = _external_run_ref(data["run_ref"], f"{field}.run_ref")
    return {
        "record_type": "evidence",
        "evidence_id": _identifier(data["evidence_id"], f"{field}.evidence_id"),
        "requirement_id": _identifier(data["requirement_id"], f"{field}.requirement_id"),
        "head_sha": _git_object_id(data["head_sha"], f"{field}.head_sha"),
        "target": _string(data["target"], f"{field}.target"),
        "state": state.value,
        "result": result,
        "run_ref": run_ref,
    }


def evidence_satisfies(value: Any, *, head_sha: str, target: str) -> bool:
    """Return whether evidence is an executed pass for the exact head/target."""
    record = _validate_evidence(_mapping(value, "evidence"))
    return (
        record["state"] == EvidenceState.EXECUTED.value
        and record["result"] == "pass"
        and record["head_sha"] == _git_object_id(head_sha, "head_sha")
        and record["target"] == _string(target, "target")
    )


def _finding_state(data: Mapping[str, Any], field: str = "finding") -> FindingState:
    try:
        return FindingState(_string(data["state"], f"{field}.state"))
    except ValueError as exc:
        raise _error(f"{field}.state", "is not a supported finding state") from exc


def _validate_duplicate_relation(data: Mapping[str, Any], state: FindingState, field: str = "finding") -> str | None:
    if state is FindingState.DUPLICATE_OF:
        if "duplicate_of" not in data:
            raise _error(f"{field}.duplicate_of", "is required for duplicate_of state")
        return _identifier(data["duplicate_of"], f"{field}.duplicate_of")
    if "duplicate_of" in data:
        raise _error(f"{field}.duplicate_of", "is only valid for duplicate_of state")
    return None


def _identifier_list(value: Any, field: str, *, nonempty: bool = False) -> list[str]:
    identifiers = _string_list(value, field, nonempty=nonempty)
    return [_identifier(item, f"{field}[{index}]") for index, item in enumerate(identifiers)]


def _validate_blocking_basis(
    data: Mapping[str, Any], origin: str, rule_id: str, field: str = "finding"
) -> dict[str, str]:
    blocking_basis = data.get("blocking_basis")
    allowed = (None, "human_confirmed", "deterministic_rule")
    if blocking_basis not in allowed:
        message = (
            "model findings cannot block without deterministic or human basis"
            if origin == "model"
            else "must be human_confirmed or deterministic_rule"
        )
        raise _error(f"{field}.blocking_basis", message)
    if blocking_basis is None:
        return _validate_no_blocking_basis(data, field)
    if blocking_basis == "human_confirmed":
        return _validate_human_blocking_basis(data, field)
    return _validate_deterministic_blocking_basis(data, rule_id, field)


def _validate_no_blocking_basis(data: Mapping[str, Any], field: str) -> dict[str, str]:
    if "blocking_rule_id" in data:
        raise _error(f"{field}.blocking_rule_id", "requires blocking_basis='deterministic_rule'")
    if "confirmed_by" in data:
        raise _error(f"{field}.confirmed_by", "requires blocking_basis='human_confirmed'")
    return {}


def _validate_human_blocking_basis(data: Mapping[str, Any], field: str) -> dict[str, str]:
    if "blocking_rule_id" in data:
        raise _error(f"{field}.blocking_rule_id", "is only valid for deterministic_rule blocking basis")
    return {
        "blocking_basis": "human_confirmed",
        "confirmed_by": _string(data.get("confirmed_by"), f"{field}.confirmed_by"),
    }


def _validate_deterministic_blocking_basis(data: Mapping[str, Any], rule_id: str, field: str) -> dict[str, str]:
    if "confirmed_by" in data:
        raise _error(f"{field}.confirmed_by", "is only valid for human_confirmed blocking basis")
    linked_rule = _identifier(data.get("blocking_rule_id"), f"{field}.blocking_rule_id")
    if linked_rule != rule_id:
        raise _error(f"{field}.blocking_rule_id", f"must match {field}.rule_id")
    return {"blocking_basis": "deterministic_rule", "blocking_rule_id": linked_rule}


def _validate_finding(data: Mapping[str, Any], field: str = "finding") -> dict[str, Any]:
    required = {
        "record_type",
        "finding_id",
        "rule_id",
        "subject",
        "failure_mode",
        "expected_outcome",
        "origin",
        "state",
        "head_sha",
    }
    _require_keys(data, required, field)
    record_type = _string(data["record_type"], f"{field}.record_type")
    if record_type != "finding":
        raise _error(f"{field}.record_type", "must equal 'finding'")
    state = _finding_state(data, field)
    duplicate_of = _validate_duplicate_relation(data, state, field)
    origin = _string(data["origin"], f"{field}.origin")
    rule_id = _identifier(data["rule_id"], f"{field}.rule_id")
    blocking = _validate_blocking_basis(data, origin, rule_id, field)
    result = {
        "record_type": "finding",
        "finding_id": _identifier(data["finding_id"], f"{field}.finding_id"),
        "rule_id": rule_id,
        "subject": _string(data["subject"], f"{field}.subject"),
        "failure_mode": _string(data["failure_mode"], f"{field}.failure_mode"),
        "expected_outcome": _string(data["expected_outcome"], f"{field}.expected_outcome"),
        "origin": origin,
        "state": state.value,
        "head_sha": _git_object_id(data["head_sha"], f"{field}.head_sha"),
    }
    result["fingerprint"] = finding_fingerprint(
        rule_id=result["rule_id"],
        subject=result["subject"],
        failure_mode=result["failure_mode"],
        expected_outcome=result["expected_outcome"],
    )
    if duplicate_of is not None:
        result["duplicate_of"] = duplicate_of
    result.update(blocking)
    return result


def _validate_analyzed_blobs(value: Any, field: str) -> dict[str, str]:
    blobs = _mapping(value, field)
    normalized: dict[str, str] = {}
    for path, digest in blobs.items():
        path_field = f"{field}[{path!r}]"
        canonical_path = _canonical_repo_path(_string(path, path_field), path_field)
        if canonical_path in normalized:
            raise _error(field, "must not contain equivalent repository paths")
        normalized[canonical_path] = _git_object_id(digest, f"{field}.{canonical_path}")
    return normalized


def _context_digest(blobs: Mapping[str, str]) -> str:
    ordered_context = [{"path": path, "blob_sha": blobs[path]} for path in sorted(blobs)]
    return canonical_hash(ordered_context)


def _validate_review_run(data: Mapping[str, Any], field: str = "review_run") -> dict[str, Any]:
    required = {
        "record_type",
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
    record_type = _string(data["record_type"], f"{field}.record_type")
    if record_type != "review_run":
        raise _error(f"{field}.record_type", "must equal 'review_run'")
    blobs = _validate_analyzed_blobs(data["analyzed_blobs"], f"{field}.analyzed_blobs")
    supplied_context_digest = _sha256(data["context_digest"], f"{field}.context_digest")
    if supplied_context_digest != _context_digest(blobs):
        raise _error(f"{field}.context_digest", "does not match the canonical analyzed_blobs context")
    return {
        "record_type": "review_run",
        "run_id": _identifier(data["run_id"], f"{field}.run_id"),
        "head_sha": _git_object_id(data["head_sha"], f"{field}.head_sha"),
        "merge_base_sha": _git_object_id(data["merge_base_sha"], f"{field}.merge_base_sha"),
        "contract_hash": _sha256(data["contract_hash"], f"{field}.contract_hash"),
        "policy_sha": _git_object_id(data["policy_sha"], f"{field}.policy_sha"),
        "context_digest": supplied_context_digest,
        "evaluator_version": _string(data["evaluator_version"], f"{field}.evaluator_version"),
        "target": _string(data["target"], f"{field}.target"),
        "review_mode": _string(data["review_mode"], f"{field}.review_mode"),
        "verdict": _string(data["verdict"], f"{field}.verdict"),
        "analyzed_blobs": blobs,
    }


def _validate_waiver(data: Mapping[str, Any], as_of: str | None) -> dict[str, Any]:
    field = "waiver"
    required = {"waiver_id", "finding_id", "actor", "reason", "scope", "head_sha", "contract_hash", "expires_at"}
    _require_keys(data, required, field)
    if as_of is None:
        raise _error("record.as_of", "is required to validate a waiver")
    expires_at = _string(data["expires_at"], f"{field}.expires_at")
    if _timestamp(expires_at, f"{field}.expires_at") <= _timestamp(as_of, "record.as_of"):
        raise _error(f"{field}.expires_at", "waiver is expired at record.as_of")
    return {
        "record_type": "waiver",
        "waiver_id": _identifier(data["waiver_id"], f"{field}.waiver_id"),
        "finding_id": _identifier(data["finding_id"], f"{field}.finding_id"),
        "actor": _string(data["actor"], f"{field}.actor"),
        "reason": _string(data["reason"], f"{field}.reason"),
        "scope": _string(data["scope"], f"{field}.scope"),
        "head_sha": _git_object_id(data["head_sha"], f"{field}.head_sha"),
        "contract_hash": _sha256(data["contract_hash"], f"{field}.contract_hash"),
        "expires_at": expires_at,
    }


def validate_record(value: Any, *, as_of: str | None = None) -> dict[str, Any]:
    """Validate a review-run, evidence, finding, waiver, or contract record."""
    data = _mapping(value, "record")
    record_type = _string(data.get("record_type"), "record.record_type")
    if record_type == "contract_version":
        contract = validate_contract(data.get("contract"))
        return {"record_type": record_type, "contract": contract, "contract_hash": canonical_hash(contract)}
    if record_type == "waiver":
        return _validate_waiver(data, as_of)
    validators = {
        "review_run": _validate_review_run,
        "evidence": _validate_evidence,
        "finding": _validate_finding,
    }
    try:
        return validators[record_type](data)
    except KeyError as exc:
        raise _error("record.record_type", f"unsupported type {record_type!r}") from exc


def _assert_sanitized_mapping(value: Mapping[Any, Any], field: str) -> None:
    for key, item in value.items():
        if not isinstance(key, str):
            raise _error(field, "object keys must be strings")
        normalized_key = key.strip().casefold()
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
    if _is_sequence(value):
        _assert_sanitized_sequence(value, field)
        return
    if isinstance(value, float):
        raise _error(field, "floating-point values are forbidden")
    if isinstance(value, str) and _SECRET_TEXT.search(value):
        raise _error(field, "secret-like material is forbidden")
    if value is None or isinstance(value, (str, bool, int)):
        return
    raise _error(field, f"unsupported JSON value type: {type(value).__name__}")


def _validate_evidence_list(value: Any) -> list[dict[str, Any]]:
    records = _sequence(value, "fixture.evidence")
    return [
        _validate_evidence(_mapping(item, f"fixture.evidence[{index}]"), f"fixture.evidence[{index}]")
        for index, item in enumerate(records)
    ]


def _validate_finding_list(value: Any) -> list[dict[str, Any]]:
    records = _sequence(value, "fixture.findings")
    return [
        _validate_finding(_mapping(item, f"fixture.findings[{index}]"), f"fixture.findings[{index}]")
        for index, item in enumerate(records)
    ]


def _validate_stale_evidence_binding(head_matches: bool, target_matches: bool, field: str) -> None:
    if head_matches or not target_matches:
        raise _error(field, "stale_sha evidence must differ only by head_sha")


def _validate_wrong_target_binding(head_matches: bool, target_matches: bool, field: str) -> None:
    if not head_matches or target_matches:
        raise _error(field, "wrong_target evidence must differ only by target")


def _validate_current_evidence_binding(head_matches: bool, target_matches: bool, field: str) -> None:
    if not head_matches or not target_matches:
        raise _error(field, "must bind to review_run head_sha and target")


def _validate_evidence_run_binding(evidence: Mapping[str, Any], run: Mapping[str, Any], field: str) -> None:
    bindings = {
        EvidenceState.STALE_SHA.value: _validate_stale_evidence_binding,
        EvidenceState.WRONG_TARGET.value: _validate_wrong_target_binding,
    }
    validator = bindings.get(evidence["state"], _validate_current_evidence_binding)
    validator(evidence["head_sha"] == run["head_sha"], evidence["target"] == run["target"], field)


def _validate_replay_rule_binding(finding: Mapping[str, Any], rules: Mapping[str, Mapping[str, Any]]) -> None:
    rule_id = finding["rule_id"]
    rule = rules.get(rule_id)
    if rule is None:
        raise _error("fixture.findings", f"rule_id {rule_id!r} does not exist in the contract")
    if finding.get("blocking_basis") is not None and not rule["blocking_eligible"]:
        raise _error("fixture.findings", f"rule_id {rule_id!r} is not blocking-eligible")


def _validate_replay_evidence_bindings(
    requirements: set[str],
    run: Mapping[str, Any],
    evidence: Sequence[Mapping[str, Any]],
    source_refs: set[str],
) -> None:
    for index, record in enumerate(evidence):
        field = f"fixture.evidence[{index}]"
        if record["requirement_id"] not in requirements:
            raise _error(f"{field}.requirement_id", "is not required by the contract")
        _validate_evidence_run_binding(record, run, field)
        run_ref = record["run_ref"]
        if f"execution:{run_ref}" not in source_refs:
            raise _error(f"{field}.run_ref", "has no matching execution source in fixture.source_refs")


def _validate_replay_finding_bindings(
    rules: Mapping[str, Mapping[str, Any]],
    run: Mapping[str, Any],
    findings: Sequence[Mapping[str, Any]],
) -> None:
    for index, finding in enumerate(findings):
        field = f"fixture.findings[{index}]"
        if finding["head_sha"] != run["head_sha"]:
            raise _error(f"{field}.head_sha", "does not match review_run.head_sha")
        _validate_replay_rule_binding(finding, rules)


def _validate_replay_contract_bindings(
    contract: Mapping[str, Any],
    run: Mapping[str, Any],
    evidence: Sequence[Mapping[str, Any]],
    source_refs: Sequence[str],
) -> None:
    if run["policy_sha"] != contract["policy_sha"]:
        raise _error("fixture.review_run.policy_sha", "does not match contract.policy_sha")
    _validate_replay_evidence_bindings(set(contract["required_evidence"]), run, evidence, set(source_refs))


def _validate_replay_expected(
    value: Any,
    run: Mapping[str, Any],
    findings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    expected = _mapping(value, "fixture.expected")
    _require_keys(expected, {"finding_ids", "verdict"}, "fixture.expected")
    expected_ids = _identifier_list(expected.get("finding_ids"), "fixture.expected.finding_ids")
    expected_verdict = _string(expected.get("verdict"), "fixture.expected.verdict")
    if expected_verdict != run["verdict"]:
        raise _error("fixture.expected.verdict", "must exactly match review_run.verdict")
    actual_ids = [finding["finding_id"] for finding in findings]
    if expected_ids != actual_ids:
        raise _error("fixture.expected.finding_ids", "must exactly match findings in stable order")
    return {"verdict": expected_verdict, "finding_ids": expected_ids}


def validate_replay_fixture(value: Any) -> dict[str, Any]:
    """Validate one sanitized, deterministic historical replay scenario."""
    data = _mapping(value, "fixture")
    _assert_sanitized(data)
    _require_keys(
        data, {"scenario_id", "source_refs", "contract", "review_run", "evidence", "findings", "expected"}, "fixture"
    )
    source_refs = _string_list(data["source_refs"], "fixture.source_refs", nonempty=True)
    contract = validate_contract(data["contract"])
    run = _validate_review_run(_mapping(data["review_run"], "fixture.review_run"), "fixture.review_run")
    if run["contract_hash"] != canonical_hash(contract):
        raise _error("fixture.review_run.contract_hash", "does not match the normalized contract")
    evidence = _validate_evidence_list(data["evidence"])
    findings = _validate_finding_list(data["findings"])
    _validate_replay_contract_bindings(contract, run, evidence, source_refs)
    rules = {rule["rule_id"]: rule for rule in contract["rules"]}
    _validate_replay_finding_bindings(rules, run, findings)
    expected = _validate_replay_expected(data["expected"], run, findings)
    return {
        "scenario_id": _identifier(data["scenario_id"], "fixture.scenario_id"),
        "source_refs": source_refs,
        "contract": contract,
        "review_run": run,
        "evidence": evidence,
        "findings": findings,
        "expected": expected,
    }
