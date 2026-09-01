"""Contract tests for the workflow security boundary remediated by issue 1785."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = PROJECT_ROOT / ".github" / "workflows"
TRIVY_VERSION = "v0.74.0"
EXPECTED_CHECKOUTS = {
    "bearer.yml": 1,
    "codacy.yml": 1,
    "codeql.yml": 1,
    "contrast-scan.yml": 1,
    "devskim.yml": 1,
    "docker.yml": 2,
    "eslint.yml": 1,
    "hadolint.yml": 1,
    "njsscan.yml": 1,
    "pmd.yml": 1,
    "pyre.yml": 1,
    "snyk-container.yml": 1,
    "snyk-infrastructure.yml": 1,
    "snyk-security.yml": 1,
    "summary.yml": 1,
    "trivy.yml": 1,
    "veracode.yml": 1,
    "zscaler-iac-scan.yml": 1,
}
TRIVY_WORKFLOWS = ("docker.yml", "trivy.yml")


def _load_workflow(name: str) -> dict[str, Any]:
    """Load one governed workflow as UTF-8 YAML."""
    workflow = yaml.safe_load((WORKFLOWS_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(workflow, dict), f"{name} must contain a workflow mapping"
    return workflow


def _steps(name: str) -> Iterator[dict[str, Any]]:
    """Yield every ordinary job step from a governed workflow."""
    jobs = _load_workflow(name).get("jobs", {})
    assert isinstance(jobs, dict), f"{name} must define a jobs mapping"
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps", [])
        if not isinstance(steps, list):
            continue
        yield from (step for step in steps if isinstance(step, dict))


@pytest.mark.unit
def test_reconciled_checkouts_do_not_persist_credentials() -> None:
    """All 19 reconciled checkout steps discard their temporary credentials."""
    actual: dict[str, int] = {}
    unguarded: list[str] = []

    for name in EXPECTED_CHECKOUTS:
        checkouts = [step for step in _steps(name) if str(step.get("uses", "")).startswith("actions/checkout@")]
        actual[name] = len(checkouts)
        for step in checkouts:
            options = step.get("with", {})
            if not isinstance(options, dict) or options.get("persist-credentials") is not False:
                unguarded.append(f"{name}: {step.get('name', 'unnamed checkout')}")

    assert actual == EXPECTED_CHECKOUTS
    assert sum(actual.values()) == 19
    assert not unguarded, "checkout credentials must not persist:\n" + "\n".join(unguarded)


@pytest.mark.unit
def test_trivy_downloads_use_the_ratified_release() -> None:
    """Both setup actions download the same reviewed immutable Trivy release."""
    for name in TRIVY_WORKFLOWS:
        setup_steps = [
            step for step in _steps(name) if str(step.get("uses", "")).startswith("aquasecurity/setup-trivy@")
        ]
        assert len(setup_steps) == 1, f"{name} must contain exactly one setup-trivy step"
        options = setup_steps[0].get("with", {})
        assert isinstance(options, dict)
        assert options.get("version") == TRIVY_VERSION


@pytest.mark.unit
def test_docker_workflow_cannot_publish_packages() -> None:
    """The validation-only Docker workflow keeps no package-write authority."""
    workflow = _load_workflow("docker.yml")
    permissions = workflow.get("permissions", {})
    assert isinstance(permissions, dict)
    assert permissions.get("contents") == "read"
    assert "packages" not in permissions

    build_steps = [
        step for step in _steps("docker.yml") if str(step.get("uses", "")).startswith("docker/build-push-action@")
    ]
    assert len(build_steps) == 1
    options = build_steps[0].get("with", {})
    assert isinstance(options, dict)
    assert options.get("push") is False


@pytest.mark.unit
def test_summary_write_uses_an_explicit_token() -> None:
    """Disabling checkout credentials does not remove summary write authority."""
    write_steps = [step for step in _steps("summary.yml") if "gh issue comment" in str(step.get("run", ""))]
    assert len(write_steps) == 1
    environment = write_steps[0].get("env", {})
    assert isinstance(environment, dict)
    assert environment.get("GH_TOKEN") == "${{ secrets.GITHUB_TOKEN }}"
