"""Unit tests for GRAC v1 machine-readable contract conformance."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.governance.relationship_assertion_contract import (
    CONTRACTS_V1_DIR,
    PredicatesDocument,
    TransitionsDocument,
    canonical_json_bytes,
    compute_registry_digest,
    is_transition_allowed,
    load_contract_bundle,
    load_json,
    run_conformance,
    sha256_hex,
)


def test_load_contract_bundle_matches_pinned_digest() -> None:
    """Pinned registry digest must match canonical predicates+transitions hash."""
    contract, predicates, transitions = load_contract_bundle()
    assert contract.contract_version == "grac.v1"
    assert contract.capability_claim_class == "NEXT"
    assert any(p.id == "financial.bond.issuer_reference@1" for p in predicates.predicates)
    assert "Accepted" in transitions.states
    predicates_raw = load_json(CONTRACTS_V1_DIR / contract.predicates_file)
    transitions_raw = load_json(CONTRACTS_V1_DIR / contract.transitions_file)
    assert compute_registry_digest(predicates_raw, transitions_raw) == contract.registry_digest


def test_run_conformance_passes_on_clean_fixtures() -> None:
    """Clean pinned fixtures must produce zero violations."""
    assert run_conformance() == []


def test_malformed_predicate_rejects_float_strength() -> None:
    """Projection strength must be a decimal string, never a JSON float."""
    with pytest.raises(ValidationError):
        PredicatesDocument.model_validate(
            {
                "predicates": [
                    {
                        "id": "financial.bond.issuer_reference@1",
                        "subject_type": "Bond",
                        "object_type": "Asset",
                        "method_ids": ["bond.issuer_id.resolution@1"],
                        "projection": {
                            "edge_type": "corporate_link",
                            "strength": 0.8,
                            "direction": "subject_to_object",
                            "purpose": "financial_graph_current_view",
                        },
                        "conflict_key": ["predicate_id", "subject_id"],
                    }
                ]
            }
        )


def test_illegal_transition_from_terminal_rejected() -> None:
    """Transitions from terminal states must not appear in the allowed matrix."""
    transitions = TransitionsDocument.model_validate(load_json(CONTRACTS_V1_DIR / "transitions.json"))
    assert not is_transition_allowed(transitions, "Rejected", "Accepted")
    assert not is_transition_allowed(transitions, "Superseded", "Accepted")
    assert is_transition_allowed(transitions, "Proposed", "Accepted")


def test_changed_golden_hash_fails_conformance(tmp_path: Path) -> None:
    """Altering a golden fixture without updating expected_digest must fail CI."""
    bundle = tmp_path / "v1"
    _copy_contract_tree(bundle)
    fixture_path = bundle / "fixtures" / "valid_accept.json"
    payload = load_json(fixture_path)
    payload["transition"]["authority"] = "tampered"
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


def test_canonical_json_is_sorted_and_compact() -> None:
    """Hash inputs must use sorted keys and compact separators without floats."""
    encoded = canonical_json_bytes({"b": 1, "a": {"z": "0.8", "y": True}})
    assert encoded == b'{"a":{"y":true,"z":"0.8"},"b":1}'
    assert sha256_hex(encoded) == sha256_hex(encoded)


def _copy_contract_tree(destination: Path) -> None:
    """Copy the pinned v1 contract tree into ``destination`` for mutation tests."""
    shutil.copytree(CONTRACTS_V1_DIR, destination)
