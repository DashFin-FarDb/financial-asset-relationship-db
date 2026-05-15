# tools/ci/check_coordination_invariants.py

from __future__ import annotations

import re
import sys
from collections.abc import Iterable
from pathlib import Path

SCAN_ROOT_DIRS = (Path("src"), Path("api"))

# -----------------------------
# Forbidden structural patterns
# -----------------------------

FORBIDDEN_PATTERNS: dict[str, re.Pattern] = {
    # Direct ownership mutation outside coordinator context.
    # \b and (?!=) prevent matching equality comparisons (==).
    "MULTIPLE_OWNERSHIP_ASSIGNMENT": re.compile(r"\b(active_worker_id|owner_id)\s*=(?!=)"),
    # Direct execution entrypoints outside coordinator
    "DIRECT_EXECUTION_ENTRY": re.compile(r"def\s+(execute_rebuild|run_rebuild|start_rebuild)\s*\("),
    # Unsafe fallback lock acquisition logic
    "UNSAFE_LOCK_FALLBACK": re.compile(r"(lock|advisory_lock).*(fallback|force|override)"),
    # Duplicate execution control paths (heuristic)
    "DUPLICATE_EXECUTION_PATH": re.compile(
        r"(execute_rebuild).*?(execute_rebuild)",
        re.DOTALL,
    ),
}

# Order-independent gate check: these two are tested together in scan_file
# rather than as a single regex, so placement of RecoveryGate in the file
# does not affect correctness.
_EXECUTION_CALL_RE = re.compile(r"def\s+(execute_rebuild|start_rebuild|rebuild_graph|_perform_rebuild_and_persist_sync)\s*\(")
_RECOVERY_GATE_RE = re.compile(r"\bRecoveryGate\b")


# -----------------------------
# Allowed exceptions (narrow)
# -----------------------------

ALLOWED_PATH_EXCEPTIONS = {
    "tests/",
    "tools/",
}

OWNERSHIP_MUTATION_ALLOWED_WRITERS = {
    Path("src/data/repository.py"),
}


def iter_python_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if any(rel.startswith(exc.rstrip("/")) for exc in ALLOWED_PATH_EXCEPTIONS):
            continue
        yield path


def scan_file(path: Path) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"ERROR reading {path}: {e}"]

    violations: list[str] = []

    for name, pattern in FORBIDDEN_PATTERNS.items():
        if name == "MULTIPLE_OWNERSHIP_ASSIGNMENT" and path in OWNERSHIP_MUTATION_ALLOWED_WRITERS:
            continue
        if pattern.search(content):
            violations.append(f"{name} violation in {path}")

    # Order-independent check: flag any file that calls execute_rebuild /
    # start_rebuild but contains no reference to RecoveryGate anywhere.
    if _EXECUTION_CALL_RE.search(content) and not _RECOVERY_GATE_RE.search(content):
        violations.append(f"MISSING_RECOVERY_GATE violation in {path}")

    return violations


def main() -> None:
    missing_roots = [root.as_posix() for root in SCAN_ROOT_DIRS if not root.exists()]
    if missing_roots:
        print(f"Required scan root(s) not found: {', '.join(missing_roots)} — failing invariant check.")
        sys.exit(1)

    all_violations: list[str] = []

    for root in SCAN_ROOT_DIRS:
        for file_path in iter_python_files(root):
            violations = scan_file(file_path)
            all_violations.extend(violations)

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
