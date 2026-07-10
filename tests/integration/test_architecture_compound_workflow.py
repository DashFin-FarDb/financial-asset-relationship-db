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
        data = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=GitHubActionsYamlLoader)  # nosec B506
        assert data["name"] == "Architecture Compound"
        assert "on" in data or True in data  # PyYAML may coerce `on` to bool True
        jobs = data["jobs"]
        assert "synthesize" in jobs
        assert "observe" not in jobs

    def test_closed_merged_trigger_and_landed_promotion(self) -> None:
        """Merged PR close is in trigger set and promotes status to landed (AE2)."""
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "closed" in text
        assert "types: [opened, synchronize, reopened, labeled, closed]" in text
        assert 'STATUS="landed"' in text
        assert "pull_request.closed" in text
        assert "github.event.pull_request.merged == true" in text
        assert "PR_MERGED_JSON:" in text
        assert "toJson(github.event.pull_request.merged || false)" in text
        assert '[ "$PR_ACTION" = "closed" ] && [ "$PR_MERGED_JSON" = "true" ]' in text
        assert "PR_HEAD_SHA:" in text
        assert "pull_request.${PR_ACTION}.${HEAD_SHORT}" in text

    def test_pr_title_via_env_not_inline_expression(self) -> None:
        """PR title must come from env (injection-safe); not interpolated into shell."""
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "PR_TITLE:" in text
        assert "github.event.pull_request.title" in text
        assert "'${{ github.event.pull_request.title }}'" not in text
        assert '"${{ github.event.pull_request.title }}"' not in text
        assert 'SUMMARY=$(jq -rn --arg t "$PR_TITLE"' in text

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
        data = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=GitHubActionsYamlLoader)  # nosec B506
        top_perms = data.get("permissions", {})
        assert top_perms.get("contents") == "read"
        synth_perms = data["jobs"]["synthesize"].get("permissions", {})
        assert synth_perms.get("contents") == "write"

    def test_push_conflict_records_hybrid_backup(self) -> None:
        """Failed knowledge-branch push records conflict for A12 hybrid backup."""
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "--record-push-conflict" in text
        assert "docs/compound/runtime.yml" in text
        assert "record knowledge-branch push conflict" in text
        assert "push_knowledge()" in text
        assert "exit 0" in text
        assert "Push still rejected after rebase retry" in text

    def test_workflow_dispatch_pins_scripts_to_origin_main(self) -> None:
        """Manual dispatch must run reviewed scripts from origin/main, not selected ref."""
        text = WORKFLOW.read_text(encoding="utf-8")
        assert 'elif [ "$EVENT_NAME" = "workflow_dispatch" ]; then' in text
        assert "git fetch --no-tags --depth=1 origin main" in text
        assert 'TRIGGER_SHA="$(git rev-parse origin/main)"' in text
        assert "never the selected non-main ref" in text

    def test_commit_stages_allowlisted_sidecars_only(self) -> None:
        """Commit step stages allowlisted outputs and fully restores scripts/compound."""
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "git add .cursor/rules" not in text
        assert ".cursor/rules/architecture-expert.mdc" in text
        assert ".cursor/rules/architecture-expert-query.mdc" in text
        assert ".openhands/microagents/architecture_expert.md" in text
        assert "git add docs/compound" in text
        assert "git restore --source=HEAD --staged --worktree -- scripts/compound" in text
        assert "git push origin" in text

    def test_actions_pinned_and_scripts_overlay(self) -> None:
        """Checkout/setup-python are SHA-pinned; scripts overlay from triggering SHA."""
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5" in text
        assert "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065" in text
        assert 'git checkout "${TRIGGER_SHA}" -- scripts/compound' in text
        assert "git restore --staged scripts/compound" in text
        assert "git restore --source=HEAD --staged --worktree -- scripts/compound" in text
        assert 'echo "TRIGGER_SHA=${TRIGGER_SHA}" >> "$GITHUB_ENV"' in text
        assert "continue-on-error:" not in text
        assert "cancel-in-progress: false" in text
        assert "architecture-compound-knowledge" in text
