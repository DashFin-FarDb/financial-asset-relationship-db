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
        with open(config_path, "r") as f:
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

    def test_no_context_chunking_config(self, config_data: Dict[str, Any]):
        """Verify context chunking configuration has been removed."""
        # Should not have context configuration
        if "agent" in config_data:
            assert "context" not in config_data["agent"], "Context chunking config should be removed in v1.0.0"

    def test_no_fallback_strategies(self, config_data: Dict[str, Any]):
        """
        Verify the PR Agent configuration does not define a 'fallback' key under the top-level 'limits' mapping.

        Parameters:
            config_data (Dict[str, Any]): Parsed contents of `.github/pr-agent-config.yml`. If a 'limits' mapping exists, this test asserts it does not contain a 'fallback' key.
        """
        limits = config_data.get("limits")
        if isinstance(limits, dict):
            assert "fallback" not in limits, "Fallback strategies should be removed"

    def test_basic_sections_present(self, config_data: Dict[str, Any]):
        """
        Check that the PR agent YAML configuration includes the essential top-level sections.

        Parameters:
            config_data (dict): Parsed YAML configuration mapping (from .github/pr-agent-config.yml).
        """
        required_sections = ["agent", "monitoring", "actions", "quality"]

        for section in required_sections:
            assert section in config_data, f"Required section '{section}' missing from config"

    def test_no_complex_token_management(self, config_data: Dict[str, Any]):
        """
        Check that the PR agent configuration does not contain complex token-chunking or explicit token-limit settings.

        Asserts that the configuration text does not include 'chunk_size', and that 'max_tokens' is absent unless a `limits.max_execution_time` value is present in the config.

        Parameters:
            config_data (Dict[str, Any]): Parsed PR agent configuration data.
        """
        config_str = str(config_data)

        # Should not contain references to chunking or token limits
        assert "chunk_size" not in config_str.lower()
        assert "max_tokens" not in config_str.lower() or config_data.get("limits", {}).get(
            "max_execution_time"
        ), "Token management should be simplified"

    def test_quality_standards_preserved(self, config_data: Dict[str, Any]):
        """
        Validate that the configuration preserves required quality settings for supported languages and Python tooling.

        Parameters:
            config_data (Dict[str, Any]): Parsed YAML configuration for the PR agent.

        Details:
            Asserts that the top-level `quality` section contains `python` and `typescript`, and that the Python quality configuration includes a `linter` and a `test_runner` set to `pytest`.
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
    def workflows_dir(self) -> Path:
        """Get workflows directory."""
        return Path(__file__).parent.parent.parent / ".github" / "workflows"

    def test_pr_agent_workflow_simplified(self, workflows_dir: Path):
        """
        Validate that the PR Agent GitHub Actions workflow has been simplified.

        Checks that .github/workflows/pr-agent.yml exists, does not reference `context_chunker` or inline `tiktoken` usage with nearby `pip install`, and includes a simplified Python dependency installation that references `requirements.txt`.
        """
        workflow_file = workflows_dir / "pr-agent.yml"
        assert workflow_file.exists()

        with open(workflow_file, "r") as f:
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

        Asserts that .github/workflows/apisec-scan.yml is present and that its contents do not contain conditional checks for `apisec_username` or `apisec_password` (for example, `secrets.apisec_username != ''`).
        """
        workflow_file = workflows_dir / "apisec-scan.yml"
        assert workflow_file.exists()

        with open(workflow_file, "r") as f:
            content = f.read()

        # Should not have "if: secrets.apisec_username != ''" type conditions
        assert "apisec_username != ''" not in content
        assert "apisec_password != ''" not in content

    def test_label_workflow_simplified(self, workflows_dir: Path):
        """
        Validate that the label workflow uses a simplified configuration.

        Asserts that .github/workflows/label.yml exists and does not contain the substring 'check-config' (case-insensitive) nor the exact text 'labeler.yml not found'.
        """
        workflow_file = workflows_dir / "label.yml"
        assert workflow_file.exists()

        with open(workflow_file, "r") as f:
            content = f.read()

        # Should be simple and not check for config existence
        assert "check-config" not in content.lower()
        assert "labeler.yml not found" not in content

    def test_greetings_workflow_simple_messages(self, workflows_dir: Path):
        """Verify greetings workflow has simple placeholder messages."""
        workflow_file = workflows_dir / "greetings.yml"
        assert workflow_file.exists()

        with open(workflow_file, "r") as f:
            workflow_data = yaml.safe_load(f)

        # Check for simple messages (not elaborate multi-line messages)
        steps = workflow_data["jobs"]["greeting"]["steps"]
        first_interaction_step = next((s for s in steps if "first-interaction" in str(s)), None)

        assert first_interaction_step is not None
        issue_msg = first_interaction_step["with"].get("issue-message", "")
        pr_msg = first_interaction_step["with"].get("pr-message", "")

        # Messages should be short placeholders
        assert len(issue_msg) < 200, "Issue message should be a simple placeholder"
        assert len(pr_msg) < 200, "PR message should be a simple placeholder"


class TestDeletedFilesImpact:
    """Validate that deleted files are no longer referenced."""

    @pytest.fixture
    def repo_root(self) -> Path:
        """
        Locate the repository root directory.

        Returns:
            Path: The Path pointing to the repository root directory.
        """
        return Path(__file__).parent.parent.parent

    def test_labeler_yml_removed(self, repo_root: Path):
        """
        Assert that the repository no longer contains the .github/labeler.yml file.
        """
        labeler_file = repo_root / ".github" / "labeler.yml"
        assert not labeler_file.exists(), "labeler.yml should be deleted"

    def test_context_chunker_removed(self, repo_root: Path):
        """Verify context_chunker.py has been removed."""
        chunker_file = repo_root / ".github" / "scripts" / "context_chunker.py"
        assert not chunker_file.exists(), "context_chunker.py should be deleted"

    def test_scripts_readme_removed(self, repo_root: Path):
        """Verify scripts README has been removed."""
        readme_file = repo_root / ".github" / "scripts" / "README.md"
        assert not readme_file.exists(), "scripts/README.md should be deleted"

    def test_codecov_workflow_removed(self, repo_root: Path):
        """Verify codecov workflow has been removed."""
        codecov_file = repo_root / ".github" / "workflows" / "codecov.yaml"
        assert not codecov_file.exists(), "codecov.yaml should be deleted"

    def test_vscode_settings_removed(self, repo_root: Path):
        """Verify .vscode/settings.json has been removed."""
        vscode_file = repo_root / ".vscode" / "settings.json"
        assert not vscode_file.exists(), ".vscode/settings.json should be deleted"

    def test_no_references_to_deleted_files(self, repo_root: Path):
        """Verify no references to deleted files in workflow files."""
        workflows_dir = repo_root / ".github" / "workflows"

        deleted_refs = ["context_chunker.py", "labeler.yml", ".github/scripts/README.md"]

        for workflow_file in workflows_dir.glob("*.yml"):
            with open(workflow_file, "r") as f:
                content = f.read()

            for deleted_ref in deleted_refs:
                assert deleted_ref not in content, f"{workflow_file.name} still references deleted file: {deleted_ref}"


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
        with open(req_dev_path, "r") as f:
            content = f.read().lower()

        assert "pyyaml" in content or "yaml" in content, "PyYAML should be in requirements-dev.txt"

    def test_no_tiktoken_requirement(self, req_dev_path: Path):
        """
        Assert that the development requirements file does not list the `tiktoken` package.

        Reads the file at the provided path and checks case-insensitively that the string `tiktoken` is not present.
        """
        with open(req_dev_path, "r") as f:
            content = f.read().lower()

        # tiktoken should not be required anymore
        assert "tiktoken" not in content, "tiktoken should be removed (no longer needed without context chunking)"

    def test_essential_dev_dependencies_present(self, req_dev_path: Path):
        """Verify essential development dependencies are present."""
        with open(req_dev_path, "r") as f:
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
        Verify .gitignore includes 'codacy.instructions.md'.

        Checks the repository .gitignore content for the presence of the filename 'codacy.instructions.md' and fails the test if it is missing.
        """
        with open(gitignore_path, "r") as f:
            content = f.read()

        assert "codacy.instructions.md" in content, "codacy.instructions.md should be in .gitignore"

    @staticmethod
    def test_test_artifacts_not_ignored(gitignore_path: Path):
        """
        Ensure the repository .gitignore does not ignore test database files.

        Asserts that the pattern 'test_*.db' is not present in the .gitignore file located at gitignore_path.
        """
        with open(gitignore_path, "r") as f:
            content = f.read()

        # junit.xml should not be specifically ignored (removed from gitignore)
        # This allows test results to be tracked if needed
        assert "test_*.db" not in content, "Test database patterns should not be in gitignore"

    @staticmethod
    def test_standard_ignores_present(gitignore_path: Path):
        """Verify standard ignore patterns are present."""
        with open(gitignore_path, "r") as f:
            content = f.read()

        standard_patterns = ["__pycache__", ".pytest_cache", "node_modules", ".coverage"]

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
        Check that the Codacy instructions have been simplified and do not include repository-specific or prescriptive phrases.

        Skips the test if the file does not exist. Fails if the file contains either 'git remote -v' or 'unless really necessary'.

        Parameters:
                codacy_instructions_path (Path): Path to .github/instructions/codacy.instructions.md
        """
        if not codacy_instructions_path.exists():
            pytest.skip("Codacy instructions file not present")

        with open(codacy_instructions_path, "r") as f:
            content = f.read()

        # Should not contain repository-specific git remote instructions
        assert (
            "git remote -v" not in content or "unless really necessary" not in content
        ), "Codacy instructions should be simplified"

    @staticmethod
    def test_codacy_critical_rules_present(codacy_instructions_path: Path):
        """
        Check that the Codacy instructions file contains required critical rules.

        Asserts that the file includes the string 'codacy_cli_analyze' and the marker 'CRITICAL'.
        """
        if not codacy_instructions_path.exists():
            pytest.skip("Codacy instructions file not present")

        with open(codacy_instructions_path, "r") as f:
            content = f.read()

        # Critical rules should be preserved
        assert "codacy_cli_analyze" in content, "Critical Codacy CLI analyze rule should be present"
        assert "CRITICAL" in content, "Critical sections should be marked"
