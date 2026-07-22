"""Contract tests for H-P1-04 required check-name reconciliation.

Guarantees:
- Policy always-required names match real GitHub Actions check-run names
- Mergify auto-merge check-success set equals the always-required policy set
- Policy does not document obsolete Workflow / job slash forms
- Frontend CI uses a unique check-run name (frontend-ci), not ambiguous "build"
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REPO_ROOT / "docs" / "ci-required-checks-policy.md"
MERGIFY_PATH = REPO_ROOT / ".mergify.yml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PROD_CONTAINER_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "production-container.yml"
FRONTEND_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "frontend-ci.yml"
PR_AGENT_CONFIG = REPO_ROOT / ".github" / "pr-agent-config.yml"

# Canonical always-required check-run names (must match policy + Mergify).
ALWAYS_REQUIRED_CHECKS = frozenset(
    {
        "Test Python 3.10",
        "Test Python 3.11",
        "Test Python 3.12",
        "Security checks",
        "build-and-smoke-test",
    }
)

PATH_FILTERED_CHECKS = frozenset({"frontend-ci"})

OBSOLETE_SLASH_FORMS = (
    "Frontend CI / build",
    "CI / test",
    "Production Container / build-and-smoke-test",
)


def _load_yaml(path: Path) -> dict:
    """Load a YAML mapping from path."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path} must parse to a mapping"
    return data


def _expand_job_check_names(job_id: str, job: object) -> list[str]:
    """Return GitHub check-run names produced by one workflow job."""
    if not isinstance(job, dict):
        return []

    display = job.get("name")
    if not isinstance(display, str) or not display.strip():
        return [job_id]

    matrix_token = "${{ matrix.python-version }}"
    if matrix_token not in display:
        return [display]

    strategy = job.get("strategy") or {}
    if not isinstance(strategy, dict):
        return [display]
    matrix = strategy.get("matrix") or {}
    if not isinstance(matrix, dict):
        return [display]
    versions = matrix.get("python-version") or []
    if not isinstance(versions, list):
        return [display]
    return [display.replace(matrix_token, str(version)) for version in versions]


def _workflow_check_names(workflow_path: Path) -> set[str]:
    """Collect check-run names from all jobs in a workflow file."""
    document = _load_yaml(workflow_path)
    jobs = document.get("jobs") or {}
    names: set[str] = set()
    if not isinstance(jobs, dict):
        return names
    for job_id, job in jobs.items():
        names.update(_expand_job_check_names(str(job_id), job))
    return names


def _policy_backtick_names(section_heading: str) -> set[str]:
    """Extract backtick-quoted names from a policy markdown #### section."""
    text = POLICY_PATH.read_text(encoding="utf-8")
    pattern = rf"#### {re.escape(section_heading)}\n(.*?)(?=\n#### |\n### |\n## |\Z)"
    match = re.search(pattern, text, flags=re.DOTALL)
    assert match is not None, f"Missing policy section: {section_heading}"
    return set(re.findall(r"`([^`]+)`", match.group(1)))


def _mergify_auto_merge_check_success() -> set[str]:
    """Return the union of check-success names required by auto-merge rules."""
    config = _load_yaml(MERGIFY_PATH)
    rules = config.get("pull_request_rules") or []
    assert isinstance(rules, list)
    names: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        actions = rule.get("actions") or {}
        if not isinstance(actions, dict) or "merge" not in actions:
            continue
        for condition in rule.get("conditions") or []:
            cond = str(condition)
            if cond.startswith("check-success="):
                names.add(cond.split("=", 1)[1])
    return names


def _pr_agent_checks(key: str) -> set[str]:
    """Return named CI checks from .github/pr-agent-config.yml."""
    config = _load_yaml(PR_AGENT_CONFIG)
    ci = config.get("ci") or {}
    assert isinstance(ci, dict)
    values = ci.get(key) or []
    assert isinstance(values, list)
    return {str(item) for item in values}


class TestAlwaysRequiredCheckNames:
    """Always-required names must exist as real workflow check-run names."""

    def test_python_ci_exposes_matrix_and_security_names(self):
        """Python CI workflow must emit Test Python 3.x and Security checks."""
        names = _workflow_check_names(CI_WORKFLOW)
        for expected in (
            "Test Python 3.10",
            "Test Python 3.11",
            "Test Python 3.12",
            "Security checks",
        ):
            assert expected in names, f"Missing check-run name in ci.yml: {expected}"

    def test_production_container_exposes_smoke_name(self):
        """Production container job id/name must be build-and-smoke-test."""
        names = _workflow_check_names(PROD_CONTAINER_WORKFLOW)
        assert "build-and-smoke-test" in names

    def test_always_required_subset_of_workflow_names(self):
        """Every always-required policy name must be produced by a PR workflow."""
        workflow_names = _workflow_check_names(CI_WORKFLOW) | _workflow_check_names(PROD_CONTAINER_WORKFLOW)
        missing = ALWAYS_REQUIRED_CHECKS - workflow_names
        assert not missing, f"Always-required names missing from workflows: {sorted(missing)}"


class TestPolicyDocumentAlignment:
    """Policy markdown must list the canonical names without slash forms."""

    def test_policy_lists_always_required_checks(self):
        """Always-required section must include every canonical check name."""
        names = _policy_backtick_names("Always required (every PR targeting `main`)")
        missing = ALWAYS_REQUIRED_CHECKS - names
        assert not missing, f"Policy missing always-required names: {sorted(missing)}"

    def test_policy_lists_path_filtered_frontend_ci(self):
        """Path-filtered section must document frontend-ci."""
        names = _policy_backtick_names(
            "Path-filtered (pass when the workflow runs; not a hard branch-protection requirement)"
        )
        assert PATH_FILTERED_CHECKS <= names

    def test_policy_has_no_obsolete_slash_forms(self):
        """Policy must not recommend Workflow / job slash check names."""
        text = POLICY_PATH.read_text(encoding="utf-8")
        for obsolete in OBSOLETE_SLASH_FORMS:
            # Mentions in "do not use" guidance are allowed; bare required-list rows are not.
            assert f"- `{obsolete}`" not in text, f"Policy still requires obsolete name: {obsolete}"

    def test_maintainer_follow_up_lists_always_required_only(self):
        """Maintainer BP guidance must list always-required names as backticks."""
        text = POLICY_PATH.read_text(encoding="utf-8")
        follow_up = text.split("## Follow-up Actions for Maintainers", 1)[1]
        for name in ALWAYS_REQUIRED_CHECKS:
            assert f"`{name}`" in follow_up, f"Maintainer section missing `{name}`"
        assert "`frontend-ci`" in follow_up
        assert "Do **not** add `frontend-ci`" in follow_up


class TestMergifyAlignment:
    """Mergify auto-merge must require exactly the always-required set."""

    def test_auto_merge_check_success_equals_always_required(self):
        """Auto-merge check-success names must equal ALWAYS_REQUIRED_CHECKS."""
        names = _mergify_auto_merge_check_success()
        assert names == ALWAYS_REQUIRED_CHECKS, (
            f"Mergify check-success mismatch.\n"
            f"  expected: {sorted(ALWAYS_REQUIRED_CHECKS)}\n"
            f"  actual:   {sorted(names)}"
        )

    def test_auto_merge_does_not_require_frontend_ci(self):
        """Path-filtered frontend-ci must not block Mergify auto-merge."""
        names = _mergify_auto_merge_check_success()
        assert "frontend-ci" not in names
        assert "build" not in names


class TestFrontendCheckName:
    """Frontend CI must report a unique check-run name."""

    def test_frontend_job_name_is_frontend_ci(self):
        """Frontend workflow job must be named frontend-ci, not build."""
        document = _load_yaml(FRONTEND_WORKFLOW)
        jobs = document.get("jobs") or {}
        assert isinstance(jobs, dict)
        assert "frontend-ci" in jobs, "Expected job id frontend-ci"
        assert "build" not in jobs, "Ambiguous job id 'build' must be removed"
        job = jobs["frontend-ci"]
        assert isinstance(job, dict)
        assert job.get("name") == "frontend-ci"

    def test_frontend_check_name_in_workflow_output(self):
        """Workflow check-run names must include frontend-ci only for that job."""
        names = _workflow_check_names(FRONTEND_WORKFLOW)
        assert names == {"frontend-ci"}


class TestPrAgentConfigAlignment:
    """PR agent required_checks must track always-required names."""

    def test_required_checks_match_always_required(self):
        """pr-agent required_checks must equal ALWAYS_REQUIRED_CHECKS."""
        required = _pr_agent_checks("required_checks")
        assert required == ALWAYS_REQUIRED_CHECKS

    def test_frontend_ci_is_optional_not_required(self):
        """frontend-ci belongs in optional_checks because it is path-filtered."""
        required = _pr_agent_checks("required_checks")
        optional = _pr_agent_checks("optional_checks")
        assert "frontend-ci" not in required
        assert "frontend-ci" in optional
        assert "build" not in required
        assert "build" not in optional
