"""
tools/ci/check_coordination_invariants.py

Stage 5C — Static Coordination Invariant Enforcement

This script enforces structural invariants to prevent:
- split-brain rebuild execution
- multiple ownership assignment paths
- bypass of RecoveryGate
- unsafe lock fallback logic
- duplicate execution entrypoints

It is designed to fail fast in CI.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

SRC_DIR = Path("src")

# -----------------------------
# Forbidden structural patterns
# -----------------------------

FORBIDDEN_PATTERNS: dict[str, re.Pattern] = {
    # Direct ownership mutation outside coordinator context
    "MULTIPLE_OWNERSHIP_ASSIGNMENT": re.compile(r"(active_worker_id\s*=|owner_id\s*=).*"),
    # Bypass of recovery gate
    "RECOVERY_GATE_BYPASS": re.compile(r"(execute_rebuild|start_rebuild).*(?!.*RecoveryGate)"),
    # Direct execution entrypoints outside coordinator
    "DIRECT_EXECUTION_ENTRY": re.compile(r"def\s+(execute_rebuild|run_rebuild|start_rebuild)\s*\("),
    # Unsafe fallback lock acquisition logic
    "UNSAFE_LOCK_FALLBACK": re.compile(r"(lock|advisory_lock).*(fallback|force|override)"),
    # Duplicate execution control paths (heuristic)
    "DUPLICATE_EXECUTION_PATH": re.compile(
        r"(execute_rebuild).*?(execute_rebuild)",
        re.DOTALL,
    ),
    # Missing explicit gating usage (heuristic)
    "MISSING_RECOVERY_GATE": re.compile(
        r"execute_rebuild(?!.*RecoveryGate)",
        re.DOTALL,
    ),
}


# -----------------------------
# Allowed exceptions (narrow)
# -----------------------------

ALLOWED_PATH_EXCEPTIONS = {
    "tests/",
    "tools/",
}


def iter_python_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        if any(str(path).startswith(exc) for exc in ALLOWED_PATH_EXCEPTIONS):
            continue
        yield path


def scan_file(path: Path) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"ERROR reading {path}: {e}"]

    violations: list[str] = []

    for name, pattern in FORBIDDEN_PATTERNS.items():
        if pattern.search(content):
            violations.append(f"{name} violation in {path}")

    return violations


def main() -> None:
    if not SRC_DIR.exists():
        print("src/ directory not found — failing invariant check.")
        sys.exit(1)

    all_violations: list[str] = []

    for file_path in iter_python_files(SRC_DIR):
        violations = scan_file(file_path)
        all_violations.extend(violations)

    # Deduplicate for readability
    unique_violations = sorted(set(all_violations))

    if unique_violations:
        print("\n❌ Coordination Invariant Violations Detected:\n")
        for v in unique_violations:
            print(f" - {v}")

        print(
            "\nCI FAILURE: Distributed coordination safety invariants violated.\n"
            "Fix required before merge to prevent split-brain execution risks."
        )
        sys.exit(1)

    print("✅ Coordination invariants passed: no split-brain risks detected.")


if __name__ == "__main__":
    main()
