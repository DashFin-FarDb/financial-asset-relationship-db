"""Offline Governance and Compliance (GNC) contract primitives."""

from typing import Any, Mapping

from .schema import (  # noqa: F401
    EvidenceState,
    FindingState,
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


def waiver_applies(value: Any, *, as_of: str, context: Mapping[str, Any]) -> bool:
    """Return whether a valid waiver binds the exact current context."""
    record = validate_record(value, as_of=as_of)
    bindings = ("finding_id", "head_sha", "contract_hash", "scope")
    return all(record[field] == context.get(field) for field in bindings)
