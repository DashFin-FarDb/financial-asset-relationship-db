"""Integration checks for architecture-compound GitHub workflow."""

from __future__ import annotations

import unittest
from pathlib import Path

import pytest
import yaml

from tests.integration.test_github_workflows import GitHubActionsYamlLoader

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows"
WORKFLOW = WORKFLOW / "architecture-compound.yml"
RESTORE_SCRIPTS_CMD = " ".join(
    [
        "git restore --source=HEAD --staged --worktree --",
        "scripts/compound",
    ]
)
PUSH_CONFLICT_APPEND_CMD = " ".join(
    ["if python scripts/compound/append_observation.py", "--record-push-conflict; then"]
)
PUSH_CONFLICT_COMMIT_CMD = " ".join(
    [
        'git commit -m "chore(compound):',
        'record knowledge-branch push conflict"',
    ]
)


@pytest.mark.integration
class TestArchitectureCompoundWorkflow(unittest.TestCase):
    """Guardrails for the architecture compound workflow YAML."""

    def test_workflow_loads(self) -> None:
        """Workflow YAML parses with GitHub Actions loader."""
        self.assertTrue(WORKFLOW.exists())
        data = yaml.load(
            WORKFLOW.read_text(encoding="utf-8"),
            Loader=GitHubActionsYamlLoader,
        )  # nosec B506
        self.assertEqual(data["name"], "Architecture Compound")
        self.assertTrue("on" in data or True in data)  # PyYAML may coerce `on` to bool True
        jobs = data["jobs"]
        self.assertIn("synthesize", jobs)
        self.assertNotIn("observe", jobs)

    def test_closed_merged_trigger_and_landed_promotion(self) -> None:
        """Merged PR close is in trigger set and promotes status to landed (AE2)."""
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("closed", text)
        self.assertIn("types: [opened, synchronize, reopened, labeled, closed]", text)
        self.assertIn('STATUS="landed"', text)
        self.assertIn("pull_request.closed", text)
        self.assertIn("github.event.pull_request.merged == true", text)
        self.assertIn("PR_MERGED_JSON:", text)
        self.assertIn("toJson(github.event.pull_request.merged || false)", text)
        self.assertIn('[ "$PR_ACTION" = "closed" ] && [ "$PR_MERGED_JSON" = "true" ]', text)
        self.assertIn("PR_HEAD_SHA:", text)
        self.assertIn("pull_request.${PR_ACTION}.${HEAD_SHORT}", text)

    def test_pr_title_via_env_not_inline_expression(self) -> None:
        """PR title must come from env (injection-safe); not interpolated into shell."""
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("PR_TITLE:", text)
        self.assertIn("github.event.pull_request.title", text)
        self.assertNotIn("'${{ github.event.pull_request.title }}'", text)
        self.assertNotIn('"${{ github.event.pull_request.title }}"', text)
        self.assertIn('SUMMARY=$(jq -rn --arg t "$PR_TITLE"', text)

    def test_no_main_auto_merge(self) -> None:
        """Workflow must not merge to main or auto-merge PRs."""
        text = WORKFLOW.read_text(encoding="utf-8")
        # Strip comments so merge-policy docs are not false positives.
        non_comment_lines = []
        for line in text.splitlines():
            if not line.lstrip().startswith("#"):
                non_comment_lines.append(line)
        code_only = "\n".join(non_comment_lines)
        lowered = code_only.lower()
        self.assertNotIn("gh pr merge", lowered)
        self.assertNotIn("auto-merge", lowered)
        self.assertNotIn("merge origin/main", lowered)
        self.assertIn("knowledge/architecture-expert", text)

    def test_permission_split(self) -> None:
        """Synthesize job elevates contents write; top-level defaults to read."""
        data = yaml.load(
            WORKFLOW.read_text(encoding="utf-8"),
            Loader=GitHubActionsYamlLoader,
        )  # nosec B506
        top_perms = data.get("permissions", {})
        self.assertEqual(top_perms.get("contents"), "read")
        synth_perms = data["jobs"]["synthesize"].get("permissions", {})
        self.assertEqual(synth_perms.get("contents"), "write")

    def test_push_conflict_records_hybrid_backup(self) -> None:
        """Failed knowledge-branch push records conflict for A12 hybrid backup."""
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("--record-push-conflict", text)
        self.assertIn("docs/compound/runtime.yml", text)
        self.assertIn("record knowledge-branch push conflict", text)
        self.assertIn("push_knowledge()", text)
        self.assertIn("exit 0", text)
        self.assertIn("Push still rejected after rebase retry", text)
        # Conflict counter must be committed and pushed (not only written locally).
        self.assertIn(PUSH_CONFLICT_APPEND_CMD, text)
        self.assertIn(PUSH_CONFLICT_COMMIT_CMD, text)
        self.assertIn("Failed to push conflict-counter update", text)
        self.assertIn("record-push-conflict failed; hybrid-backup counter not updated", text)

    def test_workflow_dispatch_pins_scripts_to_origin_main(self) -> None:
        """Manual dispatch must run reviewed scripts from origin/main."""
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('elif [ "$EVENT_NAME" = "workflow_dispatch" ]; then', text)
        self.assertIn("git fetch --no-tags --depth=1 origin main", text)
        self.assertIn('TRIGGER_SHA="$(git rev-parse origin/main)"', text)
        self.assertIn("never the selected non-main ref", text)

    def test_commit_stages_allowlisted_sidecars_only(self) -> None:
        """Commit step stages allowlisted outputs and restores scripts/compound."""
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("git add .cursor/rules", text)
        self.assertIn(".cursor/rules/architecture-expert.mdc", text)
        self.assertIn(".cursor/rules/architecture-expert-query.mdc", text)
        self.assertIn(".openhands/microagents/architecture_expert.md", text)
        self.assertIn("git add docs/compound", text)
        self.assertIn(RESTORE_SCRIPTS_CMD, text)
        self.assertIn("git push origin", text)

    def test_actions_pinned_and_scripts_overlay(self) -> None:
        """Checkout/setup-python are SHA-pinned; scripts overlay from triggering SHA."""
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0", text)
        self.assertIn("actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1", text)
        self.assertIn('git checkout "${TRIGGER_SHA}" -- scripts/compound', text)
        self.assertIn("git restore --staged scripts/compound", text)
        self.assertIn(RESTORE_SCRIPTS_CMD, text)
        self.assertIn('echo "TRIGGER_SHA=${TRIGGER_SHA}" >> "$GITHUB_ENV"', text)
        self.assertNotIn("continue-on-error:", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertIn("architecture-compound-knowledge", text)
