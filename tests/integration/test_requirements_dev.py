"""
Tests for requirements-dev.txt development dependencies file.

Validates:
- The file exists, is readable, UTF-8, ends with newline, and has no trailing whitespace
- Requirements lines are parseable by packaging.Requirement
- No duplicate packages (case-insensitive, hyphen/underscore normalized)
- Required dev tools are present (pytest, mypy, black, etc.)
- Version specifiers exist and are syntactically valid (including compound specifiers)

Policy:
- All non-types packages must have a version constraint.
- Type stub packages (types-*) may omit a version constraint (common in repos).
"""

# nosec B101

from __future__ import annotations

import re
from pathlib import Path

import pytest
from packaging.requirements import Requirement

# tests/integration/test_requirements_dev.py -> repo root is parents[2]
REQUIREMENTS_FILE = Path(__file__).resolve().parents[2] / "requirements-dev.txt"


def _strip_inline_comment(line: str) -> str:
    """Strip trailing inline comments from a requirements line."""
    return line.split("#", 1)[0].strip()


def _extract_package_token(raw_line: str, req: Requirement) -> str:
    """
    Extract the package token as written in the file (preserve original casing),
    excluding extras and environment markers.
    """
    line = _strip_inline_comment(raw_line)

    # Drop environment markers
    line = line.split(";", 1)[0].strip()
    # Drop extras
    line = line.split("[", 1)[0].strip()

    # Split at the first occurrence of any operator character (<,>,=,!,~) or comma
    pkg_part = re.split(r"(?=[<>=!~,])", line, 1)[0].strip()
    return pkg_part or req.name.strip()


def _normalize_specifier(specifier_str: str) -> str:
    """Normalize a version specifier string by removing spaces around commas."""
    if not specifier_str:
        return ""
    parts = [s.strip() for s in specifier_str.split(",") if s.strip()]
    return ",".join(parts)


def parse_requirements(file_path: Path) -> list[tuple[str, str]]:
    """
    Parse requirements file and return list of (package_token, normalized_specifier).

    - Preserves package token casing as written in the file where possible.
    - Normalizes specifiers (removes spaces around commas).
    - Ignores empty lines and comment-only lines.
    - Strips inline comments before parsing.
    """
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OSError(f"Could not open requirements file '{file_path}': {exc}") from exc

    requirements: list[tuple[str, str]] = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue

        line = _strip_inline_comment(stripped)
        if not line:
            continue

        # Fail fast if malformed
        req = Requirement(line)

        pkg = _extract_package_token(line, req)
        spec = _normalize_specifier(str(req.specifier).strip())
        requirements.append((pkg, spec))

    return requirements


def _normalize_name_for_dupe_check(name: str) -> str:
    """PEP 503-ish normalization sufficient for duplicate detection."""
    return name.strip().lower().replace("-", "_")


@pytest.fixture()
def parsed_requirements() -> list[tuple[str, str]]:
    """Parse requirements-dev.txt and return (package_token, normalized_specifier) pairs.

    This fixture centralizes file parsing so multiple tests can share a single,
    consistent interpretation of the requirements file (including comment stripping
    and specifier normalization).
    """
    return parse_requirements(REQUIREMENTS_FILE)


@pytest.fixture()
def package_names(parsed_requirements: list[tuple[str, str]]) -> list[str]:
    """Return just the package tokens extracted from the parsed requirements.

    This is used by tests that only care about package presence/duplication and not
    the associated version specifier.
    """
    return [pkg for pkg, _ in parsed_requirements]


# -----------------------
# File existence / format
# -----------------------
def test_file_exists() -> None:
    """Ensure the development requirements file path exists."""
    assert REQUIREMENTS_FILE.exists()


def test_file_is_file() -> None:
    """Ensure the requirements path points to a regular file (not a directory)."""
    assert REQUIREMENTS_FILE.is_file()


def test_file_is_readable_and_nonempty() -> None:
    """Ensure the file can be read as UTF-8 and is not empty."""
    content = REQUIREMENTS_FILE.read_text(encoding="utf-8")
    assert len(content) > 0


def test_file_ends_with_newline() -> None:
    """Ensure the file ends with a trailing newline (POSIX-friendly formatting)."""
    content = REQUIREMENTS_FILE.read_text(encoding="utf-8")
    assert content.endswith("\n")


def test_no_trailing_whitespace() -> None:
    """Ensure no line contains trailing whitespace (excluding the newline)."""
    lines = REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines(True)
    lines_with_trailing = [(i + 1, line) for i, line in enumerate(lines) if line.rstrip("\n") != line.rstrip()]
    assert lines_with_trailing == []


def test_reasonable_file_size() -> None:
    """Ensure the requirements file is not unexpectedly large for dev tooling."""
    lines = REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines()
    assert len(lines) < 200


# -----------------------
# Parseability / validity
# -----------------------
def test_all_non_comment_lines_parse_with_packaging() -> None:
    """Ensure every non-empty, non-comment requirement line parses via packaging.Requirement."""
    for raw in REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue

        line = _strip_inline_comment(stripped)
        if not line:
            continue

        Requirement(line)  # should not raise


def test_no_duplicate_packages_case_insensitive(package_names: list[str]) -> None:
    """Ensure no duplicate packages exist after normalizing case and hyphen/underscore."""
    seen: set[str] = set()
    duplicates: list[str] = []
    for pkg in package_names:
        norm = _normalize_name_for_dupe_check(pkg)
        if norm in seen:
            duplicates.append(pkg)
        seen.add(norm)
    assert duplicates == []


def test_package_names_valid_characters(package_names: list[str]) -> None:
    """Ensure extracted package tokens contain only allowed characters."""
    valid_name_pattern = re.compile(r"^[a-zA-Z0-9_.-]+$")
    invalid = [pkg for pkg in package_names if not valid_name_pattern.match(pkg)]
    assert invalid == []


# -----------------------
# Required tooling
# -----------------------
def test_required_dev_tools_present(package_names: list[str]) -> None:
    """Ensure the dev requirements include core tooling (test, lint, type, formatting, hooks)."""
    lowered = {_normalize_name_for_dupe_check(p) for p in package_names}
    required = {
        "pytest",
        "pytest_cov",
        "mypy",
        "black",
        "isort",
        "flake8",
        "pylint",
        "pre_commit",
    }
    missing = sorted(req for req in required if req not in lowered)
    assert missing == []


# -----------------------
# Version constraints
# -----------------------
def test_all_non_types_packages_have_version_constraints(
    parsed_requirements: list[tuple[str, str]],
) -> None:
    """
    Enforce version constraints for all non-types packages.
    Allow types-* packages to omit a constraint.
    """
    missing = [
        pkg
        for pkg, ver in parsed_requirements
        if not ver and not _normalize_name_for_dupe_check(pkg).startswith("types_")
    ]
    assert missing == []


def test_version_specifiers_are_valid(
    parsed_requirements: list[tuple[str, str]],
) -> None:
    """
    Validate that each non-empty specifier string is acceptable in practice.

    Allows compound constraints like ">=6.0,<7.0" and operators like "!=".
    """
    # Longest-first prevents accidental matches of ">" before ">=", etc.
    allowed_ops: tuple[str, ...] = (">=", "==", "<=", "~=", "!=", ">", "<")

    def _leading_operator(text: str) -> str | None:
        """Return the leading operator from allowed_ops, or None if none match."""
        for op in allowed_ops:
            if text.startswith(op):
                return op
        return None

    for pkg, spec in parsed_requirements:
        if not spec:
            continue

        parts = [p.strip() for p in spec.split(",") if p.strip()]
        assert parts, f"Empty specifier for {pkg}"

        for part in parts:
            op = _leading_operator(part)
            assert op is not None, f"Invalid operator in spec '{spec}' for {pkg}"

            tail = part[len(op) :].strip()
            assert tail and tail[0].isdigit(), f"Invalid version in spec '{spec}' for {pkg}"


# -----------------------
# PyYAML specific checks
# -----------------------
def test_pyyaml_present(package_names: list[str]) -> None:
    """Ensure PyYAML is present in requirements-dev.txt (case/format normalized)."""
    lowered = {_normalize_name_for_dupe_check(p) for p in package_names}
    assert "pyyaml" in lowered


def test_types_pyyaml_present(package_names: list[str]) -> None:
    """Ensure the PyYAML type stubs (types-PyYAML) are present (normalized token check)."""
    lowered = {_normalize_name_for_dupe_check(p) for p in package_names}
    assert "types_pyyaml" in lowered


def test_pyyaml_minimum_version(parsed_requirements: list[tuple[str, str]]) -> None:
    """Ensure PyYAML specifies a minimum supported version (>=6.0)."""
    pyyaml_specs = [ver for pkg, ver in parsed_requirements if _normalize_name_for_dupe_check(pkg) == "pyyaml"]
    assert len(pyyaml_specs) == 1
    assert pyyaml_specs[0].startswith(">="), "PyYAML should use a minimum version constraint"
    assert pyyaml_specs[0].startswith(">=6.0"), f"Expected PyYAML >=6.0, got {pyyaml_specs[0]}"


def test_type_stubs_have_base_packages(
    parsed_requirements: list[tuple[str, str]],
) -> None:
    """Ensure each types-* stub package has its corresponding base package present."""
    lowered = {_normalize_name_for_dupe_check(p) for p, _ in parsed_requirements}

    for pkg, _ in parsed_requirements:
        norm = _normalize_name_for_dupe_check(pkg)
        if norm.startswith("types_"):
            base = norm.removeprefix("types_")
            assert base in lowered, f"Type stub package '{pkg}' has no corresponding base package"
