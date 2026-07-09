"""Integration checks for architecture-compound GitHub workflow."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests.integration.test_github_workflows import GitHubActionsYamlLoader

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "architecture-compound.yml"


@pytest.mark.integration
class TestArchitectureCompoundWorkflow:
    """Guardrails for the architecture compound workflow YAML."""

    def test_workflow_loads(self) -> None:
        """Workflow YAML parses with GitHub Actions loader."""
        assert WORKFLOW.exists()
        data = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=GitHubActionsYamlLoader)
        assert data["name"] == "Architecture Compound"
        assert "on" in data or True in data  # PyYAML may coerce `on` to bool True
        jobs = data["jobs"]
        assert "observe" in jobs
        assert "synthesize" in jobs

    def test_no_main_auto_merge(self) -> None:
        """Workflow must not merge to main or auto-merge PRs."""
        text = WORKFLOW.read_text(encoding="utf-8")
        # Strip comments so documentation mentioning merge policy is not a false positive.
        code_only = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        lowered = code_only.lower()
        assert "gh pr merge" not in lowered
        assert "auto-merge" not in lowered
        assert "merge origin/main" not in lowered
        assert "knowledge/architecture-expert" in text

    def test_permission_split(self) -> None:
        """Synthesize job elevates contents write; top-level defaults to read."""
        data = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=GitHubActionsYamlLoader)
        top_perms = data.get("permissions", {})
        assert top_perms.get("contents") == "read"
        synth_perms = data["jobs"]["synthesize"].get("permissions", {})
        assert synth_perms.get("contents") == "write"
