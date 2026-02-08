"""
Validation tests for configuration files modified in the current branch.

Tests cover:
- .github/pr-agent-config.yml
- .github/workflows/*.yml
- requirements-dev.txt
- Deletion validation for removed files
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

# -----------------------------
# Shared fixtures / helpers
# -----------------------------


@pytest.fixture
def repo_root() -> Path:
    """Return repository root directory (3 levels above this test file)."""
    return Path(__file__).parent.parent.parent


@pytest.fixture
def workflows_dir(repo_root: Path) -> Path:
    """Return .github/workflows directory."""
    return repo_root / ".github" / "workflows"


@pytest.fixture
def config_path(repo_root: Path) -> Path:
    """Return .github/pr-agent-config.yml path."""
    return repo_root / ".github" / "pr-agent-config.yml"


@pytest.fixture
def config_data(config_path: Path) -> Dict[str, Any]:
    """Load pr-agent-config.yml as a dict."""
    if not config_path.exists():
        pytest.skip("PR agent config not found")

    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if not isinstance(data, dict):
        pytest.fail("pr-agent-config.yml must parse to a top-level mapping (dict)")

    return data


# -----------------------------
# PR agent config tests
# -----------------------------


class TestPRAgentConfigChanges:
    """Validate changes to PR Agent configuration file."""

    def test_version_is_correct(self, config_data: Dict[str, Any]) -> None:
        """Verify agent.version is '1.0.0'."""
        agent = config_data.get("agent")
        assert isinstance(agent, dict), "Top-level 'agent' section must be a mapping"
        assert agent.get("version") == "1.0.0"

    def test_no_context_chunking_config(self, config_data: Dict[str, Any]) -> None:
        """Verify context chunking configuration has been removed."""
        agent = config_data.get("agent", {})
        if isinstance(agent, dict):
            assert "context" not in agent, "agent.context must be removed"

        limits = config_data.get("limits", {})
        if isinstance(limits, dict):
            assert "max_files_per_chunk" not in limits, "Chunking limit must be removed"

    def test_no_fallback_strategies(self, config_data: Dict[str, Any]) -> None:
        """Verify limits.fallback is not present."""
        limits = config_data.get("limits")
        if isinstance(limits, dict):
            assert "fallback" not in limits, "Fallback strategies should be removed"

    def test_basic_sections_present(self, config_data: Dict[str, Any]) -> None:
        """Check essential top-level sections exist."""
        required_sections = ["agent", "monitoring", "actions", "quality"]
        for section in required_sections:
            assert section in config_data, f"Required section '{section}' missing"

    def test_no_complex_token_management(self, config_data: Dict[str, Any]) -> None:
        """
        Ensure no chunk_size / max_tokens knobs are present.

        If you later reintroduce max_tokens intentionally, define it under limits
        with a clear rationale and update this test.
        """
        config_str = str(config_data).lower()
        assert "chunk_size" not in config_str
        assert "max_tokens" not in config_str

    def test_quality_standards_preserved(self, config_data: Dict[str, Any]) -> None:
        """Validate quality settings exist and Python uses pytest."""
        quality = config_data.get("quality")
        assert isinstance(quality, dict), "Top-level 'quality' must be a mapping"
        assert "python" in quality
        assert "typescript" in quality

        py_quality = quality.get("python")
        assert isinstance(py_quality, dict), "quality.python must be a mapping"
        assert "linter" in py_quality
        assert py_quality.get("test_runner") == "pytest"


# -----------------------------
# Workflow tests
# -----------------------------


class TestWorkflowSimplifications:
    """Validate simplifications made to GitHub workflows."""

    def test_pr_agent_workflow_simplified(self, workflows_dir: Path) -> None:
        """
        Validate PR agent workflow is simplified.

        Checks that it does not reference context_chunker or tiktoken chunking logic,
        and still installs Python dependencies.
        """
        workflow_file = workflows_dir / "pr-agent.yml"
        if not workflow_file.exists():
            pytest.skip("pr-agent.yml not found")

        content = workflow_file.read_text(encoding="utf-8")

        assert "context_chunker" not in content
        assert "tiktoken" not in content

        assert "pip install" in content
        assert "requirements.txt" in content

    def test_apisec_workflow_no_credential_conditions(self, workflows_dir: Path) -> None:
        """
        Ensure APIsec workflow does not conditionally skip based on credentials presence.
        """
        workflow_file = workflows_dir / "apisec-scan.yml"
        if not workflow_file.exists():
            pytest.skip("apisec-scan.yml not found")

        content = workflow_file.read_text(encoding="utf-8")

        assert "apisec_username != ''" not in content
        assert "apisec_password != ''" not in content

    def test_label_workflow_simplified(self, workflows_dir: Path) -> None:
        """Validate label.yml contains no config-check logic for labeler.yml."""
        workflow_file = workflows_dir / "label.yml"
        if not workflow_file.exists():
            pytest.skip("label.yml not found")

        content = workflow_file.read_text(encoding="utf-8")

        assert "check-config" not in content.lower()
        assert "labeler.yml not found" not in content

    def test_greetings_workflow_simple_messages(self, workflows_dir: Path) -> None:
        """Verify greetings workflow messages are short placeholders."""
        workflow_file = workflows_dir / "greetings.yml"
        if not workflow_file.exists():
            pytest.skip("greetings.yml not found")

        workflow_data = yaml.safe_load(workflow_file.read_text(encoding="utf-8")) or {}
        jobs = workflow_data.get("jobs", {})
        greeting_job = jobs.get("greeting", {})
        steps = greeting_job.get("steps", [])

        assert steps, "Expected greeting job steps"

        first_interaction_step = next(
            (
                s
                for s in steps
                if isinstance(s, dict) and ("first-interaction" in str(s.get("uses", "")) or "with" in s)
            ),
            None,
        )
        assert first_interaction_step is not None

        with_cfg = first_interaction_step.get("with", {}) or {}
        issue_msg = str(with_cfg.get("issue-message", ""))
        pr_msg = str(with_cfg.get("pr-message", ""))

        assert len(issue_msg) < 200
        assert len(pr_msg) < 200


# -----------------------------
# Deleted files tests
# -----------------------------


class TestDeletedFilesImpact:
    """Validate that deleted files are no longer referenced."""

    def test_labeler_yml_exists(self, repo_root: Path) -> None:
        """labeler.yml should exist."""
        labeler_file = repo_root / ".github" / "labeler.yml"
        assert labeler_file.exists(), "labeler.yml should exist"

    def test_context_chunker_removed(self, repo_root: Path) -> None:
        """context_chunker.py should be removed."""
        chunker_file = repo_root / ".github" / "scripts" / "context_chunker.py"
        assert not chunker_file.exists(), "context_chunker.py should be deleted"

    def test_scripts_readme_removed(self, repo_root: Path) -> None:
        """scripts/README.md should be removed."""
        readme_file = repo_root / ".github" / "scripts" / "README.md"
        assert not readme_file.exists(), "scripts/README.md should be deleted"

    def test_codecov_workflow_removed(self, repo_root: Path) -> None:
        """codecov.yaml should be removed if this branch deleted it."""
        codecov_file = repo_root / ".github" / "workflows" / "codecov.yaml"
        assert not codecov_file.exists(), "codecov.yaml should be deleted"

    def test_vscode_settings_removed(self, repo_root: Path) -> None:
        """.vscode/settings.json should be removed if this branch deleted it."""
        vscode_file = repo_root / ".vscode" / "settings.json"
        assert not vscode_file.exists(), ".vscode/settings.json should be deleted"

    def test_no_references_to_deleted_files_in_workflows(self, workflows_dir: Path) -> None:
        """Workflows should not reference deleted files."""
        if not workflows_dir.exists():
            pytest.skip("Workflows directory not found")

        deleted_refs = [
            "context_chunker.py",
            ".github/scripts/README.md",
        ]

        workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
        for workflow_file in workflow_files:
            content = workflow_file.read_text(encoding="utf-8")
            for deleted_ref in deleted_refs:
                assert deleted_ref not in content, f"{workflow_file.name} references deleted file: {deleted_ref}"


# -----------------------------
# requirements-dev.txt tests
# -----------------------------


class TestRequirementsDevChanges:
    """Validate changes to requirements-dev.txt."""

    @pytest.fixture
    def req_dev_path(self, repo_root: Path) -> Path:
        """Return requirements-dev.txt path."""
        return repo_root / "requirements-dev.txt"

    def test_pyyaml_added(self, req_dev_path: Path) -> None:
        """Verify PyYAML is present in requirements-dev.txt."""
        if not req_dev_path.exists():
            pytest.skip("requirements-dev.txt not found")

        content = req_dev_path.read_text(encoding="utf-8").lower()
        assert "pyyaml" in content, "PyYAML should be in requirements-dev.txt"

    def test_no_tiktoken_requirement(self, req_dev_path: Path) -> None:
        """tiktoken should not be present."""
        if not req_dev_path.exists():
            pytest.skip("requirements-dev.txt not found")

        content = req_dev_path.read_text(encoding="utf-8").lower()
        assert "tiktoken" not in content

    def test_essential_dev_dependencies_present(self, req_dev_path: Path) -> None:
        """Verify essential dev dependencies exist."""
        if not req_dev_path.exists():
            pytest.skip("requirements-dev.txt not found")

        content = req_dev_path.read_text(encoding="utf-8").lower()
        for dep in ("pytest", "pyyaml"):
            assert dep in content, f"Missing essential dev dependency: {dep}"


# -----------------------------
# .gitignore tests
# -----------------------------


class TestGitignoreChanges:
    """Validate changes to .gitignore."""

    @pytest.fixture
    def gitignore_path(self, repo_root: Path) -> Path:
        """Return .gitignore path."""
        return repo_root / ".gitignore"

    def test_codacy_instructions_ignored(self, gitignore_path: Path) -> None:
        """Verify .gitignore includes codacy.instructions.md."""
        if not gitignore_path.exists():
            pytest.skip(".gitignore not found")

        content = gitignore_path.read_text(encoding="utf-8")
        assert "codacy.instructions.md" in content

    def test_test_db_not_ignored(self, gitignore_path: Path) -> None:
        """Ensure .gitignore does not ignore test db patterns."""
        if not gitignore_path.exists():
            pytest.skip(".gitignore not found")

        content = gitignore_path.read_text(encoding="utf-8")
        assert "test_*.db" not in content

    def test_standard_ignores_present(self, gitignore_path: Path) -> None:
        """Verify standard ignore patterns are present."""
        if not gitignore_path.exists():
            pytest.skip(".gitignore not found")

        content = gitignore_path.read_text(encoding="utf-8")
        for pattern in ("__pycache__", ".pytest_cache", "node_modules", ".coverage"):
            assert pattern in content


# -----------------------------
# Codacy instructions tests
# -----------------------------


class TestCodacyInstructionsChanges:
    """Validate changes to Codacy instructions."""

    @pytest.fixture
    def codacy_instructions_path(self, repo_root: Path) -> Path:
        """Return .github/instructions/codacy.instructions.md path."""
        return repo_root / ".github" / "instructions" / "codacy.instructions.md"

    def test_codacy_instructions_simplified(self, codacy_instructions_path: Path) -> None:
        """
        Fail if repo-specific or prescriptive phrases remain.

        Note: use AND here; we want neither phrase present.
        """
        if not codacy_instructions_path.exists():
            pytest.skip("Codacy instructions file not present")

        content = codacy_instructions_path.read_text(encoding="utf-8")
        assert "git remote -v" not in content
        assert "unless really necessary" not in content

    def test_codacy_critical_rules_present(self, codacy_instructions_path: Path) -> None:
        """Verify critical rules are preserved."""
        if not codacy_instructions_path.exists():
            pytest.skip("Codacy instructions file not present")

        content = codacy_instructions_path.read_text(encoding="utf-8")
        assert "codacy_cli_analyze" in content
        assert "CRITICAL" in content
