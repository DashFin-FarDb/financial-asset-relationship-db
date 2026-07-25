"""Machine-readable Governed Relationship Assertion Contract (GRAC) v1 conformance.

Loads pinned registry JSON under ``src/governance/contracts/v1/``, validates schema
and lifecycle rules, and verifies golden fixture digests. Stdlib + existing Pydantic
only; no floating-point values participate in hash inputs.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

CONTRACTS_V1_DIR = Path(__file__).resolve().parent / "contracts" / "v1"
CONTRACT_VERSION = "grac.v1"
REQUIRED_PREDICATE_ID = "financial.bond.issuer_reference@1"
REQUIRED_FIXTURE_KINDS = frozenset({"valid", "malformed_predicate", "illegal_transition", "incomplete"})
# Finite canonical decimal text: optional leading minus, no scientific notation, no underscores.
_STRENGTH_RE = re.compile(r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$")

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
        """Accept only finite canonical decimal text (no NaN/inf/scientific/+prefix)."""
        if not _STRENGTH_RE.fullmatch(value):
            raise ValueError("projection strength must be a finite canonical decimal string")
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
                raise ValueError(
                    f"transition references unknown state: " f"{transition.from_state}->{transition.to_state}"
                )
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

    @model_validator(mode="after")
    def require_complete_fixture_matrix(self) -> FixturesManifest:
        """Fail closed when any required fixture kind is missing from the manifest."""
        kinds = {entry.kind for entry in self.fixtures}
        missing = REQUIRED_FIXTURE_KINDS - kinds
        if missing:
            raise ValueError(f"fixtures manifest missing required kinds: {sorted(missing)}")
        return self


def normalize_hex_digest(value: str) -> str:
    """Normalize a stored digest by keeping lowercase hexadecimal characters only.

    Digests may be hyphen-grouped in JSON so secret scanners do not treat content
    hashes as credentials.
    """
    return "".join(ch for ch in value.lower() if ch in "0123456789abcdef")


def reject_float_hash_inputs(payload: Any, path: str = "$") -> None:
    """Raise ``ValueError`` when ``payload`` contains a JSON/Python float."""
    if isinstance(payload, float):
        raise ValueError(f"floating-point values must not participate in hash inputs at {path}")
    if isinstance(payload, dict):
        for key, value in payload.items():
            reject_float_hash_inputs(value, f"{path}.{key}")
        return
    if isinstance(payload, list):
        for index, value in enumerate(payload):
            reject_float_hash_inputs(value, f"{path}[{index}]")


def canonical_json_bytes(payload: Any) -> bytes:
    """Serialize ``payload`` as canonical UTF-8 JSON (sorted keys, compact separators)."""
    reject_float_hash_inputs(payload)
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


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


def find_transition(
    transitions: TransitionsDocument,
    from_state: str,
    to_state: str,
) -> TransitionSpec | None:
    """Return the allowed transition edge for ``from_state`` -> ``to_state``, if any."""
    for transition in transitions.transitions:
        if transition.from_state == from_state and transition.to_state == to_state:
            return transition
    return None


def is_transition_allowed(transitions: TransitionsDocument, from_state: str, to_state: str) -> bool:
    """Return True when ``from_state`` -> ``to_state`` is an allowed lifecycle edge."""
    return find_transition(transitions, from_state, to_state) is not None


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
    pinned = normalize_hex_digest(contract.registry_digest)
    if digest != pinned:
        raise ValueError(f"registry_digest mismatch: contract has {pinned}, computed {digest}")
    return contract, predicates, transitions


def check_valid_fixture(
    payload: dict[str, Any],
    predicates: PredicatesDocument,
    transitions: TransitionsDocument,
) -> str | None:
    """Return a violation message if the valid fixture is not schema- and lifecycle-correct."""
    try:
        predicate_raw = payload["predicate"]
        PredicatesDocument.model_validate({"predicates": [predicate_raw]})
    except (KeyError, ValidationError) as exc:
        return f"predicate validation failed: {exc}"

    predicate_id = predicate_raw.get("id")
    registered = next((p for p in predicates.predicates if p.id == predicate_id), None)
    if registered is None:
        return f"valid fixture predicate id not in registry: {predicate_id}"
    registered_raw = json.loads(registered.model_dump_json(exclude_none=True))
    if predicate_raw != registered_raw:
        return f"valid fixture predicate drifted from registry entry {predicate_id}"

    try:
        transition_raw = payload["transition"]
        from_state = transition_raw["from"]
        to_state = transition_raw["to"]
        authority = transition_raw["authority"]
    except KeyError as exc:
        return f"transition missing field: {exc}"

    allowed = find_transition(transitions, from_state, to_state)
    if allowed is None:
        return f"illegal transition in valid fixture: {from_state}->{to_state}"
    if authority != allowed.authority:
        return (
            f"transition authority mismatch for {from_state}->{to_state}: "
            f"fixture has {authority!r}, registry requires {allowed.authority!r}"
        )
    if allowed.requires_successor and not transition_raw.get("successor_assertion_id"):
        return f"supersession transition {from_state}->{to_state} requires successor_assertion_id"
    if not allowed.requires_successor and transition_raw.get("successor_assertion_id"):
        return f"non-supersession transition {from_state}->{to_state} must not set successor_assertion_id"
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


def _eval_valid(
    entry: FixtureExpectation,
    payload: dict[str, Any],
    predicates: PredicatesDocument,
    transitions: TransitionsDocument,
) -> list[str]:
    """Evaluate a valid golden fixture."""
    error = check_valid_fixture(payload, predicates, transitions)
    if error:
        return [f"valid fixture {entry.name} failed: {error}"]
    digest = sha256_hex(canonical_json_bytes(payload))
    if entry.expected_digest is None:
        return [f"valid fixture {entry.name} missing expected_digest"]
    expected = normalize_hex_digest(entry.expected_digest)
    if digest != expected:
        return [f"changed golden hash for {entry.name}: expected {expected}, got {digest}"]
    return []


def _eval_malformed(
    entry: FixtureExpectation,
    payload: dict[str, Any],
    _predicates: PredicatesDocument,
    _transitions: TransitionsDocument,
) -> list[str]:
    """Evaluate a malformed-predicate negative fixture."""
    error = check_malformed_predicate_fixture(payload, entry.expect_error_substring)
    if error:
        return [f"malformed_predicate fixture {entry.name} failed: {error}"]
    return []


def _eval_illegal(
    entry: FixtureExpectation,
    payload: dict[str, Any],
    _predicates: PredicatesDocument,
    transitions: TransitionsDocument,
) -> list[str]:
    """Evaluate an illegal-transition negative fixture."""
    error = check_illegal_transition_fixture(payload, transitions)
    if error:
        return [f"illegal_transition fixture {entry.name} failed: {error}"]
    return []


def _eval_incomplete(
    entry: FixtureExpectation,
    payload: dict[str, Any],
    _predicates: PredicatesDocument,
    _transitions: TransitionsDocument,
) -> list[str]:
    """Evaluate an incomplete negative fixture."""
    error = check_incomplete_fixture(payload)
    if error:
        return [f"incomplete fixture {entry.name} failed: {error}"]
    return []


_FIXTURE_EVALUATORS: dict[
    str,
    Callable[
        [FixtureExpectation, dict[str, Any], PredicatesDocument, TransitionsDocument],
        list[str],
    ],
] = {
    "valid": _eval_valid,
    "malformed_predicate": _eval_malformed,
    "illegal_transition": _eval_illegal,
    "incomplete": _eval_incomplete,
}


def evaluate_fixture_entry(
    entry: FixtureExpectation,
    payload: dict[str, Any],
    predicates: PredicatesDocument,
    transitions: TransitionsDocument,
) -> list[str]:
    """Return violation messages for a single fixture entry and loaded payload."""
    evaluator = _FIXTURE_EVALUATORS.get(entry.kind)
    if evaluator is None:
        return [f"fixture {entry.name} has unsupported kind {entry.kind}"]
    return evaluator(entry, payload, predicates, transitions)


def run_conformance(contracts_dir: Path = CONTRACTS_V1_DIR) -> list[str]:
    """Run full conformance checks; return a list of violation messages (empty = pass)."""
    violations: list[str] = []
    try:
        _contract, predicates, transitions = load_contract_bundle(contracts_dir)
    except (OSError, ValidationError, ValueError) as exc:
        return [f"contract bundle load failed: {exc}"]

    if not any(p.id == REQUIRED_PREDICATE_ID for p in predicates.predicates):
        violations.append(f"missing required predicate: {REQUIRED_PREDICATE_ID}")

    fixtures_dir = contracts_dir / "fixtures"
    manifest_path = fixtures_dir / "manifest.json"
    if not manifest_path.is_file():
        return violations + ["missing fixtures/manifest.json"]

    try:
        manifest = FixturesManifest.model_validate(load_json(manifest_path))
    except (OSError, ValidationError, ValueError) as exc:
        return violations + [f"fixtures manifest invalid: {exc}"]

    for entry in manifest.fixtures:
        fixture_path = fixtures_dir / f"{entry.name}.json"
        if not fixture_path.is_file():
            violations.append(f"incomplete fixtures: missing {fixture_path.name}")
            continue
        try:
            payload = load_json(fixture_path)
        except (OSError, ValueError) as exc:
            violations.append(f"fixture {entry.name} unreadable: {exc}")
            continue
        violations.extend(evaluate_fixture_entry(entry, payload, predicates, transitions))

    return violations
