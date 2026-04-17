"""
Integration tests for pyproject.toml [project.optional-dependencies] dev section.

Validates the version constraints in the dev extras that were updated in this PR:
- types-PyYAML bumped from >=6.0.0 to >=6.0.12
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PYPROJECT_FILE = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _parse_dev_extras(pyproject_path: Path) -> list[str]:
    """Return the list of raw dependency strings from [project.optional-dependencies] dev.

    Reads the TOML file as plain text and extracts the entries inside the
    ``dev = [...]`` array without pulling in a TOML library that may not be
    available in older Python environments (tomllib is stdlib only from 3.11).
    Falls back to the ``tomllib`` / ``tomli`` stdlib/back-port when available
    so that the parsing is robust.
    """
    try:
        # tomllib is in stdlib from Python 3.11; tomli is a compatible backport
        try:
            import tomllib  # type: ignore[import]
        except ImportError:
            import tomli as tomllib  # type: ignore[import]

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("optional-dependencies", {}).get("dev", [])
    except ImportError:
        pass

    # Fallback: plain-text extraction of the dev = [...] block
    content = pyproject_path.read_text(encoding="utf-8")
    match = re.search(r"\[project\.optional-dependencies\].*?dev\s*=\s*\[(.*?)\]", content, re.DOTALL)
    if not match:
        return []
    block = match.group(1)
    entries: list[str] = []
    for line in block.splitlines():
        line = line.strip().strip(",").strip('"').strip("'")
        if line and not line.startswith("#"):
            entries.append(line)
    return entries


@pytest.fixture()
def dev_extras() -> list[str]:
    """Return the parsed dev dependency strings from pyproject.toml."""
    return _parse_dev_extras(PYPROJECT_FILE)


# ----------------------------------
# File existence / parseability
# ----------------------------------
def test_pyproject_exists() -> None:
    """Ensure pyproject.toml exists at the repository root."""
    assert PYPROJECT_FILE.exists(), "pyproject.toml not found"


def test_pyproject_has_dev_extras(dev_extras: list[str]) -> None:
    """Ensure the [project.optional-dependencies] dev section is non-empty."""
    assert len(dev_extras) > 0, "pyproject.toml dev extras should not be empty"


# ----------------------------------
# types-PyYAML version constraint
# ----------------------------------
def test_types_pyyaml_present_in_dev_extras(dev_extras: list[str]) -> None:
    """Verify types-PyYAML is listed in the dev extras."""
    lowered = [dep.lower() for dep in dev_extras]
    assert any("types-pyyaml" in dep for dep in lowered), (
        "types-PyYAML should be listed under [project.optional-dependencies] dev in pyproject.toml"
    )


def test_types_pyyaml_minimum_version_is_6_0_12(dev_extras: list[str]) -> None:
    """Verify types-PyYAML minimum version in pyproject.toml dev extras is >=6.0.12.

    The PR bumped the constraint from >=6.0.0 to >=6.0.12.
    """
    types_pyyaml_entry = next(
        (dep for dep in dev_extras if dep.lower().startswith("types-pyyaml")), None
    )
    assert types_pyyaml_entry is not None, (
        "types-PyYAML not found in pyproject.toml dev extras"
    )

    assert ">=" in types_pyyaml_entry, (
        f"types-PyYAML should use a >= constraint, got: {types_pyyaml_entry!r}"
    )

    min_ver_str = ""
    for part in types_pyyaml_entry.split(","):
        part = part.strip()
        if part.lower().startswith("types-pyyaml>="):
            min_ver_str = part.split(">=", 1)[1].strip()
            break
        elif part.startswith(">="):
            min_ver_str = part[2:].strip()
            break

    assert min_ver_str, (
        f"Could not parse minimum version from types-PyYAML entry: {types_pyyaml_entry!r}"
    )

    min_ver = tuple(int(x) for x in min_ver_str.split(".") if x.isdigit())
    required_floor = (6, 0, 12)
    assert min_ver >= required_floor, (
        f"types-PyYAML in pyproject.toml dev extras should be >=6.0.12 but got >={min_ver_str}"
    )


def test_types_pyyaml_old_floor_not_used(dev_extras: list[str]) -> None:
    """Regression: the old >=6.0.0 floor must not still be in use.

    After the PR the constraint should resolve to at least 6.0.12.  If the
    minimum version is exactly 6.0.0 the old (pre-PR) value was not updated.
    """
    types_pyyaml_entry = next(
        (dep for dep in dev_extras if dep.lower().startswith("types-pyyaml")), None
    )
    if types_pyyaml_entry is None:
        pytest.skip("types-PyYAML not found in dev extras")

    # Confirm the entry does not pin to 6.0.0 exactly
    assert ">=6.0.0" not in types_pyyaml_entry, (
        "types-PyYAML constraint should have been bumped from >=6.0.0 to >=6.0.12"
    )


# ----------------------------------
# General dev extras sanity checks
# ----------------------------------
def test_dev_extras_include_pytest(dev_extras: list[str]) -> None:
    """Verify pytest is still listed in the dev extras."""
    lowered = [dep.lower() for dep in dev_extras]
    assert any(dep.startswith("pytest") for dep in lowered), (
        "pytest should be present in pyproject.toml dev extras"
    )


def test_dev_extras_all_have_version_constraints(dev_extras: list[str]) -> None:
    """Every dev extra should carry a version constraint (>=, ==, ~=, <=, or compound)."""
    operators = (">=", "==", "~=", "<=", ">", "<", "!=")
    missing = [dep for dep in dev_extras if not any(op in dep for op in operators)]
    assert missing == [], (
        f"Dev extras missing version constraints: {missing}"
    )