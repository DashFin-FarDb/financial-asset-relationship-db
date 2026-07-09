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
        assert WORKFLOW.exists()  # nosec B101
        data = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=GitHubActionsYamlLoader)  # nosec B506
        assert data["name"] == "Architecture Compound"  # nosec B101
        assert "on" in data or True in data  # PyYAML may coerce `on` to bool True  # nosec B101
        jobs = data["jobs"]
        assert "synthesize" in jobs  # nosec B101
        assert "observe" not in jobs  # nosec B101

    def test_closed_merged_trigger_and_landed_promotion(self) -> None:
        """Merged PR close is in trigger set and promotes status to landed (AE2)."""
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "closed" in text  # nosec B101
        assert "types: [opened, synchronize, reopened, labeled, closed]" in text  # nosec B101
        assert 'STATUS="landed"' in text  # nosec B101
        assert "pull_request.closed" in text  # nosec B101
        assert "github.event.pull_request.merged == true" in text  # nosec B101
        assert "PR_MERGED_JSON:" in text  # nosec B101
        assert "toJson(github.event.pull_request.merged || false)" in text  # nosec B101
        assert '[ "$PR_ACTION" = "closed" ] && [ "$PR_MERGED_JSON" = "true" ]' in text  # nosec B101

    def test_pr_title_via_env_not_inline_expression(self) -> None:
        """PR title must come from env (injection-safe); not interpolated into shell."""
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "PR_TITLE:" in text  # nosec B101
        assert "github.event.pull_request.title" in text  # nosec B101
        assert "'${{ github.event.pull_request.title }}'" not in text  # nosec B101
        assert '"${{ github.event.pull_request.title }}"' not in text  # nosec B101
        assert 'SUMMARY=$(jq -rn --arg t "$PR_TITLE"' in text  # nosec B101

    def test_no_main_auto_merge(self) -> None:
        """Workflow must not merge to main or auto-merge PRs."""
        text = WORKFLOW.read_text(encoding="utf-8")
        # Strip comments so documentation mentioning merge policy is not a false positive.
        code_only = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        lowered = code_only.lower()
        assert "gh pr merge" not in lowered  # nosec B101
        assert "auto-merge" not in lowered  # nosec B101
        assert "merge origin/main" not in lowered  # nosec B101
        assert "knowledge/architecture-expert" in text  # nosec B101

    def test_permission_split(self) -> None:
        """Synthesize job elevates contents write; top-level defaults to read."""
        data = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=GitHubActionsYamlLoader)  # nosec B506
        top_perms = data.get("permissions", {})
        assert top_perms.get("contents") == "read"  # nosec B101
        synth_perms = data["jobs"]["synthesize"].get("permissions", {})
        assert synth_perms.get("contents") == "write"  # nosec B101

    def test_push_conflict_records_hybrid_backup(self) -> None:
        """Failed knowledge-branch push records conflict for A12 hybrid backup."""
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "--record-push-conflict" in text  # nosec B101
