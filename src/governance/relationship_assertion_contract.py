"""Machine-readable Governed Relationship Assertion Contract (GRAC) v1 conformance.

Loads pinned registry JSON under ``src/governance/contracts/v1/``, validates schema
and lifecycle rules, and verifies golden fixture digests. Stdlib + existing Pydantic
only; no floating-point values participate in hash inputs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

CONTRACTS_V1_DIR = Path(__file__).resolve().parent / "contracts" / "v1"
CONTRACT_VERSION = "grac.v1"

LifecycleState = Literal[
    "Proposed",
    "Accepted",
    "Rejected",
    "Withdrawn",
    "Disputed",
    "Retracted",
    "Superseded",
]


class StrictModel(BaseModel):
    """Base model that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid")


class ProjectionSpec(StrictModel):
    """Predicate projection compatibility values (not confidence)."""

    edge_type: str
    strength: str = Field(description="Decimal string; never a JSON float")
    direction: Literal["subject_to_object", "object_to_subject", "bidirectional"]
    purpose: str

    @field_validator("strength")
    @classmethod
    def strength_must_be_decimal_string(cls, value: str) -> str:
        """Reject floats-as-strings that are not canonical decimal text."""
        if not isinstance(value, str):
            raise ValueError("projection strength must be a string")
        if any(ch in value for ch in "eE"):
            raise ValueError("projection strength must not use scientific notation")
        float(value)  # structural check only; hash inputs keep the original string
        return value


class PredicateSpec(StrictModel):
    """Versioned predicate registry entry."""

    id: str
    subject_type: str
    object_type: str
    method_ids: list[str] = Field(min_length=1)
    projection: ProjectionSpec
    conflict_key: list[str] = Field(min_length=1)
    slice: dict[str, str] | None = None


class PredicatesDocument(StrictModel):
    """predicates.json root."""

    predicates: list[PredicateSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def predicate_ids_unique(self) -> PredicatesDocument:
        """Reject duplicate predicate IDs."""
        ids = [p.id for p in self.predicates]
        if len(ids) != len(set(ids)):
            raise ValueError("predicate ids must be unique")
        return self


class TransitionSpec(StrictModel):
    """Allowed lifecycle transition."""

    from_state: LifecycleState = Field(alias="from")
    to_state: LifecycleState = Field(alias="to")
    authority: str
    requires_successor: bool = False

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class TransitionsDocument(StrictModel):
    """transitions.json root."""

    states: list[LifecycleState] = Field(min_length=1)
    terminal: list[LifecycleState] = Field(min_length=1)
    transitions: list[TransitionSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_transition_graph(self) -> TransitionsDocument:
        """Ensure terminal/states consistency and no duplicate edges."""
        state_set = set(self.states)
        if len(self.states) != len(state_set):
            raise ValueError("states must be unique")
        for terminal in self.terminal:
            if terminal not in state_set:
                raise ValueError(f"terminal state not listed in states: {terminal}")
        seen: set[tuple[str, str]] = set()
        for transition in self.transitions:
            if transition.from_state not in state_set or transition.to_state not in state_set:
                raise ValueError(f"transition references unknown state: {transition.from_state}->{transition.to_state}")
            if transition.from_state in self.terminal:
                raise ValueError(f"illegal transition from terminal state: {transition.from_state}")
            key = (transition.from_state, transition.to_state)
            if key in seen:
                raise ValueError(f"duplicate transition: {key[0]}->{key[1]}")
            seen.add(key)
        return self


class ContractDocument(StrictModel):
    """contract.json root."""

    contract_version: Literal["grac.v1"]
    status: Literal["frozen"]
    capability_claim_class: Literal["NEXT"]
    baseline_sha: str
    predicates_file: str
    transitions_file: str
    registry_digest: str
    normative_doc: str


class FixtureExpectation(StrictModel):
    """Per-fixture expectation metadata."""

    name: str
    kind: Literal["valid", "malformed_predicate", "illegal_transition", "incomplete"]
    expected_digest: str | None = None
    expect_error_substring: str | None = None


class FixturesManifest(StrictModel):
    """fixtures/manifest.json root."""

    fixtures: list[FixtureExpectation] = Field(min_length=1)


def canonical_json_bytes(payload: Any) -> bytes:
    """Serialize ``payload`` as canonical UTF-8 JSON (sorted keys, compact separators)."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Return lowercase hex SHA-256 digest of ``data``."""
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> Any:
    """Load a UTF-8 JSON document from ``path``."""
    return json.loads(path.read_text(encoding="utf-8"))


def compute_registry_digest(predicates_doc: dict[str, Any], transitions_doc: dict[str, Any]) -> str:
    """Hash the canonical concatenation of predicates and transitions documents."""
    payload = {"predicates": predicates_doc, "transitions": transitions_doc}
    return sha256_hex(canonical_json_bytes(payload))


def is_transition_allowed(transitions: TransitionsDocument, from_state: str, to_state: str) -> bool:
    """Return True when ``from_state`` -> ``to_state`` is an allowed lifecycle edge."""
    return any(t.from_state == from_state and t.to_state == to_state for t in transitions.transitions)


def load_contract_bundle(
    contracts_dir: Path = CONTRACTS_V1_DIR,
) -> tuple[ContractDocument, PredicatesDocument, TransitionsDocument]:
    """Load and schema-validate the pinned v1 contract bundle."""
    contract_path = contracts_dir / "contract.json"
    contract_raw = load_json(contract_path)
    contract = ContractDocument.model_validate(contract_raw)

    predicates_path = contracts_dir / contract.predicates_file
    transitions_path = contracts_dir / contract.transitions_file
    predicates_raw = load_json(predicates_path)
    transitions_raw = load_json(transitions_path)
    predicates = PredicatesDocument.model_validate(predicates_raw)
    transitions = TransitionsDocument.model_validate(transitions_raw)

    digest = compute_registry_digest(predicates_raw, transitions_raw)
    if digest != contract.registry_digest:
        raise ValueError(f"registry_digest mismatch: contract has {contract.registry_digest}, computed {digest}")
    if contract.contract_version != CONTRACT_VERSION:
        raise ValueError(f"unsupported contract_version: {contract.contract_version}")
    return contract, predicates, transitions


def check_valid_fixture(payload: dict[str, Any], transitions: TransitionsDocument) -> str | None:
    """Return a violation message if the valid fixture is not schema- and lifecycle-correct."""
    try:
        PredicatesDocument.model_validate({"predicates": [payload["predicate"]]})
    except (KeyError, ValidationError) as exc:
        return f"predicate validation failed: {exc}"
    try:
        from_state = payload["transition"]["from"]
        to_state = payload["transition"]["to"]
    except KeyError as exc:
        return f"transition missing field: {exc}"
    if not is_transition_allowed(transitions, from_state, to_state):
        return f"illegal transition in valid fixture: {from_state}->{to_state}"
    return None


def check_malformed_predicate_fixture(payload: dict[str, Any], expect_substring: str | None) -> str | None:
    """Return a violation if malformed predicate unexpectedly validates."""
    try:
        PredicatesDocument.model_validate({"predicates": [payload["predicate"]]})
    except (KeyError, ValidationError) as exc:
        detail = str(exc)
        if expect_substring and expect_substring not in detail:
            return f"malformed predicate error missing {expect_substring!r}: {detail!r}"
        return None
    return "expected malformed predicate to fail validation"


def check_illegal_transition_fixture(payload: dict[str, Any], transitions: TransitionsDocument) -> str | None:
    """Return a violation if the fixture transition is unexpectedly allowed."""
    try:
        from_state = payload["transition"]["from"]
        to_state = payload["transition"]["to"]
    except KeyError as exc:
        return f"transition missing field: {exc}"
    if is_transition_allowed(transitions, from_state, to_state):
        return f"expected illegal transition but allowed: {from_state}->{to_state}"
    return None


def check_incomplete_fixture(payload: dict[str, Any]) -> str | None:
    """Return a violation if an incomplete fixture looks complete."""
    if "predicate" in payload and "transition" in payload:
        return "incomplete fixture unexpectedly complete"
    return None


def evaluate_fixture_entry(
    entry: FixtureExpectation,
    payload: dict[str, Any],
    transitions: TransitionsDocument,
) -> list[str]:
    """Return violation messages for a single fixture entry and loaded payload."""
    if entry.kind == "valid":
        error = check_valid_fixture(payload, transitions)
        if error:
            return [f"valid fixture {entry.name} failed: {error}"]
        digest = sha256_hex(canonical_json_bytes(payload))
        if entry.expected_digest is None:
            return [f"valid fixture {entry.name} missing expected_digest"]
        if digest != entry.expected_digest:
            expected = entry.expected_digest
            return [f"changed golden hash for {entry.name}: expected {expected}, got {digest}"]
        return []

    if entry.kind == "malformed_predicate":
        error = check_malformed_predicate_fixture(payload, entry.expect_error_substring)
        if error:
            return [f"malformed_predicate fixture {entry.name} failed: {error}"]
        return []

    if entry.kind == "illegal_transition":
        error = check_illegal_transition_fixture(payload, transitions)
        if error:
            return [f"illegal_transition fixture {entry.name} failed: {error}"]
        return []

    if entry.kind == "incomplete":
        error = check_incomplete_fixture(payload)
        if error:
            return [f"incomplete fixture {entry.name} failed: {error}"]
        return []

    return [f"fixture {entry.name} has unsupported kind {entry.kind}"]


def run_conformance(contracts_dir: Path = CONTRACTS_V1_DIR) -> list[str]:
    """Run full conformance checks; return a list of violation messages (empty = pass)."""
    violations: list[str] = []
    try:
        _contract, predicates, transitions = load_contract_bundle(contracts_dir)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        return [f"contract bundle load failed: {exc}"]

    required_predicate = "financial.bond.issuer_reference@1"
    if not any(p.id == required_predicate for p in predicates.predicates):
        violations.append(f"missing required predicate: {required_predicate}")

    fixtures_dir = contracts_dir / "fixtures"
    manifest_path = fixtures_dir / "manifest.json"
    if not manifest_path.is_file():
        return violations + ["missing fixtures/manifest.json"]

    try:
        manifest = FixturesManifest.model_validate(load_json(manifest_path))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        return violations + [f"fixtures manifest invalid: {exc}"]

    for entry in manifest.fixtures:
        fixture_path = fixtures_dir / f"{entry.name}.json"
        if not fixture_path.is_file():
            violations.append(f"incomplete fixtures: missing {fixture_path.name}")
            continue
        try:
            payload = load_json(fixture_path)
        except (OSError, json.JSONDecodeError) as exc:
            violations.append(f"fixture {entry.name} unreadable: {exc}")
            continue
        violations.extend(evaluate_fixture_entry(entry, payload, transitions))

    return violations
