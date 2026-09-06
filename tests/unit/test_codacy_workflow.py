"""Contract tests for the fail-closed Codacy SARIF workflow."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "codacy.yml"
CODACY_IMAGE = "codacy/codacy-analysis-cli@sha256:d412b2a84e72d0b541e29dd6cdffa78a73afcf35d8aa546988cd2a44edaab15c"


@pytest.fixture(scope="module")
def codacy_workflow() -> dict[str, Any]:
    """Load workflow configuration without invoking any hosted scanner."""
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def codacy_steps(codacy_workflow: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the Codacy job steps from the repository workflow."""
    return codacy_workflow["jobs"]["codacy-security-scan"]["steps"]


def _step(steps: list[dict[str, Any]], name: str) -> dict[str, Any]:
    """Return one named workflow step."""
    return next(step for step in steps if step.get("name") == name)


@pytest.mark.unit
def test_codacy_direct_image_transport(codacy_steps: list[dict[str, Any]]) -> None:
    """Keep the direct image invocation free of a downloaded action wrapper."""
    scan = _step(codacy_steps, "Run Codacy Analysis CLI")

    assert "uses" not in scan
    assert "with" not in scan
    assert scan["shell"] == "bash"
    assert scan["env"] == {
        "CODACY_CODE": "${{ github.workspace }}",
        "CODACY_PROJECT_TOKEN": "${{ secrets.CODACY_PROJECT_TOKEN }}",
        "CODACY_COMMIT_SHA": "${{ github.event.pull_request.head.sha || github.sha }}",
    }
    assert "${{" not in scan["run"]
    assert CODACY_IMAGE in scan["run"]


@pytest.fixture(scope="module")
def native_bash() -> str:
    """Use native Bash for the stub, never launch WSL on Windows."""
    if os.name == "nt":
        git = shutil.which("git")
        bash = Path(git).resolve().parents[1] / "bin" / "bash.exe" if git else None
        if bash is None or not bash.is_file():
            pytest.skip("Native Git Bash is required for local Windows command tests; do not launch WSL")
        return str(bash)
    bash_path = shutil.which("bash")
    assert bash_path is not None, "Bash is required on the Linux CI runner"
    return bash_path


@pytest.mark.unit
@pytest.mark.parametrize("exit_code", [0, 1, 100, 101, 125])
@pytest.mark.parametrize("workspace", ["/synthetic/repo", "/synthetic/FarDb space;$(false)/unicode-δ"])
@pytest.mark.parametrize("token", ["", "synthetic token;$(false)"])
def test_codacy_command_arguments_and_failure_propagation(
    codacy_steps: list[dict[str, Any]], native_bash: str, exit_code: int, workspace: str, token: str
) -> None:
    """Exercise the workflow shell with an inert Docker function, not a real scanner."""
    scan = _step(codacy_steps, "Run Codacy Analysis CLI")
    stub = """docker() {
      printf '%s\\0' "$CODACY_CODE" "$CODACY_PROJECT_TOKEN" "$@"
      return "$CODACY_STUB_STATUS"
    }
    readonly -f docker
    """
    # Use only synthetic input and minimal OS environment, not developer credentials or startup hooks.
    environment = {key: os.environ[key] for key in ("SystemRoot", "WINDIR") if key in os.environ}
    environment.update(
        {
            "PATH": "",
            "LC_ALL": "C",
            "CODACY_CODE": workspace,
            "CODACY_PROJECT_TOKEN": token,
            "CODACY_COMMIT_SHA": "1" * 40,
            "CODACY_STUB_STATUS": str(exit_code),
        }
    )
    result = subprocess.run(
        [native_bash, "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", stub + scan["run"]],
        env=environment,
        capture_output=True,
        encoding="utf-8",
        timeout=10,
        check=False,
    )
    assert result.returncode == exit_code, result.stderr
    assert result.stderr == ""
    fields = result.stdout.split("\0")
    assert fields[:2] == [workspace, token]
    # Full argv equality detects unquoted paths, leaked token values, new tools/flags or missing guards.
    assert fields[2:] == [
        "run",
        "--rm",
        "--env",
        "CODACY_CODE",
        "--env",
        "CODACY_PROJECT_TOKEN",
        "--volume",
        "/var/run/docker.sock:/var/run/docker.sock",
        "--volume",
        f"{workspace}:{workspace}",
        "--volume",
        "/tmp:/tmp",
        CODACY_IMAGE,
        "--",
        "analyze",
        "--directory",
        workspace,
        "--skip-commit-uuid-validation",
        "--commit-uuid",
        "1" * 40,
        "--verbose",
        "--output",
        f"{workspace}/results.sarif",
        "--format",
        "sarif",
        "--gh-code-scanning-compat",
        "--max-allowed-issues",
        "2147483647",
        "--fail-if-incomplete",
        "",
    ]


@pytest.mark.unit
def test_codacy_job_authority_and_step_sequence_are_preserved(codacy_workflow: dict[str, Any]) -> None:
    """Keep the diagnostic repair within the existing job authority and sequence."""
    job = codacy_workflow["jobs"]["codacy-security-scan"]

    assert codacy_workflow["permissions"] == {"contents": "read"}
    assert job["permissions"] == {"contents": "read", "security-events": "write", "actions": "read"}
    assert job["concurrency"] == {
        "group": "codacy-${{ github.workflow }}-${{ github.ref }}",
        "cancel-in-progress": True,
    }
    assert job["runs-on"] == "ubuntu-latest"
    assert "continue-on-error" not in job
    assert "if" not in job
    assert [step["name"] for step in job["steps"]] == [
        "Checkout code",
        "Run Codacy Analysis CLI",
        "Validate SARIF results file",
        "Upload SARIF results file",
        "Fail when Codacy produced no SARIF",
        "Fail when Codacy analysis failed",
    ]
    assert _step(job["steps"], "Checkout code")["with"] == {"persist-credentials": False}


@pytest.mark.unit
def test_codacy_publication_triggers_are_preserved(codacy_workflow: dict[str, Any]) -> None:
    """Do not add scan events or narrow the existing publication path filters."""
    paths = [
        "**/*.py",
        "**/*.js",
        "**/*.ts",
        "**/*.tsx",
        "**/*.jsx",
        "**/*.java",
        "**/*.go",
        "**/*.rb",
        "**/*.php",
        "**/*.swift",
        "**/*.cs",
        "**/*.c",
        "**/*.cpp",
        "**/*.h",
        "**/*.hpp",
        ".github/workflows/codacy.yml",
        "!**/*.md",
        "!docs/**",
    ]
    assert codacy_workflow["on"] == {
        "push": {"branches": ["main", "Default"], "paths": paths},
        "pull_request": {"types": ["opened", "synchronize", "reopened"], "branches": ["main"], "paths": paths},
        "schedule": [{"cron": "26 15 * * 3"}],
    }


@pytest.mark.unit
def test_successful_codacy_result_is_validated_and_uploaded(codacy_steps: list[dict[str, Any]]) -> None:
    """A present SARIF file must pass JSON validation before upload."""
    validate = _step(codacy_steps, "Validate SARIF results file")
    upload = _step(codacy_steps, "Upload SARIF results file")

    assert validate["id"] == "validate_sarif"
    assert validate["if"] == "hashFiles('results.sarif') != ''"
    assert "python -m json.tool results.sarif" in validate["run"]
    assert upload["if"] == ("hashFiles('results.sarif') != '' && " "steps.validate_sarif.outcome == 'success'")
    assert upload["with"]["sarif_file"] == "results.sarif"
    assert "continue-on-error" not in upload
    assert codacy_steps.index(validate) < codacy_steps.index(upload)


@pytest.mark.unit
def test_missing_sarif_fails_even_when_codacy_reports_success(codacy_steps: list[dict[str, Any]]) -> None:
    """Missing output can never be classified as a green scan."""
    missing = _step(codacy_steps, "Fail when Codacy produced no SARIF")

    assert missing["if"] == "always() && hashFiles('results.sarif') == ''"
    assert "exit 1" in missing["run"]


@pytest.mark.unit
def test_nonzero_codacy_fails_even_when_sarif_exists(codacy_steps: list[dict[str, Any]]) -> None:
    """A partial valid SARIF upload must not mask scanner failure."""
    scan = _step(codacy_steps, "Run Codacy Analysis CLI")
    upload = _step(codacy_steps, "Upload SARIF results file")
    failure = _step(codacy_steps, "Fail when Codacy analysis failed")

    assert scan["id"] == "codacy"
    assert scan["continue-on-error"] is True
    assert failure["if"] == "always() && steps.codacy.outcome == 'failure'"
    assert "exit 1" in failure["run"]
    assert codacy_steps.index(scan) < codacy_steps.index(failure)
    assert codacy_steps.index(upload) < codacy_steps.index(failure)


@pytest.mark.unit
def test_malformed_or_rejected_sarif_cannot_be_ignored(codacy_steps: list[dict[str, Any]]) -> None:
    """JSON validation and upload rejection both remain job-fatal."""
    validate = _step(codacy_steps, "Validate SARIF results file")
    upload = _step(codacy_steps, "Upload SARIF results file")

    assert "continue-on-error" not in validate
    assert "continue-on-error" not in upload
    assert "steps.validate_sarif.outcome == 'success'" in upload["if"]
