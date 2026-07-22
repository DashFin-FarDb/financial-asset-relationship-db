"""Contract tests for H-P1-04 required check-name reconciliation.

Guarantees:
- Policy always-required names match real GitHub Actions check-run names
- Each Mergify auto-merge rule requires the full always-required check-success set
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

_MATRIX_PYTHON_TOKEN = "${{ matrix.python-version }}"
_CHECK_SUCCESS_PREFIX = "check-success="
_SECTION_BOUNDARIES = ("\n#### ", "\n### ", "\n## ")


def _load_yaml(path: Path) -> dict:
    """Load a YAML mapping from path."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path} must parse to a mapping"
    return data


def _matrix_python_versions(job: dict) -> list[str]:
    """Return python-version matrix entries, or an empty list when absent."""
    strategy = job.get("strategy")
    if not isinstance(strategy, dict):
        return []
    matrix = strategy.get("matrix")
    if not isinstance(matrix, dict):
        return []
    versions = matrix.get("python-version")
    if not isinstance(versions, list):
        return []
    return [str(version) for version in versions]


def _expand_job_check_names(job_id: str, job: object) -> list[str]:
    """Return GitHub check-run names produced by one workflow job."""
    if not isinstance(job, dict):
        return []

    display = job.get("name")
    if not isinstance(display, str) or not display.strip():
        return [job_id]
    if _MATRIX_PYTHON_TOKEN not in display:
        return [display]

    versions = _matrix_python_versions(job)
    if not versions:
        return [display]
    return [display.replace(_MATRIX_PYTHON_TOKEN, version) for version in versions]


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


def _slice_markdown_section(text: str, heading_line: str) -> str:
    """Return the body after heading_line until the next markdown section heading.

    Uses str.find/slicing instead of re.DOTALL + .*? to avoid ReDoS patterns
    flagged by the AI_AGENT_GUARDRAILS regex safety rule.
    """
    start = text.find(heading_line)
    assert start != -1, f"Missing policy section heading: {heading_line!r}"
    body_start = start + len(heading_line)
    body = text[body_start:]
    end = len(body)
    for boundary in _SECTION_BOUNDARIES:
        idx = body.find(boundary)
        if idx != -1:
            end = min(end, idx)
    return body[:end]


def _policy_backtick_names(section_heading: str) -> set[str]:
    """Extract backtick-quoted names from a policy markdown #### section."""
    text = POLICY_PATH.read_text(encoding="utf-8")
    section = _slice_markdown_section(text, f"#### {section_heading}\n")
    return set(re.findall(r"`([^`]+)`", section))


def _check_success_names(conditions: object) -> set[str]:
    """Return check-success values from one Mergify conditions list."""
    if not isinstance(conditions, list):
        return set()
    names: set[str] = set()
    for condition in conditions:
        cond = str(condition)
        if cond.startswith(_CHECK_SUCCESS_PREFIX):
            names.add(cond[len(_CHECK_SUCCESS_PREFIX) :])
    return names


def _mergify_auto_merge_rules() -> list[dict]:
    """Return Mergify pull_request_rules that define a merge action."""
    config = _load_yaml(MERGIFY_PATH)
    rules = config.get("pull_request_rules") or []
    assert isinstance(rules, list)
    merge_rules: list[dict] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        actions = rule.get("actions")
        if isinstance(actions, dict) and "merge" in actions:
            merge_rules.append(rule)
    return merge_rules


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
        assert names >= PATH_FILTERED_CHECKS

    def test_policy_has_no_obsolete_slash_forms(self):
        """Policy must not recommend Workflow / job slash check names."""
        text = POLICY_PATH.read_text(encoding="utf-8")
        for obsolete in OBSOLETE_SLASH_FORMS:
            # Mentions in "do not use" guidance are allowed; bare required-list rows are not.
            assert f"- `{obsolete}`" not in text, f"Policy still requires obsolete name: {obsolete}"

    def test_maintainer_follow_up_lists_always_required_only(self):
        """Maintainer BP guidance must list always-required names as backticks."""
        text = POLICY_PATH.read_text(encoding="utf-8")
        parts = text.split("## Follow-up Actions for Maintainers", 1)
        assert len(parts) == 2, "Policy is missing '## Follow-up Actions for Maintainers' section"
        follow_up = parts[1]
        for name in ALWAYS_REQUIRED_CHECKS:
            assert f"`{name}`" in follow_up, f"Maintainer section missing `{name}`"
        assert "`frontend-ci`" in follow_up
        assert "Do **not** add `frontend-ci`" in follow_up


class TestMergifyAlignment:
    """Mergify auto-merge must require exactly the always-required set per rule."""

    def test_each_auto_merge_rule_requires_always_required_checks(self):
        """Every auto-merge rule must require the full ALWAYS_REQUIRED_CHECKS set.

        Asserts per rule (not a union across rules) so a weaker third auto-merge
        rule cannot hide behind other rules that still list the full set.
        """
        rules = _mergify_auto_merge_rules()
        assert rules, "No Mergify auto-merge rules found"
        for rule in rules:
            names = _check_success_names(rule.get("conditions"))
            assert names == ALWAYS_REQUIRED_CHECKS, (
                f"Auto-merge rule {rule.get('name')!r} check-success mismatch.\n"
                f"  expected: {sorted(ALWAYS_REQUIRED_CHECKS)}\n"
                f"  actual:   {sorted(names)}"
            )

    def test_auto_merge_does_not_require_frontend_ci(self):
        """Path-filtered frontend-ci must not block Mergify auto-merge."""
        for rule in _mergify_auto_merge_rules():
            names = _check_success_names(rule.get("conditions"))
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
