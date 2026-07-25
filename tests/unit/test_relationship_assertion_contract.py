"""Unit tests for GRAC v1 machine-readable contract conformance."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.governance.relationship_assertion_contract import (
    CONTRACTS_V1_DIR,
    FixturesManifest,
    PredicatesDocument,
    TransitionsDocument,
    canonical_json_bytes,
    check_valid_fixture,
    compute_registry_digest,
    is_transition_allowed,
    load_contract_bundle,
    load_json,
    normalize_hex_digest,
    run_conformance,
    sha256_hex,
)

_BASE_PREDICATE = {
    "id": "financial.bond.issuer_reference@1",
    "subject_type": "Bond",
    "object_type": "Asset",
    "method_ids": ["bond.issuer_id.resolution@1"],
    "projection": {
        "edge_type": "corporate_link",
        "strength": "0.8",
        "direction": "subject_to_object",
        "purpose": "financial_graph_current_view",
    },
    "conflict_key": ["predicate_id", "subject_id"],
}


def _predicate_with_strength(strength: object) -> dict:
    """Return a predicate payload with ``projection.strength`` overridden."""
    predicate = json.loads(json.dumps(_BASE_PREDICATE))
    predicate["projection"]["strength"] = strength
    return predicate


def test_load_contract_bundle_matches_pinned_digest() -> None:
    """Pinned registry digest must match canonical predicates+transitions hash."""
    contract, predicates, transitions = load_contract_bundle()
    assert contract.contract_version == "grac.v1"
    assert contract.capability_claim_class == "NEXT"
    assert any(p.id == "financial.bond.issuer_reference@1" for p in predicates.predicates)
    assert "Accepted" in transitions.states
    predicates_raw = load_json(CONTRACTS_V1_DIR / contract.predicates_file)
    transitions_raw = load_json(CONTRACTS_V1_DIR / contract.transitions_file)
    assert compute_registry_digest(predicates_raw, transitions_raw) == normalize_hex_digest(contract.registry_digest)


def test_run_conformance_passes_on_clean_fixtures() -> None:
    """Clean pinned fixtures must produce zero violations."""
    assert run_conformance() == []


@pytest.mark.parametrize(
    "bad_strength",
    [0.8, "NaN", "inf", "-inf", "+0.8", "1e-1", "1_0", " 0.8", "1.1", "-0.1"],
)
def test_malformed_predicate_rejects_bad_strength(bad_strength: object) -> None:
    """Float, non-canonical, or out-of-range strength values must fail closed."""
    with pytest.raises(ValidationError):
        PredicatesDocument.model_validate({"predicates": [_predicate_with_strength(bad_strength)]})


def test_illegal_transition_from_terminal_rejected() -> None:
    """Transitions from terminal states must not appear in the allowed matrix."""
    transitions = TransitionsDocument.model_validate(load_json(CONTRACTS_V1_DIR / "transitions.json"))
    assert not is_transition_allowed(transitions, "Rejected", "Accepted")
    assert not is_transition_allowed(transitions, "Superseded", "Accepted")
    assert is_transition_allowed(transitions, "Proposed", "Accepted")


def test_wrong_authority_fails_valid_fixture(tmp_path: Path) -> None:
    """Allowed state edges with the wrong authority must fail conformance."""
    bundle = tmp_path / "v1"
    _copy_contract_tree(bundle)
    fixture_path = bundle / "fixtures" / "valid_accept.json"
    payload = load_json(fixture_path)
    payload["transition"]["authority"] = "proposer"
    _write_valid_fixture(bundle, fixture_path, payload)
    violations = run_conformance(bundle)
    assert any("authority mismatch" in v for v in violations)


def test_supersession_requires_string_successor_id() -> None:
    """Supersession edges must carry a non-empty string successor_assertion_id."""
    _, predicates, transitions = load_contract_bundle()
    predicate = json.loads(json.dumps(_BASE_PREDICATE))
    predicate["slice"] = {"object_id": "AAPL", "subject_id": "AAPL_BOND_2030"}
    base = {
        "predicate": predicate,
        "transition": {"from": "Accepted", "to": "Superseded", "authority": "acceptor"},
    }
    missing = check_valid_fixture(base, predicates, transitions)
    assert missing is not None and "successor_assertion_id" in missing

    bad_successors: list[object] = [True, 1, [], {}, "", "   "]
    for bad_successor in bad_successors:
        payload = json.loads(json.dumps(base))
        payload["transition"]["successor_assertion_id"] = bad_successor
        error = check_valid_fixture(payload, predicates, transitions)
        assert error is not None and "successor_assertion_id" in error

    ok = json.loads(json.dumps(base))
    ok["transition"]["successor_assertion_id"] = "assertion-successor-1"
    assert check_valid_fixture(ok, predicates, transitions) is None


def test_non_supersession_rejects_successor_key_presence() -> None:
    """Non-supersession transitions must not include successor_assertion_id at all."""
    _, predicates, transitions = load_contract_bundle()
    payload = load_json(CONTRACTS_V1_DIR / "fixtures" / "valid_accept.json")
    payload["transition"]["successor_assertion_id"] = None
    error = check_valid_fixture(payload, predicates, transitions)
    assert error is not None and "must not set successor_assertion_id" in error


def test_manifest_missing_required_kind_fails_conformance(tmp_path: Path) -> None:
    """Deleting a required kind from manifest.json must fail closed."""
    bundle = tmp_path / "v1"
    _copy_contract_tree(bundle)
    manifest_path = bundle / "fixtures" / "manifest.json"
    manifest = load_json(manifest_path)
    manifest["fixtures"] = [entry for entry in manifest["fixtures"] if entry["kind"] != "incomplete"]
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="missing required kinds"):
        FixturesManifest.model_validate(manifest)
    violations = run_conformance(bundle)
    assert any("missing required kinds" in v for v in violations)


def test_changed_golden_hash_fails_conformance(tmp_path: Path) -> None:
    """Altering a golden fixture without updating expected_digest must fail CI."""
    bundle = tmp_path / "v1"
    _copy_contract_tree(bundle)
    fixture_path = bundle / "fixtures" / "valid_accept.json"
    payload = load_json(fixture_path)
    payload["note"] = "tampered"
    fixture_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    violations = run_conformance(bundle)
    assert any("changed golden hash" in v for v in violations)


def test_incomplete_fixtures_fail_conformance(tmp_path: Path) -> None:
    """Manifest entries without fixture files must fail as incomplete."""
    bundle = tmp_path / "v1"
    _copy_contract_tree(bundle)
    (bundle / "fixtures" / "incomplete.json").unlink()
    violations = run_conformance(bundle)
    assert any("incomplete fixtures" in v for v in violations)


def test_canonical_json_rejects_floats_and_hashes_deterministically() -> None:
    """Hash inputs must use sorted keys, reject floats, and match a known digest."""
    with pytest.raises(ValueError, match="floating-point"):
        canonical_json_bytes({"weight": 0.1})
    encoded = canonical_json_bytes({"b": 1, "a": {"z": "0.8", "y": True}})
    assert encoded == b'{"a":{"y":true,"z":"0.8"},"b":1}'
    assert sha256_hex(encoded) == normalize_hex_digest(
        "1144582d-3890a53f-f5cb6e67-1e3ba856-31026acd-5df78300-23cc29cb-5df066dd"
    )


def _write_valid_fixture(bundle: Path, fixture_path: Path, payload: dict) -> None:
    """Persist a mutated valid fixture and refresh its expected digest."""
    fixture_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    manifest = load_json(bundle / "fixtures" / "manifest.json")
    for entry in manifest["fixtures"]:
        if entry["name"] == "valid_accept":
            entry["expected_digest"] = sha256_hex(canonical_json_bytes(payload))
    (bundle / "fixtures" / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _copy_contract_tree(destination: Path) -> None:
    """Copy the pinned v1 contract tree into ``destination`` for mutation tests."""
    shutil.copytree(CONTRACTS_V1_DIR, destination)
