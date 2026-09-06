"""Detect static addendum drift; do not adjudicate or replay Phase 3A runtime."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.gnc.schema import canonical_hash, validate_contract

ROOT = Path(__file__).resolve().parents[2]
ADDENDUM = "docs/governance/gnc-phase-3a-refusal-scope-addendum.md"
# Preparation identity only, not human acceptance or permission to repin.
ADDENDUM_HASH = "252211ad73c2b12de48cb64d3a5ce16ec028520af7376bfad5a7fb24d14a6292"
PARENT_HASHES = {
    "docs/governance/gnc-phase-3a-shadow-method.md": "0c6306d7c2ad6ed8f72cf0de016e29c7345f58d5eaac515010e78be749b02538",
    "docs/governance/gnc-phase-3a-shadow-contract.json": "7d7ed5533ebe328c20167a788d6822c0b6d16dfd00051cd1c623a24730fc1e89",
    "tests/fixtures/gnc/shadow/phase3a-cases.json": "2133a261d5a3d4b98bfe73a047b2e55938e136f42fb78746d09151ec194fc502",
    "tests/fixtures/gnc/shadow/phase3a-expected.json": "27b640a8d86eebd87ffdf586f85cf027b07f475c34b5fd5ca9300fdf61069395",
    "tests/unit/test_gnc_shadow_contract.py": "810f719b9ad953dff8c5e044c8a822e67a29a510b8c9b1e5a423ffc4ab62d1d4",
}
CLAUSES = (
    "That preparation decision withheld publication and CI spend; any later publication",
    "Assessment-level refusal and request-level rejection are distinct.",
    "projected states and links are empty and its source history remains preserved.",
    "Such a request cannot create, alter, substitute for, or veto authority.",
    "request must not change the projected lifecycle states, links or transitions;",
    "candidate diagnostics and raw candidate counts may differ.",
    "This does not reclassify `authority-unknown`, `waiver-inapplicable`, or any other",
    "Synthetic source authority remains a declared test assumption, not authentication.",
    "retaining every original input/expected definition and all 63 assertions.",
    "No new runtime test is executed by this candidate.",
    "not a retrofit of accepted results or proof that a runtime defect is repaired.",
)


def _bounded_bytes(relative_path: str) -> bytes:
    """Read bounded repository text without importing or executing its content."""
    with (ROOT / relative_path).open("rb") as stream:
        raw = stream.read(262145)
    assert len(raw) <= 262144, "static file exceeds the read ceiling"
    return raw


def _check_addendum(raw: bytes) -> None:
    """Bind exact preparation bytes, not runtime behavior or acceptance."""
    assert hashlib.sha256(raw).hexdigest() == ADDENDUM_HASH
    text = raw.decode("utf-8")
    for clause in CLAUSES:
        assert clause in text


def test_addendum_has_separate_exact_preparation_identity() -> None:
    """Keep the clarification identity separate from the historical freeze."""
    _check_addendum(_bounded_bytes(ADDENDUM))


@pytest.mark.parametrize("relative_path,digest", PARENT_HASHES.items())
def test_parent_bytes_are_unchanged(relative_path: str, digest: str) -> None:
    """Preserve all five accepted files, including their original static tests."""
    assert hashlib.sha256(_bounded_bytes(relative_path)).hexdigest() == digest


def test_historical_normalized_and_fixture_identities_are_unchanged() -> None:
    """Check parent normalization without deriving new outcomes or cases."""
    contract = json.loads(_bounded_bytes("docs/governance/gnc-phase-3a-shadow-contract.json"))
    inputs = json.loads(_bounded_bytes("tests/fixtures/gnc/shadow/phase3a-cases.json"))
    expected = json.loads(_bounded_bytes("tests/fixtures/gnc/shadow/phase3a-expected.json"))
    assert canonical_hash(validate_contract(contract)) == (
        "45d08e008b5bb7af1bdefd41051cd5a012f7c3f79d511a799c11c49a92d36fe9"
    )
    assert canonical_hash(inputs) == ("47f70d04ebf58cc60936488893890b58eb3b5b26890588365b39a7d281096fc6")
    assert canonical_hash(expected) == ("3d8b79a812e023fad51cf1ebfec8b83384b11a66edcbef6a6e401782f46b9205")
    assert len(inputs["cases"]) == len(expected["expected"]) == 63


@pytest.mark.parametrize("clause", CLAUSES)
def test_removing_a_boundary_clause_is_detected(clause: str) -> None:
    """Detect in-memory text drift; this is not a runtime guard-removal proof."""
    raw = _bounded_bytes(ADDENDUM)
    mutated = raw.replace(clause.encode("utf-8"), b"", 1)
    assert mutated != raw
    with pytest.raises(AssertionError):
        _check_addendum(mutated)


def test_preparation_base_and_runtime_checkpoint_are_explicit() -> None:
    """Retain the exact provenance and the original failing checkpoint reference."""
    text = _bounded_bytes(ADDENDUM).decode("utf-8")
    assert "8a606184279f65031698ead26c2b39d9ef8135cf" in text
    assert "dc1571c3a6d6f20a4f7fb0d3addb62c525c04cb8" in text
    assert "fce67057b0bad08a8e5c2d3902296f0a75670c08" in text
    assert "codex/gnc-phase3a-runtime" in text
    assert "tests/unit/test_gnc_shadow_refusal_scope_contract.py" in text
    assert "All existing files and all other new paths are forbidden." in text
