"""Contract tests for the trusted-runtime CI bootstrap boundary."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROBE = "python -m pip --version"
EXPECTED_PROBES = {
    ".circleci/config.yml": 1,
    ".github/workflows/ci.yml": 2,
    ".github/workflows/codecov.yaml": 1,
    ".github/workflows/codeflash.yaml": 1,
    ".github/workflows/codspeed.yml": 1,
    ".github/workflows/dependency-check.yml": 3,
    ".github/workflows/mcp-check.yml": 1,
    ".github/workflows/pylint.yml": 1,
    ".github/workflows/pyre.yml": 1,
    ".github/workflows/pysa.yml": 1,
    ".github/workflows/pytest.yml": 1,
    ".github/workflows/python-app.yml": 1,
    ".github/workflows/python-package.yml": 2,
    "scripts/ci_install_python_deps.sh": 1,
}


def _ci_install_surfaces() -> list[Path]:
    """Return every workflow and helper that installs CI dependencies."""
    workflows_dir = PROJECT_ROOT / ".github" / "workflows"
    workflows = sorted({*workflows_dir.glob("*.yml"), *workflows_dir.glob("*.yaml")})
    return [
        PROJECT_ROOT / ".circleci" / "config.yml",
        *workflows,
        PROJECT_ROOT / "scripts" / "ci_install_python_deps.sh",
    ]


def _logical_shell_lines(content: str) -> list[tuple[int, str]]:
    """Join shell continuations while retaining each command's physical start line."""
    logical_lines: list[tuple[int, str]] = []
    chunks: list[str] = []
    start_line = 1
    for line_number, physical_line in enumerate(content.splitlines(), start=1):
        if not chunks:
            start_line = line_number
        continued = bool(re.search(r"\\[ \t]*$", physical_line))
        chunks.append(re.sub(r"\\[ \t]*$", "", physical_line).strip())
        if not continued:
            logical_lines.append((start_line, " ".join(chunks)))
            chunks = []
    if chunks:
        logical_lines.append((start_line, " ".join(chunks)))
    return logical_lines


def _explicit_bootstrap_installs(content: str) -> list[tuple[int, str]]:
    """Return explicit pip installs of pip, setuptools, or wheel."""
    package_argument = re.compile(r"(?:^|\s)(?:pip|setuptools|wheel)(?:$|[\s<>=!~])")
    offenders: list[tuple[int, str]] = []
    for line_number, line in _logical_shell_lines(content):
        installs = re.finditer(
            r"\bpip(?:\d+(?:\.\d+)*)?\s+install\b(?P<arguments>[^;&|]*)",
            line,
        )
        for install in installs:
            arguments = install.group("arguments").split("#", maxsplit=1)[0]
            unquoted_arguments = arguments.replace('"', "").replace("'", "")
            if package_argument.search(unquoted_arguments):
                offenders.append((line_number, line.strip()))
    return offenders


@pytest.mark.unit
def test_inventory_records_runtime_pip_identity() -> None:
    """All 18 reconciled bootstrap sites retain the canonical evidence probe."""
    actual: dict[str, int] = {}
    for path in _ci_install_surfaces():
        count = path.read_text(encoding="utf-8").count(PROBE)
        if count:
            actual[path.relative_to(PROJECT_ROOT).as_posix()] = count

    assert actual == EXPECTED_PROBES
    assert sum(actual.values()) == 18


@pytest.mark.unit
def test_ci_configs_do_not_install_bootstrap_packages() -> None:
    """CI cannot silently replace runtime-supplied packaging tools."""
    offenders: list[str] = []
    for path in _ci_install_surfaces():
        content = path.read_text(encoding="utf-8")
        relative_path = path.relative_to(PROJECT_ROOT).as_posix()
        offenders.extend(
            f"{relative_path}:{line_number}: {line}" for line_number, line in _explicit_bootstrap_installs(content)
        )

    assert not offenders, "CI must not install pip, setuptools, or wheel:\n" + "\n".join(offenders)


@pytest.mark.unit
@pytest.mark.parametrize(
    "command",
    [
        "python -m pip install --upgrade pip",
        "pip install -U setuptools wheel",
        "pip3 install wheel",
        "pip3.12 install setuptools",
        'pip install "wheel==0.46.1"',
        "pip install --upgrade \\\n  pip",
        "pip install pylint && pip install wheel",
    ],
    ids=[
        "pip-upgrade",
        "short-upgrade",
        "pip3",
        "versioned-pip",
        "quoted-pin",
        "continued",
        "second-command",
    ],
)
def test_explicit_bootstrap_install_detector_rejects_mutations(command: str) -> None:
    """Common direct and multiline bootstrap mutations remain detectable."""
    assert _explicit_bootstrap_installs(command)


@pytest.mark.unit
def test_detector_preserves_physical_start_line_after_continuation() -> None:
    """Diagnostics keep real file locations after earlier continued commands."""
    content = "echo first \\\n  continued\nsafe-command\npip3 install wheel"
    assert _explicit_bootstrap_installs(content) == [(4, "pip3 install wheel")]


@pytest.mark.unit
@pytest.mark.parametrize(
    "command",
    [
        "python -m pip --version",
        "pip install -r requirements.txt",
        "pip install pip-audit",
        "python -m pip --version && pip install pylint",
    ],
    ids=["probe", "requirements", "prefixed-package", "chained-safe-install"],
)
def test_explicit_bootstrap_install_detector_allows_package_inputs(command: str) -> None:
    """Ordinary project and tool installs are outside the bootstrap prohibition."""
    assert not _explicit_bootstrap_installs(command)


@pytest.mark.unit
def test_dependency_policy_defines_trusted_bootstrap_boundary() -> None:
    """The authoritative dependency policy records the fixed CI decision."""
    policy = (PROJECT_ROOT / "docs" / "DEPENDENCY_POLICY.md").read_text(encoding="utf-8")
    section = policy.split("## CI bootstrap boundary", maxsplit=1)[1].split("\n## ", maxsplit=1)[0]
    assert PROBE in section
    assert "trusted-bootstrap boundary" in section
    assert "must not perform a floating network" in section
    assert "separate dependency decision" in section
