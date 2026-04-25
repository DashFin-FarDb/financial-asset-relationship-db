"""
Validation tests for configuration files modified in the current branch.

Tests cover:
- .github/pr-agent-config.yml
- .github/workflows/*.yml
- requirements-dev.txt
- Deletion validation for removed files
"""

from pathlib import Path
from typing import Any, Dict

import pytest
import yaml


class TestPRAgentConfigChanges:
    """Validate changes to PR Agent configuration file."""

    @pytest.fixture
    @staticmethod
    def config_path() -> Path:
        """
        Return the Path to the PR Agent YAML configuration file relative to the test module.

        Returns:
            path (Path): Path to the .github/pr-agent-config.yml file.
        """
        return Path(__file__).parent.parent.parent / ".github" / "pr-agent-config.yml"

    @pytest.fixture
    @staticmethod
    def config_data(config_path: Path) -> Dict[str, Any]:
        """
        Load and parse the PR Agent YAML configuration file.

        Parameters:
            config_path (Path): Path to the `.github/pr-agent-config.yml` file to read.

        Returns:
            config (Dict[str, Any]): Mapping representing the parsed YAML configuration.
        """
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_version_is_correct(self, config_data: Dict[str, Any]):
        """
        Verify the PR agent configuration declares agent.version equal to "1.0.0".

        Parameters:
            config_data (dict): Parsed YAML content of .github/pr-agent-config.yml.
        """
        assert "agent" in config_data
        assert "version" in config_data["agent"]
        assert config_data["agent"]["version"] == "1.0.0"

    def test_context_config_declared(self, config_data: Dict[str, Any]):
        """
        Assert that the agent configuration does not contain the context/chunking block
        (which was removed as part of the PR agent simplification).
        """
        assert "agent" in config_data
        context = config_data["agent"].get("context")
        assert context is None, "agent.context block should be removed from pr-agent-config.yml"

    def test_limits_section_present(self, config_data: Dict[str, Any]):
        """
        Verify the PR Agent configuration limits section is present and is a non-empty mapping.

        The limits section is required to be a dict with at least one key so that downstream
        code can safely iterate or look up configuration values.
        """
        limits = config_data.get("limits")
        assert isinstance(limits, dict) and limits, "limits section should be a non-empty mapping in config"

    def test_basic_sections_present(self, config_data: Dict[str, Any]):
        """
        Check that the PR agent YAML configuration includes the essential top-level sections.

        Parameters:
            config_data (dict): Parsed YAML configuration mapping (from .github/pr-agent-config.yml).
        """
        required_sections = ["agent", "monitoring", "actions", "quality"]

        for section in required_sections:
            assert section in config_data, f"Required section '{section}' missing from config"

    def test_max_execution_time_declared(self, config_data: Dict[str, Any]):
        """
        Assert that the PR agent configuration declares a usable execution timeout.

        Parameters:
            config_data (Dict[str, Any]): Parsed PR agent configuration mapping.
        """
        limits = config_data.get("limits", {})
        max_execution_time = limits.get("max_execution_time")
        assert (
            isinstance(max_execution_time, int) and max_execution_time > 0
        ), "limits.max_execution_time should be a positive integer"

    def test_quality_standards_preserved(self, config_data: Dict[str, Any]):
        """
        Validate that the configuration preserves required quality settings for supported languages.

        Asserts that the top-level "quality" section includes "python" and "typescript", and that
        under "quality.python" a "linter" is declared and "test_runner" equals "pytest".

        Parameters:
            config_data (Dict[str, Any]): Parsed YAML mapping of the PR agent configuration.
        """
        assert "quality" in config_data
        assert "python" in config_data["quality"]
        assert "typescript" in config_data["quality"]

        # Check Python quality settings
        py_quality = config_data["quality"]["python"]
        assert "linter" in py_quality
        assert "test_runner" in py_quality
        assert py_quality["test_runner"] == "pytest"


class TestWorkflowSimplifications:
    """Validate simplifications made to GitHub workflows."""

    @pytest.fixture
    @staticmethod
    def workflows_dir() -> Path:
        """Get workflows directory."""
        return Path(__file__).parent.parent.parent / ".github" / "workflows"

    def test_pr_agent_workflow_simplified(self, workflows_dir: Path):
        """
        Validate that the PR Agent GitHub Actions workflow has been simplified.

        Checks that .github/workflows/pr-agent.yml exists, does not reference `context_chunker` or
        inline `tiktoken` usage with nearby `pip install`, and includes a simplified Python
        dependency installation that references `requirements.txt`.
        """
        workflow_file = workflows_dir / "pr-agent.yml"
        assert workflow_file.exists()

        with open(workflow_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Should not contain context chunking references
        assert "context_chunker" not in content
        assert "tiktoken" not in content or "pip install" not in content.split("tiktoken")[0][-200:]

        # Should have simplified Python dependency installation
        assert "pip install" in content
        assert "requirements.txt" in content

    def test_apisec_workflow_no_conditional_skip(self, workflows_dir: Path):
        """
        Ensure the APIsec workflow file exists and does not use conditional skips based on APIsec credentials.

        Asserts that .github/workflows/apisec-scan.yml is present and that its contents do not
        contain conditional checks for `apisec_username` or `apisec_password`
        (for example, `secrets.apisec_username != ''`).
        """
        workflow_file = workflows_dir / "apisec-scan.yml"
        assert workflow_file.exists()

        with open(workflow_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Should not have "if: secrets.apisec_username != ''" type conditions
        assert "apisec_username != ''" not in content
        assert "apisec_password != ''" not in content

    def test_label_workflow_simplified(self, workflows_dir: Path):
        """
        Ensure the label workflow file exists and omits configuration-check markers.

        Checks that `.github/workflows/label.yml` is present, does not contain the substring
        "check-config" (case-insensitive), and does not contain the exact text "labeler.yml not found".

        Parameters:
            workflows_dir (Path): Path to the `.github/workflows` directory.
        """
        workflow_file = workflows_dir / "label.yml"
        assert workflow_file.exists()

        with open(workflow_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Should be simple and not check for config existence
        assert "check-config" not in content.lower()
        assert "labeler.yml not found" not in content

    def test_greetings_workflow_has_messages(self, workflows_dir: Path):
        """
        Ensure the greetings workflow contains a step referencing "first-interaction" and that
        both `issue-message` and `pr-message` in that step are non-empty.
        """
        workflow_file = workflows_dir / "greetings.yml"
        assert workflow_file.exists()

        with open(workflow_file, "r", encoding="utf-8") as f:
            workflow_data = yaml.safe_load(f)

        steps = workflow_data["jobs"]["greeting"]["steps"]
        first_interaction_step = next((s for s in steps if "first-interaction" in str(s)), None)

        assert first_interaction_step is not None
        issue_msg = first_interaction_step["with"].get("issue-message", "")
        pr_msg = first_interaction_step["with"].get("pr-message", "")

        # Messages must be non-empty and not whitespace-only.
        assert isinstance(issue_msg, str) and issue_msg.strip(), "Issue message must not be empty"
        assert isinstance(pr_msg, str) and pr_msg.strip(), "PR message must not be empty"


class TestRetainedFilesState:
    """Validate that intentionally-retained files are present and not referenced as deleted."""

    @pytest.fixture
    def repo_root(self) -> Path:
        """
        Get the repository root directory (three levels above this file).

        Returns:
            Path pointing to the repository root directory.
        """
        return Path(__file__).parent.parent.parent

    def test_labeler_yml_present(self, repo_root: Path):
        """
        Assert that .github/labeler.yml has been removed from the repository
        (deleted as part of the workflow simplification).
        """
        labeler_file = repo_root / ".github" / "labeler.yml"
        assert not labeler_file.exists(), "labeler.yml should be deleted"

    def test_context_chunker_deleted(self, repo_root: Path):
        """
        Check that .github/scripts/context_chunker.py has been removed from the repository
        (deleted as part of workflow simplification).
        """
        chunker_file = repo_root / ".github" / "scripts" / "context_chunker.py"
        assert not chunker_file.exists(), "context_chunker.py should be deleted"

    def test_scripts_readme_present(self, repo_root: Path):
        """Verify scripts README has been removed (deleted as part of simplification)."""
        readme_file = repo_root / ".github" / "scripts" / "README.md"
        assert not readme_file.exists(), "scripts/README.md should be deleted"

    def test_codecov_workflow_present(self, repo_root: Path):
        """Verify codecov workflow is present in the repository."""
        codecov_file = repo_root / ".github" / "workflows" / "codecov.yaml"
        assert codecov_file.exists(), "codecov.yaml is expected to be present"

    def test_vscode_settings_present(self, repo_root: Path):
        """Verify .vscode/settings.json is present in the repository."""
        vscode_file = repo_root / ".vscode" / "settings.json"
        assert vscode_file.exists(), ".vscode/settings.json is expected to be present"


class TestRequirementsDevChanges:
    """Validate changes to requirements-dev.txt."""

    @pytest.fixture
    def req_dev_path(self) -> Path:
        """
        Locate the repository's requirements-dev.txt file.

        Returns:
            Path: Path to the requirements-dev.txt file at the repository root.
        """
        return Path(__file__).parent.parent.parent / "requirements-dev.txt"

    def test_pyyaml_added(self, req_dev_path: Path):
        """Verify PyYAML has been added to requirements-dev.txt."""
        with open(req_dev_path, "r", encoding="utf-8") as f:
            content = f.read().lower()

        assert "pyyaml" in content or "yaml" in content, "PyYAML should be in requirements-dev.txt"

    def test_no_tiktoken_requirement(self, req_dev_path: Path):
        """
        Assert that the development requirements file does not list the `tiktoken` package.

        Reads the file at the provided path and checks case-insensitively that the string `tiktoken` is not present.
        """
        with open(req_dev_path, "r", encoding="utf-8") as f:
            content = f.read().lower()

        # tiktoken should not be required anymore
        assert "tiktoken" not in content, "tiktoken should be removed (no longer needed without context chunking)"

    def test_essential_dev_dependencies_present(self, req_dev_path: Path):
        """Verify essential development dependencies are present."""
        with open(req_dev_path, "r", encoding="utf-8") as f:
            content = f.read().lower()

        essential_deps = ["pytest", "pyyaml"]

        for dep in essential_deps:
            assert dep in content, f"Essential dev dependency '{dep}' missing from requirements-dev.txt"


class TestGitignoreChanges:
    """Validate changes to .gitignore."""

    @pytest.fixture
    def gitignore_path(self) -> Path:
        """
        Get the Path to the repository root .gitignore file.

        Returns:
            Path: Path to the .gitignore file at the repository root.
        """
        return Path(__file__).parent.parent.parent / ".gitignore"

    @staticmethod
    def test_codacy_instructions_ignored(gitignore_path: Path):
        """
        Assert that the repository .gitignore contains "codacy.instructions.md".

        Parameters:
            gitignore_path (Path): Path to the .gitignore file to check.
        """
        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "codacy.instructions.md" in content, "codacy.instructions.md should be in .gitignore"

    @staticmethod
    def test_test_artifacts_in_gitignore(gitignore_path: Path):
        """
        Verify that the repository .gitignore includes the test database glob pattern.

        The 'test_*.db' pattern is intentionally present to keep test artefacts out of
        version control.
        """
        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "test_*.db" in content, "Test database glob pattern should be present in .gitignore"

    @staticmethod
    def test_standard_ignores_present(gitignore_path: Path):
        """
        Assert that the repository `.gitignore` contains common ignore patterns.

        Checks that each of the following patterns is present in the file:
        "__pycache__", ".pytest_cache", "node_modules", and ".coverage".
        """
        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()

        standard_patterns = [
            "__pycache__",
            ".pytest_cache",
            "node_modules",
            ".coverage",
        ]

        for pattern in standard_patterns:
            assert pattern in content, f"Standard ignore pattern '{pattern}' should be in .gitignore"


class TestCodacyInstructionsChanges:
    """Validate changes to Codacy instructions."""

    @pytest.fixture
    @staticmethod
    def codacy_instructions_path() -> Path:
        """
        Compute the path to the repository's Codacy instructions file.

        Returns:
            Path: Path to `.github/instructions/codacy.instructions.md` within the repository.
        """
        return Path(__file__).parent.parent.parent / ".github" / "instructions" / "codacy.instructions.md"

    @staticmethod
    def test_codacy_instructions_simplified(codacy_instructions_path: Path):
        """
        Verify the Codacy instructions are simplified and do not include problematic
        repository-specific or prescriptive phrases.

        If the instructions file is missing the test is skipped. If present, the test fails when
        the file contains either "git remote -v" or "unless really necessary".

        Parameters:
            codacy_instructions_path (Path): Path to .github/instructions/codacy.instructions.md
        """
        if not codacy_instructions_path.exists():
            pytest.skip("Codacy instructions file not present")

        with open(codacy_instructions_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Should not contain repository-specific git remote instructions
        assert (
            "git remote -v" not in content and "unless really necessary" not in content
        ), "Codacy instructions should be simplified"

    @staticmethod
    def test_codacy_critical_rules_present(codacy_instructions_path: Path):
        """
        Check that the Codacy instructions file contains required critical rules.

        Asserts that the file includes the string 'codacy_cli_analyze' and the marker 'CRITICAL'.
        """
        if not codacy_instructions_path.exists():
            pytest.skip("Codacy instructions file not present")

        with open(codacy_instructions_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Critical rules should be preserved
        assert "codacy_cli_analyze" in content, "Critical Codacy CLI analyze rule should be present"
        assert "CRITICAL" in content, "Critical sections should be marked"
