"""Contract tests for the fail-closed Codacy SARIF workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "codacy.yml"


@pytest.fixture(scope="module")
def codacy_steps() -> list[dict[str, Any]]:
    """Load the Codacy job steps from the repository workflow."""
    workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    return workflow["jobs"]["codacy-security-scan"]["steps"]


def _step(steps: list[dict[str, Any]], name: str) -> dict[str, Any]:
    """Return one named workflow step."""
    return next(step for step in steps if step.get("name") == name)


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
