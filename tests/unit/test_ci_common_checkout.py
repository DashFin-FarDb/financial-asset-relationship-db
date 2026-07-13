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


def _steps_for_job(job_id: str, job: object) -> list[tuple[str, list]]:
    """Return a single (job_id, steps) pair when the job defines a step list."""
    if not isinstance(job, dict):
        return []
    steps = job.get("steps") or []
    if not isinstance(steps, list):
        return []
    return [(job_id, steps)]


def _job_steps(workflow: dict) -> list[tuple[str, list]]:
    """Collect (job_id, steps) pairs from a workflow document."""
    jobs = workflow.get("jobs") or {}
    pairs: list[tuple[str, list]] = []
    for job_id, job in jobs.items():
        pairs.extend(_steps_for_job(str(job_id), job))
    return pairs


def _step_uses(step: object) -> str:
    """Return the uses value for a workflow step, if present."""
    if not isinstance(step, dict):
        return ""
    uses = step.get("uses")
    if isinstance(uses, str):
        return uses
    return ""


def _is_checkout(uses: str) -> bool:
    """Return True when a step uses actions/checkout."""
    return any(marker in uses for marker in CHECKOUT_MARKERS)


def _is_ci_common(uses: str) -> bool:
    """Return True when a step invokes the local ci-common action."""
    return uses == CI_COMMON_REF or uses.endswith("/.github/actions/ci-common")


def _ci_common_violations_for_job(workflow_name: str, job_id: str, steps: list) -> list[str]:
    """Return violation messages for ci-common steps without a prior checkout."""
    violations: list[str] = []
    saw_checkout = False
    for index, step in enumerate(steps):
        uses = _step_uses(step)
        saw_checkout = saw_checkout or _is_checkout(uses)
        if not _is_ci_common(uses):
            continue
        if saw_checkout:
            continue
        violations.append(
            f"{workflow_name}: jobs.{job_id}.steps[{index}] " "uses ci-common without a preceding actions/checkout"
        )
    return violations


def _violations_for_workflow(workflow_path: Path) -> list[str]:
    """Return missing-checkout violations for one workflow file."""
    document = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        return []
    violations: list[str] = []
    for job_id, steps in _job_steps(document):
        violations.extend(_ci_common_violations_for_job(workflow_path.name, job_id, steps))
    return violations


def _collect_ci_common_checkout_violations() -> list[str]:
    """Scan workflows and collect missing-checkout violations."""
    violations: list[str] = []
    for workflow_path in _workflow_files():
        violations.extend(_violations_for_workflow(workflow_path))
    return violations


def test_ci_common_callers_checkout_first() -> None:
    """Every job that uses ci-common must checkout before that step.

    Local composite actions are resolved from the workspace, so invoking
    ./.github/actions/ci-common without a prior actions/checkout fails at
    workflow startup.
    """
    violations = _collect_ci_common_checkout_violations()
    assert not violations, "Missing checkout before ci-common:\n" + "\n".join(violations)  # nosec B101


def test_pyre_workflow_uploads_sarif() -> None:
    """Pyre workflow must emit and upload SARIF for Code Scanning."""
    workflow_path = WORKFLOWS_DIR / "pyre.yml"
    text = workflow_path.read_text(encoding="utf-8")
    assert "--output=sarif" in text  # nosec B101
    assert "pyre-results.sarif" in text  # nosec B101
    assert "github/codeql-action/upload-sarif@" in text  # nosec B101
    assert "category: pyre" in text  # nosec B101
