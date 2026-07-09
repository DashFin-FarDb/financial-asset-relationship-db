"""Integration checks for architecture-compound GitHub workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.integration.test_github_workflows import load_yaml_safe

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "architecture-compound.yml"


@pytest.mark.integration
class TestArchitectureCompoundWorkflow:
    """Guardrails for the architecture compound workflow YAML."""

    def test_workflow_loads(self) -> None:
        """Workflow YAML parses with GitHub Actions loader."""
        assert WORKFLOW.exists()
        data = load_yaml_safe(WORKFLOW)
        assert data["name"] == "Architecture Compound"
        assert "on" in data or True in data  # PyYAML may coerce `on` to bool True
        jobs = data["jobs"]
        assert "synthesize" in jobs
        assert "observe" not in jobs

    def test_pull_request_synthesis_is_skipped_for_token_safety(self) -> None:
        """Write-capable synthesis must not run from PR-controlled workflow code."""
        data = load_yaml_safe(WORKFLOW)
        triggers = data.get("on", data.get(True, {}))
        assert "pull_request" not in triggers
        assert "pull_request_target" not in triggers
        assert data["jobs"]["synthesize"].get("if") is None

    def test_landed_status_mapping_is_retained_for_non_pr_events(self) -> None:
        """Merged/main/manual event mapping still promotes status to landed (AE2)."""
        text = WORKFLOW.read_text(encoding="utf-8")
        assert 'STATUS="landed"' in text
        assert "push.main" in text
        assert "workflow_dispatch" in text
        assert "pull_request.closed" not in text

    def test_push_summary_is_built_via_jq_not_inline_expression(self) -> None:
        """Push summaries must be built through jq rather than raw shell interpolation."""
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "MERGED_PR_TITLE" in text
        assert "github.event.pull_request.title" not in text
        assert 'SUMMARY=$(jq -rn --arg t "$MERGED_PR_TITLE"' in text

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
        data = load_yaml_safe(WORKFLOW)
        top_perms = data.get("permissions", {})
        assert top_perms.get("contents") == "read"
        synth_perms = data["jobs"]["synthesize"].get("permissions", {})
        assert synth_perms.get("contents") == "write"

    def test_source_and_knowledge_checkouts_are_separate(self) -> None:
        """Workflow runs current source scripts while mutating the knowledge branch."""
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "path: source" in text
        assert "path: knowledge" in text
        assert "working-directory: knowledge" in text
        assert 'SOURCE_PYTHONPATH="${GITHUB_WORKSPACE}/source/scripts"' in text
        assert "python -m compound.append_observation \\" in text
        assert "python -m compound.synthesize \\" in text
        assert '--repo-root "$PWD"' in text

    def test_knowledge_checkout_fallback_only_for_missing_branch(self) -> None:
        """Transient checkout failures must not recreate the knowledge branch from main."""
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "git ls-remote --exit-code --heads" in text
        assert "steps.knowledge_branch.outputs.exists == 'true'" in text
        assert "steps.knowledge_branch.outputs.exists == 'false'" in text
        assert "continue-on-error: true" not in text

    def test_pr_target_state_is_not_reintroduced(self) -> None:
        """PR-target-only state must stay out of the trusted synthesize workflow."""
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "PR_HEAD_SHA:" not in text
        assert "PR_ACTION:" not in text
        assert "pull_request_target" not in text

    def test_push_conflict_records_hybrid_backup(self) -> None:
        """Failed knowledge-branch push records conflict for A12 hybrid backup."""
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "--record-push-conflict" in text
