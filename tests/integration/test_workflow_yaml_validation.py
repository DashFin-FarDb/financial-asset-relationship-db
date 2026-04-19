"""
Additional validation tests for modified workflow files.
Tests YAML structure, required fields, and GitHub Actions syntax.
"""

from pathlib import Path

import pytest
import yaml


class TestWorkflowYAMLValidation:
    """Validate YAML structure of modified workflow files."""

    WORKFLOW_DIR = Path(__file__).parent.parent.parent / ".github" / "workflows"

    @pytest.fixture
    def modified_workflows(self):
        """
        Names of workflow files that were modified in this branch.

        Returns:
            workflows (list[str]): Filenames of the modified GitHub Actions workflow YAML files.
        """
        return ["apisec-scan.yml", "greetings.yml", "label.yml", "pr-agent.yml"]

    def test_workflows_are_valid_yaml(self, modified_workflows):
        """
        Validate that each filename in `modified_workflows` exists under `WORKFLOW_DIR` and contains non-empty, valid YAML.

        Parameters:
            modified_workflows (Iterable[str]): Filenames of workflow files to validate.
        """
        for workflow_file in modified_workflows:
            path = self.WORKFLOW_DIR / workflow_file
            assert path.exists(), f"Workflow file not found: {workflow_file}"

            with open(path, "r") as f:
                try:
                    data = yaml.safe_load(f)
                    assert data is not None, f"Empty YAML in {workflow_file}"
                except yaml.YAMLError as e:
                    pytest.fail(f"Invalid YAML in {workflow_file}: {e}")

    def test_workflows_have_required_top_level_keys(self, modified_workflows):
        """
        Validate that each modified GitHub Actions workflow contains the top-level keys `name`, `on`, and `jobs`.

        PyYAML parses bare `on` as the boolean `True`; both forms are accepted so that
        workflows using either `on:` or `"on":` are treated correctly.

        Parameters:
            modified_workflows (list[str]): Filenames of workflow files that were modified in the branch.
        """
        required_keys = ["name", "on", "jobs"]

        for workflow_file in modified_workflows:
            path = self.WORKFLOW_DIR / workflow_file
            try:
                with open(path, "r", encoding="utf-8") as f:
                    workflow = yaml.safe_load(f)
                assert workflow is not None, f"Empty YAML in {workflow_file}"

                for key in required_keys:
                    # PyYAML parses the unquoted `on` trigger key as the boolean True;
                    # accept both the string "on" and the boolean True for that key.
                    if key == "on":
                        assert "on" in workflow or True in workflow, (
                            f"Workflow {workflow_file} missing required trigger key: on"
                        )
                    else:
                        assert key in workflow, f"Workflow {workflow_file} missing required key: {key}"
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {workflow_file}: {e}")
            except FileNotFoundError:
                pytest.fail(f"Workflow file not found: {workflow_file}")

    def test_pr_agent_workflow_simplified_correctly(self):
        """
        Validate the pr-agent GitHub Actions workflow is simplified: it removes chunking references and includes Python setup plus test execution.

        Asserts that pr-agent.yml (case-insensitive) does not contain "context_chunker" or "chunking", contains "python" to indicate Python setup, and contains at least one test-execution marker: "pytest", "uv run pytest", "python -m pytest", "run tests", or "name: test".
        """
        path = self.WORKFLOW_DIR / "pr-agent.yml"
        with open(path, "r") as f:
            content = f.read()

        content_lower = content.lower()

        # Should NOT contain chunking references
        assert "context_chunker" not in content_lower, "PR agent workflow still references context chunker"
        assert "chunking" not in content_lower, "PR agent workflow still has chunking logic"

        # SHOULD contain essential functionality
        assert "python" in content_lower, "PR agent workflow missing Python setup"
        assert any(
            marker in content_lower
            for marker in (
                "pytest",
                "uv run pytest",
                "python -m pytest",
                "run tests",
                "name: test",
            )
        ), "PR agent workflow missing test execution"


class TestRequirementsDevChanges:
    """Validate requirements-dev.txt modifications."""

    @staticmethod
    def test_requirements_dev_file_exists():
        """Check that requirements-dev.txt exists at the repository root."""
        path = Path(__file__).parent.parent.parent / "requirements-dev.txt"
        assert path.exists(), "requirements-dev.txt not found"

    @staticmethod
    def test_pyyaml_present_in_requirements_dev():
        """
        Check that PyYAML is declared in requirements-dev.txt.

        Reads the repository's requirements-dev.txt, ignores blank lines and comments,
        and asserts that a dependency beginning with "PyYAML" (case-insensitive) is present.
        """
        path = Path(__file__).parent.parent.parent / "requirements-dev.txt"
        assert path.exists(), "requirements-dev.txt not found"
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]
        assert any(line.lower().startswith("pyyaml") for line in lines), "PyYAML not found in requirements-dev.txt"
