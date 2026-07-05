"""Unit tests for coordination invariant scanner helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture()
def coordination_invariants_module():
    """Load coordination invariant scanner module by file path."""
    module_path = Path(__file__).resolve().parents[2] / "tools" / "ci" / "check_coordination_invariants.py"
    spec = importlib.util.spec_from_file_location("check_coordination_invariants", module_path)
    assert spec is not None and spec.loader is not None  # nosec B101
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_contains_ensure_safe_to_execute_ignores_strings_and_comments(coordination_invariants_module) -> None:
    """Raw text references should not satisfy AST-based call detection."""
    content = """
def rebuild_graph():
    note = ".ensure_safe_to_execute()"
    # Recovery gate call: gate.ensure_safe_to_execute()
    return note
"""
    assert coordination_invariants_module._contains_ensure_safe_to_execute_call(content) is False  # pylint: disable=protected-access


def test_contains_ensure_safe_to_execute_detects_real_call(coordination_invariants_module) -> None:
    """Real method calls should satisfy AST-based detection."""
    content = """
def rebuild_graph(gate):
    gate.ensure_safe_to_execute()
"""
    assert coordination_invariants_module._contains_ensure_safe_to_execute_call(content) is True  # pylint: disable=protected-access


def test_scan_file_flags_missing_gate_call_even_with_string_literal(
    tmp_path: Path,
    coordination_invariants_module,
) -> None:
    """Scanner should not accept a string literal as proof of gate invocation."""
    file_path = tmp_path / "module.py"
    file_path.write_text(
        """
def rebuild_graph():
    execute_rebuild()
    marker = ".ensure_safe_to_execute()"
""",
        encoding="utf-8",
    )

    violations = coordination_invariants_module.scan_file(file_path)
    assert any("MISSING_RECOVERY_GATE_CALL" in violation for violation in violations)  # nosec B101
