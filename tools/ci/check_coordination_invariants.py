"""Static checks for distributed coordination safety invariants."""

from __future__ import annotations

import ast
import re
import sys
from collections.abc import Iterable
from pathlib import Path

SCAN_ROOT_DIRS = (Path("src"), Path("api"))
_EXECUTION_ENTRYPOINTS = (
    "execute_rebuild",
    "start_rebuild",
    "rebuild_graph",
    "_perform_rebuild_and_persist_sync",
)

# -----------------------------
# Forbidden structural patterns
# -----------------------------

FORBIDDEN_PATTERNS: dict[str, re.Pattern] = {
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
_EXECUTION_PATTERN = "|".join(_EXECUTION_ENTRYPOINTS)
_EXECUTION_CALL_RE = re.compile(rf"\b({_EXECUTION_PATTERN})\b")


# -----------------------------
# Allowed exceptions (narrow)
# -----------------------------

ALLOWED_PATH_EXCEPTIONS = {
    "tests/",
    "tools/",
}

OWNERSHIP_MUTATION_ALLOWED_WRITERS = {
    Path("src/data/repository.py"),
    Path("src/data/db_models.py"),
}


def iter_python_files(root: Path) -> Iterable[Path]:
    """Yield Python files under root, skipping allowed exception paths."""
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if any(rel.startswith(exc.rstrip("/")) for exc in ALLOWED_PATH_EXCEPTIONS):
            continue
        yield path


def scan_file(path: Path) -> list[str]:
    """Scan a Python file for coordination invariant violations."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [f"ERROR reading {path}: {e}"]

    violations: list[str] = []

    # Ownership mutation is intentionally checked via AST (not regex) to avoid
    # false positives in comments/strings and false negatives in spacing variants.
    if path not in OWNERSHIP_MUTATION_ALLOWED_WRITERS and _contains_ownership_assignment(content):
        violations.append(f"MULTIPLE_OWNERSHIP_ASSIGNMENT violation in {path}")

    for name, pattern in FORBIDDEN_PATTERNS.items():
        if pattern.search(content):
            violations.append(f"{name} violation in {path}")

    # Strengthened check: flag any file that calls execution entrypoint
    # but does NOT actually call RecoveryGate.ensure_safe_to_execute().
    # Uses AST call matching to prevent bypass via comments/string literals.
    has_execution_call = _EXECUTION_CALL_RE.search(content)
    has_recovery_gate_call = _contains_ensure_safe_to_execute_call(content)

    if has_execution_call and not has_recovery_gate_call:
        violations.append(f"MISSING_RECOVERY_GATE_CALL violation in {path}")

    return violations


def _contains_ensure_safe_to_execute_call(content: str) -> bool:
    """Return True when file contains a real ensure_safe_to_execute() call expression."""
    try:
        parsed = ast.parse(content)
    except SyntaxError:
        return False

    for node in ast.walk(parsed):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "ensure_safe_to_execute"
        ):
            return True
    return False


def _contains_ownership_assignment(content: str) -> bool:
    """Return True when content contains assignment to active_worker_id/owner_id."""
    try:
        parsed = ast.parse(content)
    except SyntaxError:
        return False

    for node in ast.walk(parsed):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]

        for target in targets:
            if any(name in {"active_worker_id", "owner_id"} for name in _iter_assignment_target_names(target)):
                return True
    return False


def _iter_assignment_target_names(target: ast.expr) -> Iterable[str]:
    """Yield assignment target names for Name/Attribute/Tuple/List targets."""
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, ast.Attribute):
        yield target.attr
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            yield from _iter_assignment_target_names(element)


def main() -> None:
    """Run coordination invariant checks and exit non-zero on violations."""
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
