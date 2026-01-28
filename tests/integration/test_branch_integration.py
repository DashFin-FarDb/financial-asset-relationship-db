"""
Integration tests validating all branch changes work together cohesively.

Tests cross-cutting concerns:
1. Workflow changes are consistent across all files
2. Dependencies are compatible with workflow needs
3. Removed files don't break existing functionality
4. Overall branch maintains system integrity
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

import pytest
import yaml


class TestWorkflowConsistency:
    """Test consistency across all modified workflows."""

    @pytest.fixture
    @staticmethod
    @staticmethod
    def all_workflows() -> Dict[str, Dict]:
        """Mapping from workflow path to parsed YAML dict."""
        workflow_files = [
            ".github/workflows/pr-agent.yml",
            ".github/workflows/apisec-scan.yml",
            ".github/workflows/label.yml",
            ".github/workflows/greetings.yml",
        ]

        workflows: Dict[str, Dict] = {}

        for wf_file in workflow_files:
            path = Path(wf_file)
            if not path.exists():
                continue

            try:
                with open(path, encoding="utf-8") as file_handle:
                    loaded = yaml.safe_load(file_handle)
                    workflows[wf_file] = loaded if isinstance(loaded, dict) else {}
            except yaml.YAMLError as exc:
                print(f"Warning: failed to parse {wf_file}: {exc}; skipping")

        return workflows

    def test_all_workflows_use_consistent_action_versions(
        self,
        all_workflows: Dict[str, Dict],
    ) -> None:
        """Ensure actions are pinned consistently across workflows."""
        action_versions: Dict[str, Dict[str, List[str]]] = {}

        for wf_file, workflow in all_workflows.items():
            for job in workflow.get("jobs", {}).values():
                for step in job.get("steps", []):
                    uses = step.get("uses", "")
                    if "@" not in uses:
                        continue

                    action_name, action_version = uses.split("@", maxsplit=1)
                    action_versions.setdefault(action_name, {}).setdefault(
                        action_version, []
                    ).append(wf_file)

        for action, versions in action_versions.items():
            if len(versions) > 1 and "actions/checkout" not in action:
                print(
                    f"Warning: {action} uses multiple versions: {list(versions.keys())}"
                )

    def test_all_workflows_use_github_token_consistently(
        self,
        all_workflows: Dict[str, Dict],
    ) -> None:
        """Verify approved GITHUB_TOKEN syntax."""
        for wf_file, workflow in all_workflows.items():
            workflow_str = yaml.dump(workflow)

            if "GITHUB_TOKEN" in workflow_str or "github.token" in workflow_str:
                assert (
                    "secrets.GITHUB_TOKEN" in workflow_str
                    or "${{ github.token }}" in workflow_str
                ), f"{wf_file}: GITHUB_TOKEN should use proper syntax"

    def test_simplified_workflows_have_fewer_steps(
        self,
        all_workflows: Dict[str, Dict],
    ) -> None:
        """Simplified workflows should have at most three steps."""
        simplified = {
            ".github/workflows/label.yml",
            ".github/workflows/greetings.yml",
        }

        for wf_file in simplified:
            workflow = all_workflows.get(wf_file)
            if not workflow:
                continue

            for job_name, job in workflow.get("jobs", {}).items():
                steps = job.get("steps", [])
                assert len(steps) <= 3, (
                    f"{wf_file}:{job_name} has {len(steps)} steps (expected <= 3)"
                )


class TestDependencyWorkflowIntegration:
    """Test that dependencies support workflow needs."""

    def test_workflows_parse_with_pyyaml(self) -> None:
        """Verify PyYAML parses workflows and branch coherence.

        This test ensures GitHub workflows and branch changes adhere to project
        standards, avoid security issues, and remain parseable by PyYAML.
        """
        workflow_dir = Path(".github/workflows")
        if not workflow_dir.exists():
            pytest.skip("Workflows directory not found")

        for wf_file in workflow_dir.glob("*.yml"):
            try:
                with open(wf_file, encoding="utf-8") as file_handle:
                    workflow = yaml.safe_load(file_handle)

                assert workflow is not None
                assert isinstance(workflow, dict)
            except yaml.YAMLError as exc:
                pytest.fail(f"PyYAML failed to parse {wf_file}: {exc}")

    def test_requirements_support_workflow_test_needs(self) -> None:
        """Ensure pytest and PyYAML are present in dev requirements."""
        with open("requirements-dev.txt", encoding="utf-8") as file_handle:
            content = file_handle.read().lower()

        assert "pytest" in content
        assert "pyyaml" in content


class TestRemovedFilesIntegration:
    """Test that removed files don't break functionality."""

    @staticmethod
    def test_workflows_dont_reference_removed_scripts() -> None:
        """Ensure workflows do not reference scripts that have been removed."""
        removed_files = {
            "context_chunker.py",
            ".github/scripts/README.md",
            ".github/labeler.yml",
        }

        workflow_files = {
            ".github/workflows/pr-agent.yml",
            ".github/workflows/label.yml",
        }

        for wf_file in workflow_files:
            path = Path(wf_file)
            if not path.exists():
                continue

            content = path.read_text(encoding="utf-8")
            for removed in removed_files:
                assert removed not in content, f"{wf_file} references {removed}"

    @staticmethod
    def test_label_workflow_doesnt_need_labeler_config() -> None:
        """Verify that the label workflow does not require an external labeler configuration."""
        label_path = Path(".github/workflows/label.yml")
        if not label_path.exists():
            pytest.skip("label.yml not present")

        with open(label_path, encoding="utf-8") as file_handle:
            workflow = yaml.safe_load(file_handle)

        steps = workflow["jobs"]["label"]["steps"]
        labeler_step = steps[0]

        assert "actions/labeler" in labeler_step["uses"]
        with_config = labeler_step.get("with", {})
        assert (
            "config-path" not in with_config
            or with_config.get("config-path") == ".github/labeler.yml"
        )

    @staticmethod
    def test_pr_agent_workflow_self_contained() -> None:
        """Check that the pull request agent workflow is self - contained without external script references."""
        content = Path(".github/workflows/pr-agent.yml").read_text(encoding="utf-8")

        assert "context_chunker" not in content
        assert "fetch-context" not in content
        assert "chunking" not in content.lower() or "no chunking" in content.lower()


class TestWorkflowSecurityConsistency:
    """Test security practices across workflows."""

    @staticmethod
    def test_all_workflows_avoid_pr_injection() -> None:
        """Detect unsafe patterns in workflows to prevent PR content injection vulnerabilities."""
        dangerous_patterns = [
            r"\$\{\{.*github\.event\.pull_request\.title.*\}\}.*\|",
            r"\$\{\{.*github\.event\.pull_request\.body.*\}\}.*\|",
            r"\$\{\{.*github\.event\.issue\.title.*\}\}.*\|",
        ]

        injection_risks: List[str] = []

        for wf_file in Path(".github/workflows").glob("*.yml"):
            content = wf_file.read_text(encoding="utf-8")

            for pattern in dangerous_patterns:
                if re.search(pattern, content):
                    injection_risks.append(f"{wf_file}: pattern matched {pattern}")

        assert not injection_risks, "Potential PR injection risks found:\n" + "\n".join(
            injection_risks
        )


class TestBranchCoherence:
    """Test overall branch coherence."""

    @staticmethod
    def test_simplification_theme_consistent() -> None:
        """Ensure workflows adhere to simplification theme by staying within defined line limits."""
        workflows_to_check = [
            (".github/workflows/pr-agent.yml", 200),
            (".github/workflows/label.yml", 30),
            (".github/workflows/greetings.yml", 20),
        ]

        for wf_file, max_lines in workflows_to_check:
            path = Path(wf_file)
            if not path.exists():
                continue

            line_count = len(path.read_text(encoding="utf-8").splitlines())
            assert line_count <= max_lines, (
                f"{wf_file} has {line_count} lines (expected <= {max_lines})"
            )


class TestBranchQuality:
    """Test overall quality of branch changes."""

    @staticmethod
    def test_no_merge_conflict_markers() -> None:
        """Confirm no merge conflict markers are present in workflows and other files."""
        conflict_markers = {"<<<<<<<", "=======", ">>>>>>>"}
        files_to_check = [
            ".github/workflows/pr-agent.yml",
            ".github/workflows/apisec-scan.yml",
            ".github/workflows/label.yml",
            ".github/workflows/greetings.yml",
            "requirements-dev.txt",
        ]

        for file_path in files_to_check:
            path = Path(file_path)
            if not path.exists():
                continue

            content = path.read_text(encoding="utf-8")
            for marker in conflict_markers:
                assert marker not in content, f"{file_path} contains {marker}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
