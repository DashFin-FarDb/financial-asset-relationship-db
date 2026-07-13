"""Regression checks for local ci-common composite usage."""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOWS_DIR = Path(__file__).resolve().parents[2] / ".github" / "workflows"
CI_COMMON_REF = "./.github/actions/ci-common"
CHECKOUT_MARKERS = (
    "actions/checkout@",
    "uses: actions/checkout",
)


def _workflow_files() -> list[Path]:
    """Return workflow YAML files under .github/workflows."""
    return sorted(WORKFLOWS_DIR.glob("*.yml")) + sorted(WORKFLOWS_DIR.glob("*.yaml"))


def _job_steps(workflow: dict) -> list[tuple[str, list]]:
    """Collect (job_id, steps) pairs from a workflow document."""
    jobs = workflow.get("jobs") or {}
    pairs: list[tuple[str, list]] = []
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps") or []
        if isinstance(steps, list):
            pairs.append((str(job_id), steps))
    return pairs


def _step_uses(step: object) -> str:
    """Return the uses value for a workflow step, if present."""
    if not isinstance(step, dict):
        return ""
    uses = step.get("uses")
    return uses if isinstance(uses, str) else ""


def test_ci_common_callers_checkout_first() -> None:
    """Every job that uses ci-common must checkout before that step.

    Local composite actions are resolved from the workspace, so invoking
    ./.github/actions/ci-common without a prior actions/checkout fails at
    workflow startup.
    """
    violations: list[str] = []

    for workflow_path in _workflow_files():
        document = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            continue

        for job_id, steps in _job_steps(document):
            saw_checkout = False
            for index, step in enumerate(steps):
                uses = _step_uses(step)
                if any(marker in uses for marker in CHECKOUT_MARKERS):
                    saw_checkout = True
                if uses == CI_COMMON_REF or uses.endswith("/.github/actions/ci-common"):
                    if not saw_checkout:
                        violations.append(
                            f"{workflow_path.name}: jobs.{job_id}.steps[{index}] "
                            "uses ci-common without a preceding actions/checkout"
                        )

    assert not violations, "Missing checkout before ci-common:\n" + "\n".join(violations)


def test_pyre_workflow_uploads_sarif() -> None:
    """Pyre workflow must emit and upload SARIF for Code Scanning."""
    workflow_path = WORKFLOWS_DIR / "pyre.yml"
    text = workflow_path.read_text(encoding="utf-8")
    assert "--output=sarif" in text
    assert "pyre-results.sarif" in text
    assert "github/codeql-action/upload-sarif@" in text
    assert "category: pyre" in text
